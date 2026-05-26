-- ============================================================================
-- Osculating orbital elements — extend `asteroids` with the columns needed
-- for Keplerian propagation to an arbitrary date.
-- Run once in the Supabase SQL editor. Idempotent.
-- ============================================================================
--
-- Per `db_design.md` §9.1 the design pivoted from velocity-space (proper-
-- element) positions to physical heliocentric positions derived by Kepler
-- propagation. To propagate a body we need a full osculating element set
-- at a known epoch:
--
--   a         — semi-major axis            → adds `a_au_osc`
--   e         — eccentricity               → adds `e_osc`
--   i         — inclination                → adds `i_deg_osc`
--   Ω (node)  — longitude of ascending node  → adds `node_deg`
--   ω (peri)  — argument of perihelion       → adds `peri_deg`
--   M₀ (ma)   — mean anomaly at epoch        → adds `ma_deg`
--   epoch     — JD at which M₀ is defined    → adds `epoch_jd`
--
-- NB: the existing `a_au` / `e` / `i_deg` columns hold *proper* elements
-- from Nesvorný 2015 (averaged over ~1 Myr), not osculating ones — so we
-- can't reuse them for Kepler propagation. Proper elements stay where they
-- are (used as Zappalà-metric route attribute, db_design.md §10.3); the
-- new `_osc` columns carry the instantaneous values from JPL SBDB.
--
-- Source: JPL SBDB osculating elements per body. The fetch is run by
-- `pipeline/fetch_osculating_elements.py`; until it runs, these columns
-- are NULL and `pipeline/snapshot_daily.py` skips such rows.

ALTER TABLE asteroids
    ADD COLUMN IF NOT EXISTS a_au_osc  numeric,
    ADD COLUMN IF NOT EXISTS e_osc     numeric,
    ADD COLUMN IF NOT EXISTS i_deg_osc numeric,
    ADD COLUMN IF NOT EXISTS node_deg  numeric,
    ADD COLUMN IF NOT EXISTS peri_deg  numeric,
    ADD COLUMN IF NOT EXISTS ma_deg    numeric,
    ADD COLUMN IF NOT EXISTS epoch_jd  numeric;

COMMENT ON COLUMN asteroids.a_au_osc IS
    'Osculating semi-major axis (AU). Distinct from `a_au` which is the proper element.';
COMMENT ON COLUMN asteroids.e_osc IS
    'Osculating eccentricity. Distinct from `e` which is the proper element.';
COMMENT ON COLUMN asteroids.i_deg_osc IS
    'Osculating inclination (degrees, ecliptic J2000). Distinct from `i_deg` (proper).';
COMMENT ON COLUMN asteroids.node_deg IS
    'Longitude of ascending node Ω (degrees, equinox J2000, ecliptic frame).';
COMMENT ON COLUMN asteroids.peri_deg IS
    'Argument of perihelion ω (degrees).';
COMMENT ON COLUMN asteroids.ma_deg IS
    'Mean anomaly M₀ at epoch (degrees).';
COMMENT ON COLUMN asteroids.epoch_jd IS
    'Epoch as Julian Date (TDB) at which M₀ is defined.';
