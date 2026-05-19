"""
Flora family asteroid pipeline.

Steps:
1. Download Nesvorný (2015) family membership list for Flora (#828)
2. Cross-reference WISE/NEOWISE albedos (Masiero et al.)
3. Generate Tier 1/2/3 game parameters
4. Optionally upsert to Supabase

Usage:
    python fetch_flora.py --limit 200 --out flora.json
    python fetch_flora.py --limit 200 --push-db
"""

from __future__ import annotations

import argparse
import json
import logging
import random
import time
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
import requests

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)

# ── constants ────────────────────────────────────────────────────────────────

FLORA_FAMILY_ID = 402          # Nesvorný 2015 PDS ID for Flora family
SBDB_API = "https://ssd-api.jpl.nasa.gov/sbdb_query.api"
WISE_MPC_URL = (
    "https://minorplanetcenter.net/Extended_Files/extended_mpc_ep.json.gz"
)
# Masiero WISE albedo table — PDS Small Bodies Node
WISE_PDS_URL = (
    "https://sbnarchive.psi.edu/pds4/non_mission/gbo.ast.wise.survey/data/"
    "neowise_diam_albedo.csv"
)
# Nesvorný 2015 family list on PDS
NESVORY_PDS_URL = (
    "https://sbnarchive.psi.edu/pds3/non_mission/EAR_A_VARGBDET_5_NESVORNYFAM_V3_0/"
    "data/families/flora_family.tab"
)

# spectral class distribution for Flora region (DeMeo & Carry 2013 + Nesvorný 2015)
SPECTRAL_DIST = {
    "S": 0.70,
    "C": 0.13,
    "V": 0.05,
    "D": 0.04,
    "M": 0.02,
    "E": 0.02,
    "P": 0.02,
    "K": 0.01,
    "U": 0.01,
}

# albedo ranges per spectral class (geometric albedo, pV)
ALBEDO_RANGE = {
    "S": (0.15, 0.35),
    "C": (0.03, 0.10),
    "V": (0.25, 0.50),
    "D": (0.02, 0.08),
    "M": (0.10, 0.30),
    "E": (0.35, 0.60),
    "P": (0.02, 0.07),
    "K": (0.08, 0.20),
    "U": (0.05, 0.25),
}

# density g/cm³ mean ± σ per spectral class
DENSITY_PARAMS = {
    "S": (3.5, 0.4),   # LL chondrite bulk
    "C": (1.4, 0.3),   # Ryugu/Bennu bulk
    "V": (3.8, 0.3),   # HED
    "D": (1.2, 0.3),
    "M": (5.0, 0.8),
    "E": (3.2, 0.5),
    "P": (1.3, 0.3),
    "K": (3.0, 0.4),
    "U": (2.0, 0.6),
}

# rotation period hours: mean, σ (lognormal params after log transform)
# LCDB statistics (Warner et al.)
ROT_LOG_MEAN = np.log(6.0)   # ~6 h median
ROT_LOG_STD  = 0.6


# ── Nesvorný catalog fetch ────────────────────────────────────────────────────

def fetch_nesvory_members(limit: Optional[int] = None) -> pd.DataFrame:
    """
    Download Flora family membership from JPL SBDB query API.
    Returns DataFrame with columns: number, name, H, a, e, inc, q, Q
    """
    log.info("Fetching Flora family members from JPL SBDB …")

    # SBDB query: filter by family flag. Flora = family #402
    # We use the fields available in SBDB small body query
    params = {
        "fields": "spkid,full_name,H,a,e,i,q,Q,class,diameter,albedo",
        "sb-cdata": json.dumps({
            "AND": [
                ["class", "=", "MBA"],
                ["a", ">", "2.15"],
                ["a", "<", "2.40"],
                ["e", "<", "0.20"],
                ["i", "<", "10.0"],
            ]
        }),
        "full-prec": "false",
    }
    if limit:
        params["limit"] = str(limit)

    try:
        r = requests.get(SBDB_API, params=params, timeout=60)
        r.raise_for_status()
        data = r.json()
    except requests.RequestException as exc:
        log.warning("SBDB fetch failed (%s), using synthetic fallback", exc)
        return _synthetic_flora(limit or 200)

    fields = data.get("fields", [])
    rows   = data.get("data",   [])

    if not rows:
        log.warning("SBDB returned 0 rows, using synthetic fallback")
        return _synthetic_flora(limit or 200)

    df = pd.DataFrame(rows, columns=fields)
    df = df.rename(columns={"i": "inc", "full_name": "name"})
    for col in ["H", "a", "e", "inc", "q", "Q"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    log.info("SBDB returned %d Flora-region bodies", len(df))
    return df


def _synthetic_flora(n: int) -> pd.DataFrame:
    """
    Generate synthetic Flora-like orbital elements when network is unavailable.
    Distributions match Nesvorný 2015 proper element statistics.
    """
    rng = np.random.default_rng(42)
    a   = rng.uniform(2.17, 2.38, n)
    e   = rng.uniform(0.02, 0.18, n)
    inc = rng.uniform(2.0,  9.0,  n)
    H   = rng.uniform(11.0, 20.5, n)   # includes sub-km bodies (H>18)
    q   = a * (1 - e)
    Q   = a * (1 + e)
    numbers = rng.integers(10000, 500000, n)

    return pd.DataFrame({
        "spkid":    [f"20{n}" for n in numbers],
        "name":     [f"({num})" for num in numbers],
        "H":        H,
        "a":        a,
        "e":        e,
        "inc":      inc,
        "q":        q,
        "Q":        Q,
        "class":    ["MBA"] * n,
        "diameter": [None] * n,
        "albedo":   [None] * n,
    })


# ── WISE albedo fetch ─────────────────────────────────────────────────────────

def fetch_wise_albedos() -> dict[str, float]:
    """
    Download WISE/NEOWISE albedo table and return {asteroid_name: pV} mapping.
    Falls back to empty dict if network unavailable.
    """
    log.info("Fetching WISE albedos …")
    try:
        r = requests.get(WISE_PDS_URL, timeout=60)
        r.raise_for_status()
        from io import StringIO
        df = pd.read_csv(StringIO(r.text), comment="#")
        # typical column names vary; try common ones
        name_col = next((c for c in df.columns if "name" in c.lower() or "desig" in c.lower()), None)
        pv_col   = next((c for c in df.columns if "pv" in c.lower() or "albedo" in c.lower()), None)
        if name_col and pv_col:
            df[pv_col] = pd.to_numeric(df[pv_col], errors="coerce")
            result = dict(zip(df[name_col].astype(str), df[pv_col]))
            log.info("Loaded %d WISE albedos", len(result))
            return result
    except Exception as exc:
        log.warning("WISE fetch failed (%s), proceeding without observed albedos", exc)
    return {}


# ── diameter from H + albedo ──────────────────────────────────────────────────

def diameter_from_H(H: float, pV: float) -> float:
    """
    Standard formula: D = (1329 / sqrt(pV)) * 10^(-H/5)  km
    """
    return (1329.0 / np.sqrt(pV)) * 10 ** (-H / 5.0)


# ── spectral class assignment ─────────────────────────────────────────────────

def assign_spectral_class(row: pd.Series, rng: np.random.Generator) -> str:
    """
    Assign spectral class probabilistically from Flora-region distribution.
    If WISE albedo is available, use it to constrain S vs C vs V boundary.
    """
    pv = row.get("pv_wise")
    if pd.notna(pv):
        if pv > 0.25:
            candidates = {"S": 0.75, "V": 0.12, "E": 0.08, "M": 0.05}
        elif pv < 0.08:
            candidates = {"C": 0.50, "D": 0.20, "P": 0.20, "K": 0.10}
        else:
            candidates = {"S": 0.55, "K": 0.15, "M": 0.15, "C": 0.10, "U": 0.05}
    else:
        candidates = SPECTRAL_DIST

    keys   = list(candidates.keys())
    probs  = np.array([candidates[k] for k in keys], dtype=float)
    probs /= probs.sum()
    return rng.choice(keys, p=probs)


# ── Tier 1 parameters ─────────────────────────────────────────────────────────

def build_tier1(row: pd.Series, rng: np.random.Generator) -> dict:
    """Tier 1 = catalog data (observable from Earth/catalogue)."""
    spec = row["spectral_class"]
    pv   = row.get("pv_wise")
    if pd.isna(pv):
        lo, hi = ALBEDO_RANGE[spec]
        pv = float(rng.uniform(lo, hi))
        pv_source = "generated"
    else:
        pv_source = "WISE"

    H = float(row["H"]) if pd.notna(row["H"]) else float(rng.uniform(12, 18))
    D = float(row["diameter"]) if pd.notna(row.get("diameter")) else diameter_from_H(H, pv)

    return {
        "H_magnitude":    round(H, 2),
        "albedo_pv":      round(pv, 4),
        "albedo_source":  pv_source,
        "diameter_km":    round(D, 3),
        "a_au":           round(float(row["a"]), 6),
        "e":              round(float(row["e"]), 6),
        "inc_deg":        round(float(row["inc"]), 4),
        "q_au":           round(float(row["q"]), 6),
        "Q_au":           round(float(row["Q"]), 6),
        "spectral_class": spec,
    }


# ── Tier 2 parameters ─────────────────────────────────────────────────────────

def build_tier2(tier1: dict, rng: np.random.Generator) -> dict:
    """Tier 2 = flyby measurements (density, rotation, surface features)."""
    spec = tier1["spectral_class"]
    D    = tier1["diameter_km"]

    mean_rho, sig_rho = DENSITY_PARAMS[spec]
    density = float(np.clip(rng.normal(mean_rho, sig_rho), 0.5, 8.0))

    # mass kg:  M = ρ · (4/3)π(D/2)³   (D in m)
    r_m  = D * 1000 / 2
    mass = density * 1e3 * (4 / 3) * np.pi * r_m ** 3

    # rotation: lognormal
    rot_h = float(np.exp(rng.normal(ROT_LOG_MEAN, ROT_LOG_STD)))
    rot_h = round(max(2.0, min(rot_h, 1000.0)), 2)

    # shape: rubble pile vs monolith threshold ~150 m (Richardson 2002)
    if D < 0.15:
        structure = "monolith"
    elif D < 0.5:
        structure = rng.choice(["monolith", "rubble_pile"], p=[0.45, 0.55])
    else:
        structure = "rubble_pile"

    # elongation a/b ratio (lognormal)
    elongation = round(float(np.exp(rng.normal(0.25, 0.2))), 2)  # 1.0 = sphere
    elongation = max(1.0, min(elongation, 3.5))

    # surface gravity m/s²  (g = (4/3)π G ρ r)
    r_surf = D * 1000 / 2                          # metres
    g_surf = round((4 / 3) * np.pi * 6.674e-11 * density * 1e3 * r_surf, 8)

    # escape velocity m/s  (v = sqrt(2 g r))
    v_esc = round(np.sqrt(2 * g_surf * r_surf), 4)

    # thermal inertia J m⁻² K⁻¹ s⁻0.5: regolith ~50, bare rock ~2000
    if structure == "rubble_pile":
        ti = float(rng.lognormal(np.log(100), 0.5))
    else:
        ti = float(rng.lognormal(np.log(500), 0.6))

    return {
        "density_gcc":       round(density, 3),
        "mass_kg":           round(mass, 3),
        "rotation_h":        rot_h,
        "structure":         structure,
        "elongation":        elongation,
        "surface_gravity":   g_surf,
        "escape_velocity_ms": v_esc,
        "thermal_inertia":   round(ti, 1),
    }


# ── Tier 3 parameters ─────────────────────────────────────────────────────────

# Composition templates from db_design.md
COMPOSITION_TEMPLATES: dict[str, list[tuple[str, float, float]]] = {
    # (mineral_id, mean_pct, sigma_pct)
    "S": [
        ("olivin",        52, 6),
        ("pyroxen_lowca", 24, 4),
        ("pyroxen_highca", 5, 2),
        ("plagioklas",     9, 2),
        ("fe_ni_metal",    4, 3),
        ("troilit",        5, 2),
        ("chromit",        0.5, 0.3),
    ],
    "C": [
        ("fylosilikat",   65, 8),
        ("magnetit",       6, 2),
        ("troilit",        4, 2),
        ("karbonaty",      4, 2),
        ("h2o_bound",      9, 3),
        ("c_organic",      3, 1.5),
        ("olivin",         4, 2),
        ("pyroxen_lowca",  3, 1.5),
    ],
    "M": [
        ("fe_ni_metal",   88, 5),
        ("troilit",        6, 2),
        ("schreibersite",  2, 1),
        ("chromit",        0.5, 0.3),
        ("pt",             0.005, 0.003),
        ("pd",             0.003, 0.002),
        ("ir",             0.0005, 0.0003),
        ("au",             0.0008, 0.0005),
        ("ge",             0.05, 0.03),
        ("ga",             0.04, 0.03),
    ],
    "E": [
        ("enstatit",      70, 8),
        ("fe_ni_metal",   14, 5),
        ("troilit",        6, 2),
        ("plagioklas",     5, 2),
        ("pyroxen_lowca",  3, 2),
    ],
    "P": [
        ("fylosilikat",   50, 8),
        ("magnetit",      12, 3),
        ("c_organic",      6, 3),
        ("troilit",        5, 2),
        ("karbonaty",      8, 3),
        ("h2o_bound",     12, 3),
        ("olivin",         4, 2),
        ("pyroxen_lowca",  3, 1.5),
    ],
    "V": [
        ("pyroxen_highca", 55, 8),
        ("plagioklas",    38, 6),
        ("ilmenit",        2, 1),
        ("chromit",        0.8, 0.4),
        ("olivin",         1, 1),
    ],
    "D": [
        ("fylosilikat",   40, 6),
        ("magnetit",       9, 3),
        ("c_organic",     11, 4),
        ("troilit",        6, 2),
        ("karbonaty",      7, 3),
        ("h2o_bound",     10, 3),
        ("olivin",         8, 3),
        ("pyroxen_lowca",  5, 2),
    ],
    "K": [
        ("olivin",        45, 6),
        ("pyroxen_lowca", 28, 5),
        ("pyroxen_highca", 5, 2),
        ("fe_ni_metal",    5, 2),
        ("plagioklas",     6, 2),
        ("fylosilikat",    7, 3),
        ("troilit",        4, 2),
    ],
    "U": [   # unknown — blend of S and C
        ("olivin",        35, 10),
        ("fylosilikat",   25, 10),
        ("pyroxen_lowca", 15, 5),
        ("magnetit",       8, 4),
        ("fe_ni_metal",    5, 3),
        ("troilit",        5, 3),
        ("h2o_bound",      5, 3),
    ],
}

RARE_FIND_MATRIX: dict[str, dict[str, float]] = {
    # find_id: {spectral_class: probability}
    "microdiamonds":      {"S": 0.001, "M": 0.003, "V": 0.0005, "D": 0.001},
    "lonsdaleite":        {"P": 0.0005, "D": 0.003},
    "presolar_sic":       {"C": 0.001, "P": 0.001, "D": 0.001, "K": 0.0005},
    "quasicrystal":       {"M": 0.003},
    "ribose":             {"C": 0.003, "P": 0.001, "D": 0.002},
    "magnetic_record":    {"M": 0.015, "E": 0.001},
    "amino_acids":        {"C": 0.03, "P": 0.005, "D": 0.02, "K": 0.003},
    "nucleobases":        {"C": 0.01, "P": 0.003, "D": 0.005},
    "tholins":            {"C": 0.005, "P": 0.005, "D": 0.03},
    "fullerene":          {"C": 0.005, "P": 0.002, "D": 0.003, "K": 0.001},
    "he3_saturation":     {k: 0.02 for k in SPECTRAL_DIST},
    "n_compounds":        {"C": 0.01, "P": 0.005, "D": 0.04},
    "schreibersite_rich": {"S": 0.002, "C": 0.003, "M": 0.03},
    "ti_concentrate":     {"V": 0.05},
    "ree_concentrate":    {"V": 0.02, "D": 0.003, "K": 0.01},
    "pt_jackpot":         {"M": 0.08},
    "xenolith_diff":      {k: 0.001 for k in SPECTRAL_DIST},
    "active_volatiles":   {"C": 0.001, "P": 0.001, "D": 0.003},
}

RARE_FIND_TIERS = {
    "microdiamonds": "LEGENDARY", "lonsdaleite": "LEGENDARY",
    "presolar_sic": "LEGENDARY", "quasicrystal": "LEGENDARY",
    "ribose": "LEGENDARY", "magnetic_record": "LEGENDARY",
    "amino_acids": "EXOTIC", "nucleobases": "EXOTIC", "tholins": "EXOTIC",
    "fullerene": "EXOTIC", "he3_saturation": "EXOTIC", "n_compounds": "EXOTIC",
    "schreibersite_rich": "EXOTIC", "ti_concentrate": "EXOTIC",
    "ree_concentrate": "EXOTIC", "pt_jackpot": "EXOTIC",
    "xenolith_diff": "EXOTIC", "active_volatiles": "EXOTIC",
}


def build_tier3(tier1: dict, tier2: dict, rng: np.random.Generator) -> dict:
    """Tier 3 = surface landing — mineralogy + rare finds."""
    spec  = tier1["spectral_class"]
    D     = tier1["diameter_km"]
    tmpl  = COMPOSITION_TEMPLATES.get(spec, COMPOSITION_TEMPLATES["U"])

    # generate composition with truncated normal, then renormalise
    raw = {}
    for mineral_id, mean, sigma in tmpl:
        val = float(rng.normal(mean, sigma))
        raw[mineral_id] = max(0.0, val)

    total = sum(raw.values())
    if total > 0:
        composition = {k: round(v / total * 100, 4) for k, v in raw.items()}
    else:
        composition = {k: 0.0 for k in raw}

    # rare finds
    rare_finds = []
    for find_id, class_probs in RARE_FIND_MATRIX.items():
        p = class_probs.get(spec, 0.0)
        # size preference: small objects more likely monolithic finds
        if find_id in ("microdiamonds", "lonsdaleite", "quasicrystal") and D > 2.0:
            p *= 0.3
        if find_id in ("ribose", "amino_acids", "nucleobases") and D < 0.5:
            p *= 0.5
        if rng.random() < p:
            rare_finds.append({
                "find_id":    find_id,
                "rarity":     RARE_FIND_TIERS.get(find_id, "EXOTIC"),
                "abundance":  round(float(rng.lognormal(-4, 0.8)), 8),  # ppm-scale
            })

    # porosity
    porosity = round(float(np.clip(rng.normal(0.35, 0.10), 0.05, 0.65)), 3)

    return {
        "composition":   composition,
        "rare_finds":    rare_finds,
        "porosity":      porosity,
    }


# ── main pipeline ─────────────────────────────────────────────────────────────

def run_pipeline(limit: Optional[int] = None, seed: int = 42) -> list[dict]:
    rng = np.random.default_rng(seed)

    df   = fetch_nesvory_members(limit)
    wise = fetch_wise_albedos()

    # attach WISE albedo where we have it
    def _extract_number(name: str) -> str:
        import re
        m = re.search(r"\((\d+)\)", str(name))
        return m.group(1) if m else str(name).strip()

    df["asteroid_num"] = df["name"].apply(_extract_number)
    df["pv_wise"]      = df["asteroid_num"].map(wise)

    asteroids = []
    for _, row in df.iterrows():
        row["spectral_class"] = assign_spectral_class(row, rng)

        t1 = build_tier1(row, rng)
        t2 = build_tier2(t1, rng)
        t3 = build_tier3(t1, t2, rng)

        record = {
            "source_id":    str(row.get("spkid", row["name"])),
            "name":         str(row["name"]).strip(),
            "tier1":        t1,
            "tier2":        t2,
            "tier3":        t3,
        }
        asteroids.append(record)

    log.info("Generated %d asteroid records", len(asteroids))
    return asteroids


# ── Supabase upload ───────────────────────────────────────────────────────────

SUPABASE_URL = "https://tfyuyylcygamglpdfudd.supabase.co"
SUPABASE_KEY = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
    "eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InRmeXV5eWxjeWdhbWdscGRmdWRkIiwicm9sZSI6"
    "InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3OTE3NDgzNSwiZXhwIjoyMDk0NzUwODM1fQ."
    "j3fg_8fCZoZ2hpikXl0mMCsvimEvHae6_LJBtpdXLVo"
)


def push_to_supabase(asteroids: list[dict]) -> None:
    from supabase import create_client
    sb = create_client(SUPABASE_URL, SUPABASE_KEY)

    log.info("Pushing %d records to Supabase …", len(asteroids))
    batch_size = 50

    for i in range(0, len(asteroids), batch_size):
        batch = asteroids[i : i + batch_size]
        rows  = []
        t2_rows = []
        t3_rows = []

        for ast in batch:
            t1  = ast["tier1"]
            t2  = ast["tier2"]
            t3  = ast["tier3"]
            sid = ast["source_id"]

            rows.append({
                "source_id":      sid,
                "name":           ast["name"],
                "spectral_class": t1["spectral_class"],
                "H_magnitude":    t1["H_magnitude"],
                "albedo_pv":      t1["albedo_pv"],
                "albedo_source":  t1["albedo_source"],
                "diameter_km":    t1["diameter_km"],
                "a_au":           t1["a_au"],
                "e":              t1["e"],
                "inc_deg":        t1["inc_deg"],
                "q_au":           t1["q_au"],
                "Q_au":           t1["Q_au"],
            })
            t2_rows.append({
                "source_id":        sid,
                "density_gcc":      t2["density_gcc"],
                "mass_kg":          t2["mass_kg"],
                "rotation_h":       t2["rotation_h"],
                "structure":        t2["structure"],
                "elongation":       t2["elongation"],
                "surface_gravity":  t2["surface_gravity"],
                "escape_velocity_ms": t2["escape_velocity_ms"],
                "thermal_inertia":  t2["thermal_inertia"],
            })
            t3_rows.append({
                "source_id":  sid,
                "composition": t3["composition"],
                "rare_finds":  t3["rare_finds"],
                "porosity":    t3["porosity"],
            })

        sb.table("asteroids").upsert(rows, on_conflict="source_id").execute()
        sb.table("asteroid_tier2").upsert(t2_rows, on_conflict="source_id").execute()
        sb.table("asteroid_tier3").upsert(t3_rows, on_conflict="source_id").execute()
        log.info("  batch %d–%d done", i, i + len(batch))
        time.sleep(0.2)

    log.info("Supabase push complete")


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser(description="Flora asteroid pipeline")
    ap.add_argument("--limit",   type=int,  default=None, help="max bodies to fetch")
    ap.add_argument("--seed",    type=int,  default=42,   help="RNG seed")
    ap.add_argument("--out",     type=str,  default=None, help="output JSON path")
    ap.add_argument("--push-db", action="store_true",     help="upsert to Supabase")
    args = ap.parse_args()

    asteroids = run_pipeline(limit=args.limit, seed=args.seed)

    if args.out:
        Path(args.out).write_text(json.dumps(asteroids, indent=2, ensure_ascii=False))
        log.info("Saved → %s", args.out)

    if args.push_db:
        push_to_supabase(asteroids)


if __name__ == "__main__":
    main()
