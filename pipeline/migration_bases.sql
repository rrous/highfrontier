-- ============================================================================
-- bases — table of player home bases.
-- Run once in the Supabase SQL editor. Idempotent.
-- ============================================================================
--
-- A base is the player's current home in the asteroid field. Per `db_design.md`
-- §11.1 the player explores asteroids in the *surroundings* of the current base
-- during the day and moves to a new base in the evening.
--
-- First base is Flora (the family's namesake). No other bases are seeded — the
-- table is kept simple on purpose; multi-base mechanics (§11.6 snapshots,
-- §1.1 daily base switching) come later and will extend this schema.
--
-- A base lives at an asteroid. Its position in proper-element velocity space
-- is therefore not stored here — it is read from the joined `asteroids` row.

CREATE TABLE IF NOT EXISTS bases (
    id          bigserial    PRIMARY KEY,
    name        text         NOT NULL UNIQUE,
    asteroid_id bigint       NOT NULL REFERENCES asteroids(id) ON DELETE RESTRICT,
    created_at  timestamptz  NOT NULL DEFAULT now()
);

-- Seed the first base: Flora.
INSERT INTO bases (name, asteroid_id)
SELECT 'Flora', a.id
FROM asteroids a
WHERE a.name = 'Flora'
ON CONFLICT (name) DO NOTHING;

-- RLS: the list of bases is public (anyone can see which bases exist).
-- Writes happen offline under service_role, which bypasses RLS.
ALTER TABLE bases ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS bases_read ON bases;
CREATE POLICY bases_read
    ON bases
    FOR SELECT
    TO anon, authenticated
    USING (true);
