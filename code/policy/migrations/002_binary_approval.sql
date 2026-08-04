-- Convert all approval surfaces to durable approved/blocked decisions.
-- Existing overturned appeals become approved scopes; upheld/denied become blocked.

ALTER TABLE access_requests DROP CONSTRAINT IF EXISTS access_requests_status_check;
UPDATE access_requests SET status = 'blocked' WHERE status = 'denied';
ALTER TABLE access_requests ADD CONSTRAINT access_requests_status_check
    CHECK (status IN ('pending', 'approved', 'blocked'));
ALTER TABLE access_requests ADD COLUMN IF NOT EXISTS admin_note TEXT;
ALTER TABLE access_requests ADD COLUMN IF NOT EXISTS reason_code TEXT;

ALTER TABLE decision_appeals DROP CONSTRAINT IF EXISTS decision_appeals_status_check;
UPDATE decision_appeals SET status = CASE
    WHEN status = 'overturned' THEN 'approved'
    WHEN status = 'upheld' THEN 'blocked'
    ELSE status
END;
ALTER TABLE decision_appeals ADD CONSTRAINT decision_appeals_status_check
    CHECK (status IN ('pending', 'approved', 'blocked'));
ALTER TABLE decision_appeals ADD COLUMN IF NOT EXISTS scope_fingerprint TEXT;
ALTER TABLE decision_appeals ADD COLUMN IF NOT EXISTS reason_code TEXT;
DO $$ BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'decision_appeals'
          AND column_name = 'prompt_hash'
    ) THEN
        EXECUTE 'UPDATE decision_appeals SET scope_fingerprint = prompt_hash '
                'WHERE scope_fingerprint IS NULL AND prompt_hash IS NOT NULL';
    END IF;
END $$;
ALTER TABLE decision_appeals DROP COLUMN IF EXISTS prompt_hash;
ALTER TABLE decision_appeals DROP COLUMN IF EXISTS pass_used;
