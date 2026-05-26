"""
Fetch osculating orbital elements from JPL SBDB for every asteroid in the
`asteroids` table and upsert them into the osculating-element columns.

This is the ETL step that prepares the inputs for Kepler propagation in
`pipeline/snapshot_daily.py` (db_design.md §9.1, §11.6). It is a one-shot
backfill — re-run on demand when JPL refreshes the osculating epoch.

Uses the same SBDB query API and spkid pagination as
`fetch_flora.py::fetch_sbdb_metadata`. We do not reuse its cache: the SBDB
metadata cache stores name/H/spectral/rotation only.

Usage:
    SUPABASE_URL=… SUPABASE_SERVICE_KEY=… python fetch_osculating_elements.py
    # optional: --limit 200       (debug: stop after N matched rows)
    # optional: --no-cache        (ignore on-disk cache, re-query SBDB)
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import time
from pathlib import Path

import requests

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)

# ── constants ────────────────────────────────────────────────────────────────

SBDB_API = "https://ssd-api.jpl.nasa.gov/sbdb_query.api"
SPKID_BASE = 20_000_000  # spkid = SPKID_BASE + asteroid_number (numbered)

CACHE_DIR = Path(__file__).parent / ".data_cache"
CACHE_DIR.mkdir(exist_ok=True)
CACHE_FILE = CACHE_DIR / "sbdb_osculating_elements.json"

UPSERT_PAGE = 500  # rows per Supabase upsert batch


# ── SBDB query ───────────────────────────────────────────────────────────────

_FULL_NAME_NUM = re.compile(r"^\s*\(?\s*(\d+)\s*\)?")


def _number_from_full_name(s: str | None) -> int | None:
    """Extract leading asteroid number from a `full_name` like '(8) Flora'."""
    if not s:
        return None
    m = _FULL_NAME_NUM.match(s)
    return int(m.group(1)) if m else None


def fetch_sbdb_elements(numbers: set[int], use_cache: bool = True) -> dict[int, dict]:
    """
    Fetch osculating elements for the given asteroid numbers from SBDB.

    Returns dict number → {a, e, i, om, w, ma, epoch} (all floats; degrees and JD).
    Rows where any required field is missing are dropped.
    """
    if use_cache and CACHE_FILE.exists():
        log.info("SBDB osculating: using cache (%s)", CACHE_FILE)
        cached = json.loads(CACHE_FILE.read_text())
        return {int(k): v for k, v in cached.items() if int(k) in numbers}

    log.info("Fetching SBDB osculating elements for %d numbered asteroids …",
             len(numbers))

    max_num = max(numbers)
    step    = 50_000
    out: dict[int, dict] = {}

    for lo in range(0, max_num + step, step):
        hi = lo + step
        params = {
            "fields":   "spkid,full_name,a,e,i,om,w,ma,epoch",
            "sb-class": "MBA",
            "sb-cdata": json.dumps({
                "AND": [
                    f"spkid|GE|{SPKID_BASE + lo}",
                    f"spkid|LT|{SPKID_BASE + hi}",
                ]
            }),
            "limit": "50000",
        }
        for attempt in range(3):
            try:
                r = requests.get(SBDB_API, params=params, timeout=120)
                r.raise_for_status()
                break
            except requests.RequestException as exc:
                wait = 4 ** attempt
                log.warning("  spkid %d-%d attempt %d failed: %s (retry in %ds)",
                            lo, hi, attempt + 1, exc, wait)
                time.sleep(wait)
        else:
            log.warning("  skipping spkid range %d-%d after 3 failures", lo, hi)
            continue

        batch = (r.json() or {}).get("data") or []
        kept = 0
        for row in batch:
            spkid, full_name, a, e, i, om, w, ma, epoch = row
            num = _number_from_full_name(full_name)
            if num is None or num not in numbers:
                continue
            try:
                out[num] = {
                    "a":     float(a),
                    "e":     float(e),
                    "i":     float(i),
                    "om":    float(om),
                    "w":     float(w),
                    "ma":    float(ma),
                    "epoch": float(epoch),
                }
                kept += 1
            except (TypeError, ValueError):
                continue
        log.info("  spkid %d–%d: %d batch rows, %d matched (running %d)",
                 lo, hi, len(batch), kept, len(out))

    CACHE_FILE.write_text(json.dumps({str(k): v for k, v in out.items()},
                                     ensure_ascii=False))
    log.info("SBDB osculating: %d / %d asteroids matched, cached → %s",
             len(out), len(numbers), CACHE_FILE)
    return out


# ── Supabase IO ──────────────────────────────────────────────────────────────

def make_client():
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_KEY")
    if not url or not key:
        raise SystemExit(
            "Set SUPABASE_URL and SUPABASE_SERVICE_KEY before running "
            "fetch_osculating_elements.py."
        )
    from supabase import create_client
    return create_client(url, key)


def load_asteroid_numbers(sb) -> set[int]:
    """Return the set of `asteroids.id` values (numbered asteroid catalog numbers)."""
    ids: set[int] = set()
    page = 1000
    start = 0
    while True:
        r = (sb.table("asteroids")
             .select("id")
             .range(start, start + page - 1)
             .execute())
        batch = r.data or []
        ids.update(int(row["id"]) for row in batch)
        if len(batch) < page:
            break
        start += page
    return ids


def upsert_elements(sb, elements: dict[int, dict]) -> None:
    """Upsert the fetched osculating elements into `asteroids`."""
    rows = [
        {
            "id":        num,
            "a_au_osc":  vals["a"],
            "e_osc":     vals["e"],
            "i_deg_osc": vals["i"],
            "node_deg":  vals["om"],
            "peri_deg":  vals["w"],
            "ma_deg":    vals["ma"],
            "epoch_jd":  vals["epoch"],
        }
        for num, vals in elements.items()
    ]
    log.info("Upserting osculating elements for %d asteroids …", len(rows))
    for i in range(0, len(rows), UPSERT_PAGE):
        sb.table("asteroids").upsert(rows[i:i + UPSERT_PAGE], on_conflict="id").execute()
        log.info("  %d/%d", min(i + UPSERT_PAGE, len(rows)), len(rows))


# ── CLI ──────────────────────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser(description="Fetch SBDB osculating elements → asteroids.")
    ap.add_argument("--limit", type=int, default=None, help="debug: stop after N rows")
    ap.add_argument("--no-cache", action="store_true", help="ignore on-disk SBDB cache")
    args = ap.parse_args()

    sb = make_client()
    numbers = load_asteroid_numbers(sb)
    if not numbers:
        raise SystemExit("`asteroids` table is empty — load the catalog first.")
    log.info("Asteroids in DB: %d", len(numbers))

    elements = fetch_sbdb_elements(numbers, use_cache=not args.no_cache)
    if args.limit:
        elements = dict(list(elements.items())[: args.limit])

    if not elements:
        raise SystemExit("No osculating elements fetched — nothing to upsert.")

    upsert_elements(sb, elements)
    log.info("Done. Run pipeline/snapshot_daily.py next to materialize the scene.")


if __name__ == "__main__":
    main()
