-- ============================================================================
-- Route-planner schema migration — prepares Supabase for the full Flora dataset
-- Run this in the Supabase SQL editor BEFORE pushing transform_to_db.py output.
-- ============================================================================

-- 1) New column for the generated Z coordinate (inclination axis).
--    The route planner is 2D (x_pos/y_pos); z_pos is stored for the client to
--    represent inclination separately.
ALTER TABLE asteroids ADD COLUMN IF NOT EXISTS z_pos numeric;

-- 2) `id` must accept explicit values — transform_to_db.py uses the asteroid
--    catalog number as the primary key (so asteroid_tier2/3.asteroid_id can be
--    built before insert). If `id` was created as serial/identity, drop the
--    auto-generation. One of these may be a no-op depending on how the table
--    was created; that is harmless.
ALTER TABLE asteroids ALTER COLUMN id DROP IDENTITY IF EXISTS;
ALTER TABLE asteroids ALTER COLUMN id DROP DEFAULT;

-- 3) Remove the 12 hand-made demo rows.
--    REQUIRED: demo id=8 collides with the real asteroid (8) Flora.
TRUNCATE asteroids, asteroid_tier2, asteroid_tier3 RESTART IDENTITY CASCADE;

-- After this, run:  python pipeline/transform_to_db.py --push
-- (with SUPABASE_URL and SUPABASE_SERVICE_KEY set as environment variables)
