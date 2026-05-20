-- ============================================================================
-- nearby_asteroids — proximity query for the route planner.
-- Run once in the Supabase SQL editor. Idempotent (CREATE OR REPLACE).
-- ============================================================================

-- Returns asteroids within `radius` of the query location, ordered by 3D
-- distance (delta-v in proper-element velocity space: x/y plus z = inclination
-- axis). Hard-capped at 100 rows regardless of `max_n`.
CREATE OR REPLACE FUNCTION nearby_asteroids(
    qx     numeric,
    qy     numeric,
    qz     numeric DEFAULT 0,
    radius numeric DEFAULT 1000,
    max_n  integer DEFAULT 100
)
RETURNS SETOF asteroids
LANGUAGE sql
STABLE
AS $$
    SELECT *
    FROM asteroids
    WHERE (x_pos - qx) ^ 2
        + (y_pos - qy) ^ 2
        + (COALESCE(z_pos, 0) - qz) ^ 2 <= radius ^ 2
    ORDER BY (x_pos - qx) ^ 2
           + (y_pos - qy) ^ 2
           + (COALESCE(z_pos, 0) - qz) ^ 2 ASC
    LIMIT LEAST(GREATEST(max_n, 0), 100);
$$;
