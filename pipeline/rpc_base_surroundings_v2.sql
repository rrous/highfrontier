-- ============================================================================
-- base_surroundings_v2 — snapshot-backed surroundings of a named base.
-- Run once in the Supabase SQL editor. Idempotent (CREATE OR REPLACE).
-- ============================================================================
--
-- Physical-space successor of `base_surroundings` after the design pivot to
-- Kepler-propagated heliocentric coordinates (db_design.md §9.1, §11.3,
-- §11.6; scale verified against JPL Horizons in docs/horizons_verification.md).
--
-- Compared to the legacy `base_surroundings` (proper-element velocity space,
-- `delta_v` = Euclidean distance in that space), this RPC returns:
--   - heliocentric position XYZ in km and velocity XYZ in km/s (ecliptic
--     J2000) propagated to `p_date`,
--   - offsets from the base (dx/dy/dz/d_km),
--   - deltaV XYZ components `dv*_kms` (v_target − v_base) plus the derived
--     |dv|, v_radial, v_tang and dv_eff = |v_tang| + max(0, v_radial) —
--     the per-segment route cost that replaces the fixed DV_STOP (§11.3),
--   - the same Tier-1 catalog fields the legacy RPC exposed.
--
-- Data source is `scene_snapshots` (built daily by pipeline/snapshot_daily.py),
-- joined back to `asteroids` for catalog columns. Snapshot rows written before
-- 2026-06 lack the stored derived fields, so they are COALESCE-recomputed from
-- the dv*/d* components here.
--
-- The base's own asteroid is included (d_km = 0, dv = 0) so the client can
-- render it without a separate lookup. Hard-capped at 100 rows.

CREATE OR REPLACE FUNCTION base_surroundings_v2(
    base_name text,
    p_date    date    DEFAULT CURRENT_DATE,
    radius_km numeric DEFAULT 50000000,
    max_n     integer DEFAULT 100
)
RETURNS TABLE (
    id            bigint,
    name          text,
    spectral_type text,
    x_km          numeric,
    y_km          numeric,
    z_km          numeric,
    vx_kms        numeric,
    vy_kms        numeric,
    vz_kms        numeric,
    dx_km         numeric,
    dy_km         numeric,
    dz_km         numeric,
    d_km          numeric,
    dvx_kms       numeric,
    dvy_kms       numeric,
    dvz_kms       numeric,
    dv_kms        numeric,
    v_radial_kms  numeric,
    v_tang_kms    numeric,
    dv_eff_kms    numeric,
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
    fast_rotation boolean
)
LANGUAGE sql
STABLE
AS $$
    WITH raw AS (
        SELECT
            (item->>'id')::bigint        AS id,
            item->>'name'                AS name,
            item->>'spectral_type'       AS spectral_type,
            (item->>'x_km')::numeric     AS x_km,
            (item->>'y_km')::numeric     AS y_km,
            (item->>'z_km')::numeric     AS z_km,
            (item->>'vx_kms')::numeric   AS vx_kms,
            (item->>'vy_kms')::numeric   AS vy_kms,
            (item->>'vz_kms')::numeric   AS vz_kms,
            (item->>'dx_km')::numeric    AS dx_km,
            (item->>'dy_km')::numeric    AS dy_km,
            (item->>'dz_km')::numeric    AS dz_km,
            (item->>'d_km')::numeric     AS d_km,
            (item->>'dvx_kms')::numeric  AS dvx_kms,
            (item->>'dvy_kms')::numeric  AS dvy_kms,
            (item->>'dvz_kms')::numeric  AS dvz_kms,
            (item->>'dv_kms')::numeric       AS dv_kms_stored,
            (item->>'v_radial_kms')::numeric AS v_radial_stored,
            (item->>'v_tang_kms')::numeric   AS v_tang_stored,
            (item->>'dv_eff_kms')::numeric   AS dv_eff_stored
        FROM bases bs
        JOIN scene_snapshots s
          ON s.base_id = bs.id AND s.snapshot_date = p_date
        CROSS JOIN LATERAL jsonb_array_elements(s.asteroid_data) AS item
        WHERE bs.name = base_name
          AND (item->>'d_km')::numeric <= radius_km
    ),
    derived AS (
        SELECT
            raw.*,
            COALESCE(raw.dv_kms_stored,
                     sqrt(raw.dvx_kms^2 + raw.dvy_kms^2 + raw.dvz_kms^2))
                AS dv_kms,
            COALESCE(raw.v_radial_stored,
                     CASE WHEN raw.d_km > 0
                          THEN (raw.dvx_kms * raw.dx_km
                              + raw.dvy_kms * raw.dy_km
                              + raw.dvz_kms * raw.dz_km) / raw.d_km
                          ELSE 0 END)
                AS v_radial_kms
        FROM raw
    )
    SELECT
        d.id,
        d.name,
        d.spectral_type,
        d.x_km, d.y_km, d.z_km,
        d.vx_kms, d.vy_kms, d.vz_kms,
        d.dx_km, d.dy_km, d.dz_km, d.d_km,
        d.dvx_kms, d.dvy_kms, d.dvz_kms,
        d.dv_kms,
        d.v_radial_kms,
        COALESCE(d.v_tang_stored,
                 sqrt(GREATEST(0, d.dv_kms^2 - d.v_radial_kms^2)))
            AS v_tang_kms,
        COALESCE(d.dv_eff_stored,
                 sqrt(GREATEST(0, d.dv_kms^2 - d.v_radial_kms^2))
                 + GREATEST(0, d.v_radial_kms))
            AS dv_eff_kms,
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
        a.fast_rotation
    FROM derived d
    JOIN asteroids a ON a.id = d.id
    ORDER BY d.d_km ASC
    LIMIT LEAST(GREATEST(max_n, 0), 100);
$$;
