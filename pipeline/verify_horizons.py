"""
Verify asteroid positions and Δv against JPL Horizons.

Cross-checks the heliocentric state vectors used by the route planner
(snapshot_daily.py propagates osculating elements with a Kepler solver) against
the authoritative JPL Horizons ephemeris for the same epoch.

For each target body we report:
    - heliocentric position (x, y, z) [AU and km], ecliptic J2000, Sun-centred
    - heliocentric velocity (vx, vy, vz) [km/s]
    - distance to Flora (#8)            [km, AU]
    - Δv to Flora = |v_target - v_Flora| [km/s, m/s]

"Δv" here matches the project definition (app/game/physics/flight.ts:deltaV):
the magnitude of the heliocentric velocity-vector difference between two bodies
— i.e. the velocity-space distance, NOT a transfer-orbit burn budget.

Usage:
    python verify_horizons.py                       # today (UTC)
    python verify_horizons.py --date 2026-06-04
    python verify_horizons.py --out ../docs/horizons_verification.md
"""

from __future__ import annotations

import argparse
import math
import re
import sys
import time
from datetime import datetime, timezone

import requests

HORIZONS_API = "https://ssd.jpl.nasa.gov/api/horizons.api"
AU_KM = 1.495978707e8  # 1 AU in km (IAU 2012)

# Reference base body and the targets to verify.
# In Horizons a trailing ";" marks a small-body record number — WITHOUT it,
# COMMAND='8' resolves to the Neptune barycentre, not asteroid 8 Flora.
FLORA = ("8", "Flora")
TARGETS = [
    ("2112", "Ulyanov"),
    ("17102", "Begzhigitova"),
    ("8297", "Gerardfaure"),
    ("58580", "Elenacuoghi"),
]


def fetch_state(record: str, epoch_iso: str) -> dict:
    """
    Query Horizons VECTORS for one small body and return its heliocentric,
    ecliptic-J2000 state vector (km, km/s) at `epoch_iso` (UTC, 00:00).

    VEC_TABLE='2'   -> position + velocity
    CENTER='500@10' -> Sun body centre (heliocentric)
    REF_PLANE='ECLIPTIC', REF_SYSTEM='J2000' -> match snapshot_daily.py frame
    OUT_UNITS='KM-S'
    """
    params = {
        "format": "text",
        "COMMAND": f"'{record};'",
        "OBJ_DATA": "NO",
        "MAKE_EPHEM": "YES",
        "EPHEM_TYPE": "VECTORS",
        "CENTER": "'500@10'",
        "REF_PLANE": "ECLIPTIC",
        "REF_SYSTEM": "J2000",
        "VEC_TABLE": "2",
        "OUT_UNITS": "KM-S",
        "TLIST": f"'{epoch_iso}'",
        "TIME_TYPE": "UT",
    }
    last_err: Exception | None = None
    for attempt in range(4):
        try:
            r = requests.get(HORIZONS_API, params=params, timeout=60)
            r.raise_for_status()
            return parse_vectors(record, r.text)
        except Exception as e:  # noqa: BLE001 — retry on any network/parse hiccup
            last_err = e
            time.sleep(2 ** attempt)
    raise RuntimeError(f"Horizons query failed for {record}: {last_err}")


def parse_vectors(record: str, text: str) -> dict:
    """Extract X/Y/Z/VX/VY/VZ and the resolved target name from a VECTORS reply."""
    soe = text.find("$$SOE")
    eoe = text.find("$$EOE")
    if soe == -1 or eoe == -1:
        raise RuntimeError(
            f"No ephemeris block for {record}. Horizons said:\n{text[:600]}"
        )
    block = text[soe:eoe]

    def grab(key: str) -> float:
        m = re.search(rf"{key}\s*=\s*([-+0-9.Ee]+)", block)
        if not m:
            raise RuntimeError(f"Missing {key} for {record} in:\n{block}")
        return float(m.group(1))

    # "Target body name: 8 Flora (A847 UB)  {source: ...}"
    name_m = re.search(r"Target body name:\s*(.+?)\s*\{", text)
    resolved = name_m.group(1).strip() if name_m else record

    return {
        "record": record,
        "resolved": resolved,
        "x": grab("X"), "y": grab("Y"), "z": grab("Z"),
        "vx": grab("VX"), "vy": grab("VY"), "vz": grab("VZ"),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Verify positions/Δv vs JPL Horizons.")
    ap.add_argument("--date", default=None,
                    help="epoch YYYY-MM-DD (UTC 00:00); default: today UTC")
    ap.add_argument("--out", default=None,
                    help="write Markdown report to this path (default: stdout only)")
    args = ap.parse_args()

    epoch_date = (datetime.strptime(args.date, "%Y-%m-%d").date()
                  if args.date else datetime.now(timezone.utc).date())
    epoch_iso = f"{epoch_date.isoformat()} 00:00"
    print(f"Epoch: {epoch_iso} UT  (heliocentric, ecliptic J2000)\n", file=sys.stderr)

    flora = fetch_state(FLORA[0], epoch_iso)
    print(f"  fetched {FLORA[1]}: {flora['resolved']}", file=sys.stderr)

    rows = []
    for rec, label in TARGETS:
        s = fetch_state(rec, epoch_iso)
        print(f"  fetched {label}: {s['resolved']}", file=sys.stderr)

        dx, dy, dz = s["x"] - flora["x"], s["y"] - flora["y"], s["z"] - flora["z"]
        dist_km = math.sqrt(dx * dx + dy * dy + dz * dz)

        dvx, dvy, dvz = s["vx"] - flora["vx"], s["vy"] - flora["vy"], s["vz"] - flora["vz"]
        dv_kms = math.sqrt(dvx * dvx + dvy * dvy + dvz * dvz)

        rows.append({
            "label": label, **s,
            "dist_km": dist_km, "dist_au": dist_km / AU_KM,
            "dvx": dvx, "dvy": dvy, "dvz": dvz, "dv_kms": dv_kms,
        })

    md = render_md(epoch_iso, flora, rows)
    print("\n" + md)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(md)
        print(f"\nWrote {args.out}", file=sys.stderr)


def render_md(epoch_iso: str, flora: dict, rows: list[dict]) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    L: list[str] = []
    L.append("# Ověření poloh a Δv proti JPL Horizons")
    L.append("")
    L.append(f"- **Epocha:** {epoch_iso} UT")
    L.append(f"- **Vygenerováno:** {now}")
    L.append("- **Zdroj:** JPL Horizons API (`EPHEM_TYPE=VECTORS`)")
    L.append("- **Rámec:** heliocentrický (Slunce, `500@10`), ekliptika J2000, jednotky km / km·s⁻¹")
    L.append(f"- **Referenční těleso:** {flora['resolved']} (rec #{flora['record']})")
    L.append("")
    L.append("> **Δv** = velikost rozdílu heliocentrických rychlostních vektorů oproti "
             "Floře (velocity-space distance), shodně s definicí `deltaV()` v "
             "`app/game/physics/flight.ts`. Nejde o rozpočet na přeletový manévr.")
    L.append("")

    # Reference state
    L.append("## Referenční stav — Flora")
    L.append("")
    L.append("| veličina | X | Y | Z |")
    L.append("|---|---:|---:|---:|")
    L.append(f"| poloha [AU] | {flora['x']/AU_KM:.6f} | {flora['y']/AU_KM:.6f} | {flora['z']/AU_KM:.6f} |")
    L.append(f"| poloha [km] | {flora['x']:.3e} | {flora['y']:.3e} | {flora['z']:.3e} |")
    L.append(f"| rychlost [km/s] | {flora['vx']:.6f} | {flora['vy']:.6f} | {flora['vz']:.6f} |")
    L.append("")

    # Summary
    L.append("## Souhrn — cílová tělesa vs. Flora")
    L.append("")
    L.append("| těleso | rec # | Horizons rozlišil | vzdálenost [AU] | vzdálenost [km] | Δv [km/s] | Δv [m/s] |")
    L.append("|---|---|---|---:|---:|---:|---:|")
    for r in rows:
        L.append(
            f"| {r['label']} | {r['record']} | {r['resolved']} | "
            f"{r['dist_au']:.6f} | {r['dist_km']:.3e} | "
            f"{r['dv_kms']:.6f} | {r['dv_kms']*1000:.1f} |"
        )
    L.append("")

    # Δv broken into components
    L.append("## Rozklad Δv po složkách (těleso − Flora)")
    L.append("")
    L.append("> Konvence `těleso − Flora` shodná s polem `dv*_kms` ve `snapshot_daily.py` "
             "(`v_target − v_base`). Velikost `|Δv|` je na znaménku nezávislá.")
    L.append("")
    L.append("| těleso | ΔVX [m/s] | ΔVY [m/s] | ΔVZ [m/s] | \\|Δv\\| [km/s] | \\|Δv\\| [m/s] |")
    L.append("|---|---:|---:|---:|---:|---:|")
    for r in rows:
        L.append(
            f"| {r['label']} | {r['dvx']*1000:+.1f} | {r['dvy']*1000:+.1f} | "
            f"{r['dvz']*1000:+.1f} | {r['dv_kms']:.6f} | {r['dv_kms']*1000:.1f} |"
        )
    L.append("")

    # Per-body state vectors
    L.append("## Stavové vektory cílových těles")
    L.append("")
    L.append("| těleso | X [AU] | Y [AU] | Z [AU] | VX [km/s] | VY [km/s] | VZ [km/s] |")
    L.append("|---|---:|---:|---:|---:|---:|---:|")
    for r in rows:
        L.append(
            f"| {r['label']} | {r['x']/AU_KM:.6f} | {r['y']/AU_KM:.6f} | {r['z']/AU_KM:.6f} | "
            f"{r['vx']:.6f} | {r['vy']:.6f} | {r['vz']:.6f} |"
        )
    L.append("")
    return "\n".join(L)


if __name__ == "__main__":
    main()
