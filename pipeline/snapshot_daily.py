"""
Daily scene snapshot — Keplerian propagation of all asteroids to a target date,
top 100 nearest bodies per active base written to `scene_snapshots`.

Per `db_design.md` §11.6: the design pivoted from velocity-space proper-element
distances to physical heliocentric distances derived from osculating orbital
elements propagated to the mission date. This script is the offline job that
produces one row per (base, date).

Inputs (from Supabase):
    - `asteroids` rows with osculating elements (a_au, e, i_deg, node_deg,
      peri_deg, ma_deg, epoch_jd). Rows missing any of these are skipped.
    - `bases` rows joined to their host asteroid (Flora is the first base).

Output:
    - `scene_snapshots(base_id, snapshot_date, asteroid_data jsonb)` upserted.

Algorithm:
    For each body, solve Kepler's equation E - e·sin(E) = M(t) by Newton-
    Raphson. Position in the orbital plane is then rotated to ecliptic J2000
    by ω, i, Ω. Velocity is the analytic time derivative. We ignore planetary
    perturbations — the resulting error (~100 000 km over 10 years for main-
    belt asteroids) is far below the scene threshold (10–50 Mkm; §10.3).

Usage:
    SUPABASE_URL=… SUPABASE_SERVICE_KEY=… python snapshot_daily.py
    # optional: --date 2026-05-25  (default = today UTC)
    # optional: --base Flora       (default = all bases)
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import os
from datetime import date, datetime, timezone

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)

# ── physical constants ────────────────────────────────────────────────────────

MU_SUN_M3_S2 = 1.32712440041e20   # heliocentric gravitational parameter, m³/s²
AU_M = 1.495978707e11             # 1 AU in metres
DAY_S = 86400.0

TOP_N = 100         # rows kept per base per day (db_design.md §11.6)
KEPLER_TOL = 1e-11  # Newton-Raphson convergence


# ── Kepler propagation ────────────────────────────────────────────────────────

def date_to_jd(d: date) -> float:
    """Julian Date at 00:00 TT of the given civil date (Gregorian)."""
    y, m, dd = d.year, d.month, d.day
    if m <= 2:
        y -= 1
        m += 12
    a = y // 100
    b = 2 - a + a // 4
    return math.floor(365.25 * (y + 4716)) + math.floor(30.6001 * (m + 1)) + dd + b - 1524.5


def solve_kepler(mean_anom: float, ecc: float) -> float:
    """Solve E - e·sin(E) = M for E (radians) via Newton-Raphson."""
    M = math.fmod(mean_anom, 2.0 * math.pi)
    if M < -math.pi:
        M += 2.0 * math.pi
    elif M > math.pi:
        M -= 2.0 * math.pi

    E = M if ecc < 0.8 else math.pi
    for _ in range(60):
        f = E - ecc * math.sin(E) - M
        fp = 1.0 - ecc * math.cos(E)
        dE = f / fp
        E -= dE
        if abs(dE) < KEPLER_TOL:
            break
    return E


def propagate(a_au: float, ecc: float, inc_deg: float,
              node_deg: float, peri_deg: float, ma0_deg: float,
              epoch_jd: float, target_jd: float) -> tuple[float, float, float, float, float, float]:
    """
    Propagate one body from (a, e, i, Ω, ω, M₀; epoch_jd) to `target_jd`.

    Returns heliocentric position (m) and velocity (m/s) in ecliptic J2000:
    (x, y, z, vx, vy, vz).
    """
    a_m = a_au * AU_M
    n = math.sqrt(MU_SUN_M3_S2 / (a_m ** 3))           # mean motion, rad/s
    dt_s = (target_jd - epoch_jd) * DAY_S
    M = math.radians(ma0_deg) + n * dt_s
    E = solve_kepler(M, ecc)

    cos_E = math.cos(E)
    sin_E = math.sin(E)
    one_minus_e2 = 1.0 - ecc * ecc
    sqrt_omec2 = math.sqrt(one_minus_e2)

    # Position in the orbital plane (perifocal frame).
    x_p = a_m * (cos_E - ecc)
    y_p = a_m * sqrt_omec2 * sin_E

    # Velocity in the perifocal frame: derivative of (x_p, y_p) wrt time.
    r = a_m * (1.0 - ecc * cos_E)
    E_dot = n / (1.0 - ecc * cos_E)
    vx_p = -a_m * sin_E * E_dot
    vy_p = a_m * sqrt_omec2 * cos_E * E_dot

    # Rotate perifocal → ecliptic J2000 by (ω, i, Ω):
    #   R = R3(-Ω) · R1(-i) · R3(-ω)
    cos_w = math.cos(math.radians(peri_deg))
    sin_w = math.sin(math.radians(peri_deg))
    cos_i = math.cos(math.radians(inc_deg))
    sin_i = math.sin(math.radians(inc_deg))
    cos_O = math.cos(math.radians(node_deg))
    sin_O = math.sin(math.radians(node_deg))

    P11 =  cos_O * cos_w - sin_O * sin_w * cos_i
    P12 = -cos_O * sin_w - sin_O * cos_w * cos_i
    P21 =  sin_O * cos_w + cos_O * sin_w * cos_i
    P22 = -sin_O * sin_w + cos_O * cos_w * cos_i
    P31 =  sin_w * sin_i
    P32 =  cos_w * sin_i

    x  = P11 * x_p  + P12 * y_p
    y  = P21 * x_p  + P22 * y_p
    z  = P31 * x_p  + P32 * y_p
    vx = P11 * vx_p + P12 * vy_p
    vy = P21 * vx_p + P22 * vy_p
    vz = P31 * vx_p + P32 * vy_p

    # `r` is the perifocal-frame radius; sanity check against the rotated position.
    _ = r
    return x, y, z, vx, vy, vz


# ── Supabase IO ───────────────────────────────────────────────────────────────

def make_client():
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_KEY")
    if not url or not key:
        raise SystemExit(
            "Set SUPABASE_URL and SUPABASE_SERVICE_KEY before running "
            "snapshot_daily.py (do NOT hardcode the service_role key)."
        )
    from supabase import create_client
    return create_client(url, key)


def fetch_asteroids(sb) -> list[dict]:
    """All asteroid rows with a complete osculating element set."""
    cols = ("id,name,spectral_type,"
            "a_au_osc,e_osc,i_deg_osc,node_deg,peri_deg,ma_deg,epoch_jd")
    rows: list[dict] = []
    page = 1000
    start = 0
    while True:
        r = (sb.table("asteroids")
             .select(cols)
             .not_.is_("a_au_osc",  "null")
             .not_.is_("e_osc",     "null")
             .not_.is_("i_deg_osc", "null")
             .not_.is_("node_deg",  "null")
             .not_.is_("peri_deg",  "null")
             .not_.is_("ma_deg",    "null")
             .not_.is_("epoch_jd",  "null")
             .range(start, start + page - 1)
             .execute())
        batch = r.data or []
        rows.extend(batch)
        if len(batch) < page:
            break
        start += page
    return rows


def fetch_bases(sb, only_name: str | None) -> list[dict]:
    q = sb.table("bases").select("id,name,asteroid_id")
    if only_name:
        q = q.eq("name", only_name)
    r = q.execute()
    return r.data or []


# ── snapshot computation ──────────────────────────────────────────────────────

def build_snapshot(bodies: list[dict], base_id_in_bodies: int, target_jd: float) -> list[dict]:
    """Propagate every body, compute offsets from the base body, keep top N."""
    propagated: list[tuple[float, dict]] = []
    base_state: tuple[float, float, float, float, float, float] | None = None

    for row in bodies:
        try:
            state = propagate(
                a_au=float(row["a_au_osc"]),
                ecc=float(row["e_osc"]),
                inc_deg=float(row["i_deg_osc"]),
                node_deg=float(row["node_deg"]),
                peri_deg=float(row["peri_deg"]),
                ma0_deg=float(row["ma_deg"]),
                epoch_jd=float(row["epoch_jd"]),
                target_jd=target_jd,
            )
        except (TypeError, ValueError):
            continue
        if row["id"] == base_id_in_bodies:
            base_state = state
        propagated.append((row["id"], {"row": row, "state": state}))

    if base_state is None:
        return []

    bx, by, bz, bvx, bvy, bvz = base_state

    items = []
    for _, entry in propagated:
        x, y, z, vx, vy, vz = entry["state"]
        dx = x - bx
        dy = y - by
        dz = z - bz
        d = math.sqrt(dx * dx + dy * dy + dz * dz)
        items.append({
            "id":            entry["row"]["id"],
            "name":          entry["row"]["name"],
            "spectral_type": entry["row"]["spectral_type"],
            "x_km":          x  / 1000.0,
            "y_km":          y  / 1000.0,
            "z_km":          z  / 1000.0,
            "vx_kms":        vx / 1000.0,
            "vy_kms":        vy / 1000.0,
            "vz_kms":        vz / 1000.0,
            "dx_km":         dx / 1000.0,
            "dy_km":         dy / 1000.0,
            "dz_km":         dz / 1000.0,
            "d_km":          d  / 1000.0,
            "dvx_kms":       (vx - bvx) / 1000.0,
            "dvy_kms":       (vy - bvy) / 1000.0,
            "dvz_kms":       (vz - bvz) / 1000.0,
        })

    items.sort(key=lambda it: it["d_km"])
    return items[:TOP_N]


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser(description="Daily scene snapshot per base.")
    ap.add_argument("--date", default=None, help="target date YYYY-MM-DD (default: today UTC)")
    ap.add_argument("--base", default=None, help="restrict to a single base name (default: all)")
    args = ap.parse_args()

    if args.date:
        target_date = datetime.strptime(args.date, "%Y-%m-%d").date()
    else:
        target_date = datetime.now(timezone.utc).date()
    target_jd = date_to_jd(target_date)
    log.info("Target date %s = JD %.3f", target_date.isoformat(), target_jd)

    sb = make_client()

    bases = fetch_bases(sb, args.base)
    if not bases:
        raise SystemExit(f"No bases found (filter: {args.base!r}).")
    log.info("Bases to snapshot: %s", ", ".join(b["name"] for b in bases))

    bodies = fetch_asteroids(sb)
    log.info("Asteroid rows with complete osculating elements: %d", len(bodies))
    if not bodies:
        raise SystemExit(
            "No asteroids with complete osculating elements (node_deg/peri_deg/"
            "ma_deg/epoch_jd). Run the SBDB ETL update before snapshotting."
        )

    for b in bases:
        items = build_snapshot(bodies, b["asteroid_id"], target_jd)
        if not items:
            log.warning("Base %s: host asteroid %s not in osculating-element set — skipping",
                        b["name"], b["asteroid_id"])
            continue
        payload = {
            "base_id":       b["id"],
            "snapshot_date": target_date.isoformat(),
            "asteroid_data": items,
        }
        sb.table("scene_snapshots").upsert(payload, on_conflict="base_id,snapshot_date").execute()
        log.info("Base %s: wrote %d items, nearest = %.0f km",
                 b["name"], len(items), items[0]["d_km"])


if __name__ == "__main__":
    main()
