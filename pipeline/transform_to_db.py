"""
Transform raw_data/flora_full.json into the route-planner Supabase schema.

The scientific catalog (flora_full.json) and the route-planner DB are two
different layers:

  flora_full.json   = "Identita" — raw scientific truth (Tier 1/2/3 numeric)
  Supabase tables   = "Charakter" — what the player sees: scene coordinates,
                      formatted display strings, gameplay flags

This script is the ETL adapter between them. It produces rows for three
tables (asteroids / asteroid_tier2 / asteroid_tier3) that match the live
schema the HTML route planner reads.

Positioning
-----------
flora_full.json has only proper elements (a, e, i) — no orbital phase, so a
literal heliocentric position is impossible. Instead bodies are projected
into proper-element velocity space (Zappalà metric), where Euclidean
distance equals dynamical relatedness. Coordinates are kept in m/s.

Tiering
-------
asteroids       = CATALOG — degraded values (precision driven by whether the
                  underlying datum is actually WISE/LCDB-measured)
asteroid_tier2  = FLYBY   — true values + `anomalies` flagging surprises (⚡)
asteroid_tier3  = STOP    — mineralogy string + rare-find headline

Usage
-----
    python transform_to_db.py --out db_payload.json
    SUPABASE_URL=... SUPABASE_SERVICE_KEY=... python transform_to_db.py --push
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import os
import random
import statistics
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_IN = REPO_ROOT / "raw_data" / "flora_full.json"

# ── positioning ───────────────────────────────────────────────────────────────

# Zappalà et al. (1990) velocity-distance weights for (δa/a, δe, δsin i)
ZAPPALA_W = (5.0 / 4.0, 2.0, 2.0)
AU_YR_TO_MS = 4744.0  # 1 AU/yr ≈ 4744 m/s


def compute_positions(records: list[dict]) -> dict[str, tuple[float, float, float]]:
    """
    Project proper elements into velocity space and return per-body
    (x_pos, y_pos, z_pos) in m/s, shifted so every axis starts at 0.

    x ← semi-major axis, y ← eccentricity, z ← inclination.
    """
    a   = [r["tier1"]["a_au"] for r in records]
    e   = [r["tier1"]["e"] for r in records]
    sin_i = [math.sin(math.radians(r["tier1"]["inc_deg"])) for r in records]

    a_mean   = statistics.mean(a)
    e_mean   = statistics.mean(e)
    sin_mean = statistics.mean(sin_i)

    # orbital speed v = n·a for the family mean (m/s)
    v_ms = (2.0 * math.pi / math.sqrt(a_mean)) * AU_YR_TO_MS

    kx, ky, kz = (math.sqrt(w) for w in ZAPPALA_W)
    raw: dict[str, tuple[float, float, float]] = {}
    for r in records:
        t1 = r["tier1"]
        x = v_ms * kx * ((t1["a_au"] - a_mean) / a_mean)
        y = v_ms * ky * (t1["e"] - e_mean)
        z = v_ms * kz * (math.sin(math.radians(t1["inc_deg"])) - sin_mean)
        raw[r["source_id"]] = (x, y, z)

    off_x = -min(v[0] for v in raw.values())
    off_y = -min(v[1] for v in raw.values())
    off_z = -min(v[2] for v in raw.values())
    return {
        sid: (round(x + off_x, 2), round(y + off_y, 2), round(z + off_z, 2))
        for sid, (x, y, z) in raw.items()
    }


# ── formatting helpers ────────────────────────────────────────────────────────

_SUP = str.maketrans("0123456789-", "⁰¹²³⁴⁵⁶⁷⁸⁹⁻")


def fmt_mass(kg: float) -> str | None:
    """Format a mass in kg as e.g. '4.2×10¹⁸'."""
    if kg is None or kg <= 0:
        return None
    exp = int(math.floor(math.log10(kg)))
    mant = kg / 10 ** exp
    return f"{mant:.1f}×10{str(exp).translate(_SUP)}"


def fmt_density(gcc: float) -> str | None:
    if gcc is None or gcc <= 0:
        return None
    return f"{gcc:.1f} g/cm³"


def body_rng(asteroid_id: int) -> random.Random:
    """Deterministic per-body RNG so catalog degradation is reproducible."""
    return random.Random((asteroid_id * 2654435761) & 0xFFFFFFFF)


# ── eco / minerals / rare-find labels ─────────────────────────────────────────

STRUCT_LABEL = {"rubble_pile": "RUBBLE PILE", "monolith": "MONOLIT"}

MINERAL_NAMES = {
    "olivin": "olivín", "pyroxen": "pyroxen", "plagioklas": "plagioklas",
    "fe_ni_metal": "Fe-Ni", "troilit": "troilit", "chromit": "chromit",
    "fylosilikat": "fylosilikát", "magnetit": "magnetit", "karbonaty": "karbonáty",
    "h2o_bound": "H₂O", "c_organic": "org. C", "enstatit": "enstatit",
    "schreibersite": "schreibersite", "ilmenit": "ilmenit",
    "pt": "Pt", "pd": "Pd", "ir": "Ir", "au": "Au", "ge": "Ge", "ga": "Ga",
}

FIND_LABELS = {
    "microdiamonds": "MIKRODIAMANTY", "lonsdaleite": "LONSDALEIT",
    "presolar_sic": "PRESOLÁRNÍ SiC", "quasicrystal": "KVAZIKRYSTAL",
    "ribose": "RIBÓZA", "magnetic_record": "MAGNETICKÝ ZÁZNAM",
    "amino_acids": "AMINOKYSELINY", "nucleobases": "NUKLEOBÁZE",
    "tholins": "THOLINY", "fullerene": "FULLERENY", "he3_saturation": "He-3 SATURACE",
    "n_compounds": "DUSÍKATÉ SLOUČENINY", "schreibersite_rich": "SCHREIBERSITE",
    "ti_concentrate": "Ti KONCENTRÁT", "ree_concentrate": "REE KONCENTRÁT",
    "pt_jackpot": "PLATINOVÝ JACKPOT", "xenolith_diff": "XENOLIT",
    "active_volatiles": "AKTIVNÍ VOLATILY",
}

# rare finds detectable already at flyby (db_design.md §7 reveal column)
T2_REVEALABLE_FINDS = {"magnetic_record", "ti_concentrate", "active_volatiles", "pt_jackpot"}


def minerals_str(composition: dict[str, float]) -> str:
    """Build the Tier-3 display string, merging low/high-Ca pyroxene."""
    merged: dict[str, float] = {}
    for mineral, pct in composition.items():
        key = "pyroxen" if mineral.startswith("pyroxen") else mineral
        merged[key] = merged.get(key, 0.0) + pct
    items = sorted(merged.items(), key=lambda kv: kv[1], reverse=True)
    parts = [f"{MINERAL_NAMES.get(k, k)} {v:.0f} %" for k, v in items if v >= 0.5]
    return ", ".join(parts[:6])


def special_str(rare_finds: list[dict]) -> str | None:
    """Headline for the rarest find on the body."""
    if not rare_finds:
        return None
    rank = {"LEGENDARY": 0, "EXOTIC": 1}
    best = min(rare_finds, key=lambda rf: rank.get(rf.get("rarity"), 2))
    return FIND_LABELS.get(best["find_id"], best["find_id"].upper())


def eco_true(composition: dict[str, float], rare_finds: list[dict]) -> list[str]:
    """Precise eco tags from actual composition + rare finds (flyby / stop)."""
    eco: list[str] = []
    if composition.get("fe_ni_metal", 0) >= 4.0:
        eco.append("Fe")
    find_ids = {rf["find_id"] for rf in rare_finds}
    if composition.get("pt", 0) > 0 or "pt_jackpot" in find_ids:
        eco.append("PGM")
    if composition.get("h2o_bound", 0) >= 3.0:
        eco.append("H₂O")
    return eco


def eco_catalog(spectral_type: str) -> list[str]:
    """Coarse eco guess from spectral type only (catalog tier)."""
    if spectral_type == "M":
        return ["Fe", "PGM"]
    if spectral_type in ("S", "K", "E"):
        return ["Fe"]
    if spectral_type in ("C", "D", "P"):
        return ["H₂O"]
    return []


def h2o_level(composition: dict[str, float]) -> int:
    """Map bound-water percentage to the route planner's 0-4 dot scale."""
    return max(0, min(4, round(composition.get("h2o_bound", 0) / 3.0)))


# ── transform ─────────────────────────────────────────────────────────────────

def transform(records: list[dict]) -> dict[str, list[dict]]:
    positions = compute_positions(records)

    asteroids: list[dict] = []
    tier2_rows: list[dict] = []
    tier3_rows: list[dict] = []

    for r in records:
        t1, t2, t3 = r["tier1"], r["tier2"], r["tier3"]
        aid = int(r["source_id"])
        rng = body_rng(aid)

        spec = t1["spectral_class"]
        x, y, z = positions[r["source_id"]]

        true_albedo   = t1["albedo_pv"]
        true_diam     = t1["diameter_km"]
        albedo_known  = t1.get("albedo_source") == "WISE"
        rot_known     = t2.get("rotation_source", "").startswith("LCDB")

        # ── catalog degradation ───────────────────────────────────────────────
        alb_sigma  = 0.03 if albedo_known else 0.25
        cat_albedo = round(max(0.01, true_albedo * (1 + rng.gauss(0, alb_sigma))), 3)

        diam_sigma = 0.05 if albedo_known else 0.20
        cat_diam   = round(max(0.05, true_diam * (1 + rng.gauss(0, diam_sigma))), 2)

        cat_period = round(t2["rotation_h"], 2) if rot_known else None

        magnetic     = spec == "M" or t3["composition"].get("fe_ni_metal", 0) > 25.0
        is_interloper = spec != "S"          # Flora is an S-type family
        fast_rotation = t2["rotation_h"] < 4.0

        # ── CATALOG row (asteroids) ───────────────────────────────────────────
        asteroids.append({
            "id":             aid,
            "name":           r["name"],
            "spectral_type":  spec,
            "x_pos":          x,
            "y_pos":          y,
            "z_pos":          z,
            "r_size":         round(max(1.0, math.sqrt(true_diam) * 1.5), 1),
            "albedo":         cat_albedo,
            "diameter_km":    cat_diam,
            "mass_str":       None,            # mass needs a gravity flyby
            "period_h":       cat_period,
            "has_satellite":  False,           # binary data not in pipeline
            "structure":      "?",             # structure is a Tier-2 reveal
            "h2o_level":      h2o_level(t3["composition"]),
            "eco":            eco_catalog(spec),
            "is_interloper":  is_interloper,
            "fast_rotation":  fast_rotation,
            "a_au":           t1["a_au"],
            "e":              t1["e"],
            "i_deg":          t1["inc_deg"],
            "h_mag":          t1["H_magnitude"],
            "family":         "flora",
        })

        # ── FLYBY anomalies (⚡) ───────────────────────────────────────────────
        # Only genuine surprises — not catalog imprecision. The route planner
        # already shows the catalog value next to the flyby value, so plain
        # noise needs no flag; ⚡ means "this body is structurally unusual".
        anomalies: dict[str, str] = {}
        if t1.get("albedo_class_conflict"):
            anomalies["albedo"] = "⚡ albedo ≠ typ"
        if magnetic and spec != "M":
            anomalies["magnetic"] = "⚡ kov"
        find_ids = {rf["find_id"] for rf in t3["rare_finds"]}
        if find_ids & T2_REVEALABLE_FINDS:
            anomalies["eco"] = "⚡ anomálie"

        # ── FLYBY row (asteroid_tier2) ────────────────────────────────────────
        tier2_rows.append({
            "asteroid_id":    aid,
            "albedo":         true_albedo,
            "diameter_km":    true_diam,
            "mass_str":       fmt_mass(t2["mass_kg"]),
            "density_str":    fmt_density(t2["bulk_density_gcc"]),
            "period_h":       round(t2["rotation_h"], 2),
            "has_satellite":  False,
            "structure":      STRUCT_LABEL.get(t2["structure"], "?"),
            "h2o_level":      h2o_level(t3["composition"]),
            "eco":            eco_true(t3["composition"], t3["rare_finds"]),
            "magnetic":       magnetic,
            "anomalies":      anomalies,
        })

        # ── STOP row (asteroid_tier3) ─────────────────────────────────────────
        tier3_rows.append({
            "asteroid_id":    aid,
            "minerals":       minerals_str(t3["composition"]),
            "eco":            eco_true(t3["composition"], t3["rare_finds"]),
            "h2o_level":      h2o_level(t3["composition"]),
            "special":        special_str(t3["rare_finds"]),
        })

    return {
        "asteroids":      asteroids,
        "asteroid_tier2": tier2_rows,
        "asteroid_tier3": tier3_rows,
    }


# ── Supabase push ─────────────────────────────────────────────────────────────

def push_to_supabase(payload: dict[str, list[dict]]) -> None:
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_KEY")
    if not url or not key:
        raise SystemExit(
            "Set SUPABASE_URL and SUPABASE_SERVICE_KEY environment variables "
            "before using --push (do NOT hardcode the service_role key)."
        )
    from supabase import create_client

    sb = create_client(url, key)
    # asteroids first — tier2/tier3 reference it by asteroid_id
    for table, conflict in (
        ("asteroids", "id"),
        ("asteroid_tier2", "asteroid_id"),
        ("asteroid_tier3", "asteroid_id"),
    ):
        rows = payload[table]
        log.info("Pushing %d rows → %s", len(rows), table)
        for i in range(0, len(rows), 500):
            sb.table(table).upsert(rows[i:i + 500], on_conflict=conflict).execute()
            log.info("  %s: %d/%d", table, min(i + 500, len(rows)), len(rows))
    log.info("Supabase push complete")


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser(description="flora_full.json → route-planner DB schema")
    ap.add_argument("--in", dest="inp", default=str(DEFAULT_IN), help="input JSON")
    ap.add_argument("--out", default=None, help="write transformed payload JSON here")
    ap.add_argument("--push", action="store_true", help="upsert to Supabase (env keys)")
    args = ap.parse_args()

    records = json.loads(Path(args.inp).read_text())
    log.info("Loaded %d asteroid records from %s", len(records), args.inp)

    payload = transform(records)
    log.info("Transformed: %d asteroids / %d tier2 / %d tier3",
             len(payload["asteroids"]), len(payload["asteroid_tier2"]),
             len(payload["asteroid_tier3"]))

    if args.out:
        Path(args.out).write_text(json.dumps(payload, ensure_ascii=False, indent=2))
        log.info("Saved payload → %s", args.out)

    if args.push:
        push_to_supabase(payload)

    if not args.out and not args.push:
        log.warning("Nothing to do — pass --out and/or --push")


if __name__ == "__main__":
    main()
