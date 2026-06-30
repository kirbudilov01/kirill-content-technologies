ALTER TABLE content_factory_video_stats
    ADD COLUMN IF NOT EXISTS moderation_status TEXT NOT NULL DEFAULT 'pending',
    ADD COLUMN IF NOT EXISTS moderation_updated_at TIMESTAMPTZ;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'content_factory_video_stats_moderation_status_check'
    ) THEN
        ALTER TABLE content_factory_video_stats
            ADD CONSTRAINT content_factory_video_stats_moderation_status_check
            CHECK (moderation_status IN ('pending', 'approved', 'rejected'));
    END IF;
END $$;

ALTER TABLE content_factory_report_history
    DROP CONSTRAINT IF EXISTS content_factory_report_history_period_days_check;

ALTER TABLE content_factory_report_history
    ADD CONSTRAINT content_factory_report_history_period_days_check
    CHECK (period_days IN (7, 30, 90, 365));

CREATE INDEX IF NOT EXISTS idx_content_factory_video_stats_moderation
    ON content_factory_video_stats (owner_id, moderation_status, captured_at DESC);

CREATE INDEX IF NOT EXISTS idx_content_factory_video_stats_published
    ON content_factory_video_stats (owner_id, published_at DESC);