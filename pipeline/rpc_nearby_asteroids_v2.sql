-- ============================================================================
-- nearby_asteroids — snapshot-backed scene query (db_design.md §9.1).
-- Run once in the Supabase SQL editor. Idempotent (CREATE OR REPLACE).
-- ============================================================================
--
-- This is the snapshot-backed overload of `nearby_asteroids` introduced by
-- the design pivot from velocity-space to physical-distance scenes.
-- Postgres picks it (vs. the legacy `nearby_asteroids(numeric, numeric, …)`
-- in `rpc_nearby_asteroids.sql`) by argument types — both can coexist while
-- the client migrates.
--
-- Signature matches `db_design.md` §9.1:
--   nearby_asteroids(base_id, date, radius_km, max_n)
--
-- Reads `scene_snapshots` (built by `pipeline/snapshot_daily.py`),
-- filters items with d_km ≤ radius_km, sorts ascending by d_km, caps at 100.

CREATE OR REPLACE FUNCTION nearby_asteroids(
    p_base_id    bigint,
    p_date       date    DEFAULT CURRENT_DATE,
    p_radius_km  numeric DEFAULT 50000000,
    p_max_n      integer DEFAULT 100
)
RETURNS jsonb
LANGUAGE sql
STABLE
AS $$
    WITH items AS (
        SELECT item
        FROM scene_snapshots s,
             jsonb_array_elements(s.asteroid_data) AS item
        WHERE s.base_id = p_base_id
          AND s.snapshot_date = p_date
          AND (item->>'d_km')::numeric <= p_radius_km
        ORDER BY (item->>'d_km')::numeric ASC
        LIMIT LEAST(GREATEST(p_max_n, 0), 100)
    )
    SELECT COALESCE(jsonb_agg(item), '[]'::jsonb) FROM items;
$$;
