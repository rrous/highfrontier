-- ============================================================================
-- scene_snapshots — daily cached physical-distance scene for each base.
-- Run once in the Supabase SQL editor. Idempotent.
-- ============================================================================
--
-- Per `db_design.md` §11.6: a daily offline job propagates orbital elements
-- to today's date, computes physical heliocentric positions, and stores the
-- top 100 bodies nearest to each active base as one JSONB row keyed by
-- (base_id, snapshot_date).
--
-- The stored array preserves the order computed by the job — already sorted
-- by `d_km` ascending — so the client can pick the first N without resorting.
--
-- JSONB array element shape (one object per asteroid):
--   {
--     "id":            <bigint>,
--     "name":          <text>,
--     "spectral_type": <text>,
--     "x_km":          <numeric>,   -- heliocentric position, ecliptic J2000 (km)
--     "y_km":          <numeric>,
--     "z_km":          <numeric>,
--     "vx_kms":        <numeric>,   -- heliocentric velocity (km/s)
--     "vy_kms":        <numeric>,
--     "vz_kms":        <numeric>,
--     "dx_km":         <numeric>,   -- offset from base
--     "dy_km":         <numeric>,
--     "dz_km":         <numeric>,
--     "d_km":          <numeric>,   -- |r_target - r_base|  (km)
--     "dvx_kms":       <numeric>,   -- v_target - v_base
--     "dvy_kms":       <numeric>,
--     "dvz_kms":       <numeric>
--   }
--
-- The base's own asteroid is included with d_km = 0 so the client can render
-- it without a separate lookup.

CREATE TABLE IF NOT EXISTS scene_snapshots (
    base_id        bigint        NOT NULL REFERENCES bases(id) ON DELETE CASCADE,
    snapshot_date  date          NOT NULL,
    asteroid_data  jsonb         NOT NULL,
    computed_at    timestamptz   NOT NULL DEFAULT now(),
    PRIMARY KEY (base_id, snapshot_date)
);

CREATE INDEX IF NOT EXISTS scene_snapshots_date_idx
    ON scene_snapshots (snapshot_date);
