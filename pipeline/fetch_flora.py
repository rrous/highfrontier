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
import time
from pathlib import Path
from typing import Optional

CACHE_DIR = Path(__file__).parent / ".data_cache"
CACHE_DIR.mkdir(exist_ok=True)

import numpy as np
import pandas as pd
import requests

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)

# ── constants ────────────────────────────────────────────────────────────────

SBDB_API = "https://ssd-api.jpl.nasa.gov/sbdb_query.api"

# Nesvorný 2015 v3.0 — Flora family #402, fixed-width ASCII table
# Columns (START_BYTE, BYTES): AST_NUMBER(1,6) A_PROP(8,7) E_PROP(16,8)
#   SIN_I_PROP(25,8) ABS_MAG(34,5) C_PARAM(40,8) FAMILY_NUMBER(49,3) FAMILY_NAME(53,18)
NESVORY_URL = (
    "https://sbnarchive.psi.edu/pds3/non_mission/"
    "EAR_A_VARGBDET_5_NESVORNYFAM_V3_0/data/families/402_flora.tab"
)

# WISE/NEOWISE main-belt diameters & albedos (Masiero et al. 2011–2015)
# CSV: ASTEROID_NUMBER, PROV_DESIG, MPC_PACKED_NAME, ABSOLUTE_MAG, SLOPE_PARAM,
#      MEAN_JD, N_W1..N_W4, FIT_CODE, DIAMETER, DIAMETER_ERR,
#      V_ALBEDO, V_ALBEDO_ERR, IR_ALBEDO, IR_ALBEDO_ERR,
#      BEAMING_PARAM, BEAMING_PARAM_ERR, STACKED_FLAG, REFERENCE
WISE_URL = (
    "https://sbnarchive.psi.edu/pds3/non_mission/"
    "EAR_A_COMPIL_5_NEOWISEDIAM_V1_0/data/neowise_mainbelt.tab"
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
    Download Flora family members from Nesvorný 2015 PDS catalog (402_flora.tab).

    Fixed-width format (bytes, 1-based):
      1–6   AST_NUMBER   asteroid number
      8–14  A_PROP       proper semi-major axis [AU]
      16–23 E_PROP       proper eccentricity
      25–32 SIN_I_PROP   sin(proper inclination)
      34–38 ABS_MAG      absolute magnitude H
      40–47 C_PARAM      velocity distance parameter

    Returns DataFrame with columns:
      number, a_prop, e_prop, sin_i_prop, H, c_param, name, inc_prop,  q, Q
    """
    log.info("Fetching Flora family members from Nesvorný 2015 PDS …")
    cache_file = CACHE_DIR / "402_flora.tab"
    if cache_file.exists():
        log.info("  (using cache: %s)", cache_file)
        raw = cache_file.read_text()
    else:
        try:
            r = requests.get(NESVORY_URL, timeout=60)
            r.raise_for_status()
            raw = r.text
            cache_file.write_text(raw)
        except requests.RequestException as exc:
            raise RuntimeError(
            f"Cannot download Nesvorný catalog: {exc}\n"
            f"URL: {NESVORY_URL}"
        ) from exc

    colspecs = [(0, 6), (7, 14), (15, 23), (24, 32), (33, 38), (39, 47)]
    names    = ["number", "a_prop", "e_prop", "sin_i_prop", "H", "c_param"]

    from io import StringIO
    df = pd.read_fwf(StringIO(raw), colspecs=colspecs, names=names, header=None)
    df["number"]     = pd.to_numeric(df["number"],     errors="coerce").astype("Int64")
    df["a_prop"]     = pd.to_numeric(df["a_prop"],     errors="coerce")
    df["e_prop"]     = pd.to_numeric(df["e_prop"],     errors="coerce")
    df["sin_i_prop"] = pd.to_numeric(df["sin_i_prop"], errors="coerce")
    df["H"]          = pd.to_numeric(df["H"],          errors="coerce")
    df["c_param"]    = pd.to_numeric(df["c_param"],    errors="coerce")
    df = df.dropna(subset=["number", "a_prop", "e_prop", "sin_i_prop"])
    df["inc_prop"]   = np.degrees(np.arcsin(df["sin_i_prop"].clip(-1, 1)))
    df["name"]       = df["number"].apply(lambda n: f"({int(n)})")
    # derive osculating-approximate q and Q from proper elements
    df["q"] = df["a_prop"] * (1 - df["e_prop"])
    df["Q"] = df["a_prop"] * (1 + df["e_prop"])

    if limit:
        df = df.head(limit)

    log.info("Nesvorný catalog: %d Flora family members", len(df))
    return df.reset_index(drop=True)


# ── WISE albedo fetch ─────────────────────────────────────────────────────────

# Column indices in neowise_mainbelt.tab (0-based after CSV split):
#  0  ASTEROID_NUMBER   1  PROV_DESIG   2  MPC_PACKED_NAME
#  3  ABSOLUTE_MAG      4  SLOPE_PARAM  5  MEAN_JD
#  6-9 N_W1..N_W4      10 FIT_CODE
# 11  DIAMETER         12  DIAMETER_ERR
# 13  V_ALBEDO         14  V_ALBEDO_ERR
# ...
_WISE_COLS = [
    "ast_number", "prov_desig", "mpc_packed", "H_wise", "G",
    "mean_jd", "n_w1", "n_w2", "n_w3", "n_w4", "fit_code",
    "diameter_km", "diameter_err", "v_albedo", "v_albedo_err",
    "ir_albedo", "ir_albedo_err", "beaming", "beaming_err",
    "stacked_flag", "reference",
]

def fetch_wise_albedos() -> pd.DataFrame:
    """
    Download WISE/NEOWISE main-belt albedo+diameter table.
    Returns DataFrame indexed by integer asteroid number with columns:
      diameter_km, v_albedo, v_albedo_err
    Only rows with valid V_ALBEDO are included.
    """
    log.info("Fetching WISE/NEOWISE main-belt albedos (~24 MB) …")
    cache_file = CACHE_DIR / "neowise_mainbelt.tab"
    if cache_file.exists():
        log.info("  (using cache: %s)", cache_file)
        raw = cache_file.read_text()
    else:
        try:
            r = requests.get(WISE_URL, timeout=120)
            r.raise_for_status()
            raw = r.text
            cache_file.write_text(raw)
        except requests.RequestException as exc:
            log.warning("WISE fetch failed (%s) — proceeding without observed albedos", exc)
            return pd.DataFrame()

    from io import StringIO
    df = pd.read_csv(
        StringIO(raw),
        names=_WISE_COLS,
        header=None,
        skipinitialspace=True,
        dtype={"mpc_packed": str},
        low_memory=False,
    )
    df["ast_number"] = pd.to_numeric(df["ast_number"], errors="coerce").astype("Int64")
    df["v_albedo"]   = pd.to_numeric(df["v_albedo"],   errors="coerce")
    df["diameter_km"]= pd.to_numeric(df["diameter_km"],errors="coerce")

    # keep only rows with valid albedo; if multiple observations per body, take mean
    df = df.dropna(subset=["ast_number", "v_albedo"])
    df = df[df["v_albedo"] > 0]
    agg = (
        df.groupby("ast_number")
        .agg(
            diameter_km=("diameter_km", "mean"),
            v_albedo=("v_albedo", "mean"),
            v_albedo_err=("v_albedo_err", "mean"),
            n_obs=("v_albedo", "count"),
        )
        .reset_index()
    )
    log.info("WISE: %d unique bodies with albedo measurement", len(agg))
    return agg


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
    pv_raw = row.get("pv_wise")
    pv = float(pv_raw) if (pv_raw is not None and pd.notna(pv_raw)) else None
    if pv is not None:
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

    pv_wise = row.get("pv_wise")
    if pd.notna(pv_wise) and float(pv_wise) > 0:
        pv        = float(pv_wise)
        pv_source = "WISE"
    else:
        lo, hi    = ALBEDO_RANGE[spec]
        pv        = float(rng.uniform(lo, hi))
        pv_source = "generated"

    H = float(row["H"]) if pd.notna(row.get("H")) else float(rng.uniform(12, 18))

    # prefer WISE diameter; fall back to H+pV formula
    d_wise = row.get("diameter_wise")
    if pd.notna(d_wise) and float(d_wise) > 0:
        D = float(d_wise)
    else:
        D = diameter_from_H(H, pv)

    return {
        "H_magnitude":    round(H, 2),
        "albedo_pv":      round(pv, 4),
        "albedo_source":  pv_source,
        "diameter_km":    round(D, 3),
        "a_au":           round(float(row["a_prop"]), 6),
        "e":              round(float(row["e_prop"]), 6),
        "inc_deg":        round(float(row["inc_prop"]), 4),
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

    flora = fetch_nesvory_members(limit)
    wise  = fetch_wise_albedos()

    # merge WISE into Flora by integer asteroid number
    if not wise.empty:
        flora = flora.merge(
            wise[["ast_number", "diameter_km", "v_albedo", "v_albedo_err"]],
            left_on="number", right_on="ast_number", how="left",
        )
        flora = flora.rename(columns={
            "v_albedo":     "pv_wise",
            "v_albedo_err": "pv_wise_err",
            "diameter_km":  "diameter_wise",
        })
        flora = flora.drop(columns=["ast_number"], errors="ignore")
        wise_hit = flora["pv_wise"].notna().sum()
        log.info("WISE cross-match: %d / %d bodies have measured albedo", wise_hit, len(flora))
    else:
        flora["pv_wise"]      = np.nan
        flora["pv_wise_err"]  = np.nan
        flora["diameter_wise"]= np.nan

    asteroids = []
    for _, row in flora.iterrows():
        row = row.copy()
        row["spectral_class"] = assign_spectral_class(row, rng)

        t1 = build_tier1(row, rng)
        t2 = build_tier2(t1, rng)
        t3 = build_tier3(t1, t2, rng)

        record = {
            "source_id": str(int(row["number"])),
            "name":      row["name"],
            "tier1":     t1,
            "tier2":     t2,
            "tier3":     t3,
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
