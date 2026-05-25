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
--   a         — semi-major axis            (already present as `a_au`)
--   e         — eccentricity               (already present as `e`)
--   i         — inclination                (already present as `i_deg`)
--   Ω (node)  — longitude of ascending node  → adds `node_deg`
--   ω (peri)  — argument of perihelion       → adds `peri_deg`
--   M₀ (ma)   — mean anomaly at epoch        → adds `ma_deg`
--   epoch     — JD at which M₀ is defined    → adds `epoch_jd`
--
-- Source: JPL SBDB osculating elements per body. ETL change is tracked
-- separately — until it lands, these columns will be NULL and the daily
-- snapshot job will skip such rows.

ALTER TABLE asteroids
    ADD COLUMN IF NOT EXISTS node_deg  numeric,
    ADD COLUMN IF NOT EXISTS peri_deg  numeric,
    ADD COLUMN IF NOT EXISTS ma_deg    numeric,
    ADD COLUMN IF NOT EXISTS epoch_jd  numeric;

COMMENT ON COLUMN asteroids.node_deg IS
    'Longitude of ascending node Ω (degrees, equinox J2000, ecliptic frame).';
COMMENT ON COLUMN asteroids.peri_deg IS
    'Argument of perihelion ω (degrees).';
COMMENT ON COLUMN asteroids.ma_deg IS
    'Mean anomaly M₀ at epoch (degrees).';
COMMENT ON COLUMN asteroids.epoch_jd IS
    'Epoch as Julian Date (TDB) at which M₀ is defined.';
