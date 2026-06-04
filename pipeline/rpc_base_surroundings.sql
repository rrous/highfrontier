-- ============================================================================
-- base_surroundings — proximity query keyed by a named base.
-- Run once in the Supabase SQL editor. Idempotent (CREATE OR REPLACE).
-- ============================================================================
--
-- Returns asteroids in the surroundings of the given base, ordered by 3D
-- distance (delta-v) in proper-element velocity space. The base's own
-- asteroid is included in the result (it sits at delta_v = 0) so the client
-- can render it without a separate lookup.
--
-- Compared to `nearby_asteroids`, this RPC:
--   - takes a base name instead of raw x/y/z coordinates,
--   - returns relative offsets dx/dy/dz and delta_v ready to use,
--   - is the entry point for the "surroundings of a base" interface
--     described in `db_design.md` §11.1 / §11.3.
--
-- Hard-capped at 100 rows regardless of `max_n`.

CREATE OR REPLACE FUNCTION base_surroundings(
    base_name text,
    radius    numeric DEFAULT 100000,
    max_n     integer DEFAULT 100
)
RETURNS TABLE (
    id            bigint,
    name          text,
    spectral_type text,
    x_pos         numeric,
    y_pos         numeric,
    z_pos         numeric,
    r_size        numeric,
    albedo        numeric,
    diameter_km   numeric,
    mass_str      text,
    period_h      numeric,
    has_satellite boolean,
    structure     text,
    h2o_level     integer,
    eco           text[],
    is_interloper boolean,
    fast_rotation boolean,
    dx            numeric,
    dy            numeric,
    dz            numeric,
    delta_v       numeric
)
LANGUAGE sql
STABLE
AS $$
    WITH b AS (
        SELECT a.x_pos AS bx,
               a.y_pos AS by,
               COALESCE(a.z_pos, 0) AS bz
        FROM bases bs
        JOIN asteroids a ON a.id = bs.asteroid_id
        WHERE bs.name = base_name
    )
    SELECT
        a.id,
        a.name,
        a.spectral_type,
        a.x_pos,
        a.y_pos,
        a.z_pos,
        a.r_size,
        a.albedo,
        a.diameter_km,
        a.mass_str,
        a.period_h,
        a.has_satellite,
        a.structure,
        a.h2o_level,
        a.eco,
        a.is_interloper,
        a.fast_rotation,
        a.x_pos - b.bx                       AS dx,
        a.y_pos - b.by                       AS dy,
        COALESCE(a.z_pos, 0) - b.bz          AS dz,
        sqrt( (a.x_pos - b.bx) ^ 2
            + (a.y_pos - b.by) ^ 2
            + (COALESCE(a.z_pos, 0) - b.bz) ^ 2 ) AS delta_v
    FROM asteroids a, b
    WHERE (a.x_pos - b.bx) ^ 2
        + (a.y_pos - b.by) ^ 2
        + (COALESCE(a.z_pos, 0) - b.bz) ^ 2 <= radius ^ 2
    ORDER BY delta_v ASC
    LIMIT LEAST(GREATEST(max_n, 0), 100);
$$;
