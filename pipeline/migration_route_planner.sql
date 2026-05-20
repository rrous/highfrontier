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

-- 3) Widen real-valued columns to numeric.
--    The hand-made demo rows used whole numbers, so several physical columns
--    were created as integer. The full catalog carries fractional values
--    (e.g. h_mag 18.2, albedo 0.24, positions in velocity space), which a
--    numeric column accepts without loss. integer -> numeric is a safe widen.
ALTER TABLE asteroids ALTER COLUMN x_pos       TYPE numeric;
ALTER TABLE asteroids ALTER COLUMN y_pos       TYPE numeric;
ALTER TABLE asteroids ALTER COLUMN r_size      TYPE numeric;
ALTER TABLE asteroids ALTER COLUMN albedo      TYPE numeric;
ALTER TABLE asteroids ALTER COLUMN diameter_km TYPE numeric;
ALTER TABLE asteroids ALTER COLUMN period_h    TYPE numeric;
ALTER TABLE asteroids ALTER COLUMN a_au        TYPE numeric;
ALTER TABLE asteroids ALTER COLUMN e           TYPE numeric;
ALTER TABLE asteroids ALTER COLUMN i_deg       TYPE numeric;
ALTER TABLE asteroids ALTER COLUMN h_mag       TYPE numeric;
ALTER TABLE asteroid_tier2 ALTER COLUMN albedo      TYPE numeric;
ALTER TABLE asteroid_tier2 ALTER COLUMN diameter_km TYPE numeric;
ALTER TABLE asteroid_tier2 ALTER COLUMN period_h    TYPE numeric;

-- 4) Allow every spectral type the catalog produces.
--    The existing check constraint accepts S/C/M/V/E/D/P/K but rejects U
--    (unclassified — 163 bodies whose spectral type is genuinely unknown).
ALTER TABLE asteroids DROP CONSTRAINT IF EXISTS asteroids_spectral_type_check;
ALTER TABLE asteroids ADD CONSTRAINT asteroids_spectral_type_check
    CHECK (spectral_type IN ('S', 'C', 'M', 'V', 'E', 'D', 'P', 'K', 'U'));

-- 5) Remove the 12 hand-made demo rows.
--    REQUIRED: demo id=8 collides with the real asteroid (8) Flora.
TRUNCATE asteroids, asteroid_tier2, asteroid_tier3 RESTART IDENTITY CASCADE;

-- After this, run:  python pipeline/transform_to_db.py --push
-- (with SUPABASE_URL and SUPABASE_SERVICE_KEY set as environment variables)
