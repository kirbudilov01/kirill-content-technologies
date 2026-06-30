ALTER TABLE content_factory_channels
    ADD COLUMN IF NOT EXISTS preferred_period_preset TEXT,
    ADD COLUMN IF NOT EXISTS preferred_period_days INTEGER,
    ADD COLUMN IF NOT EXISTS preferred_start_date DATE,
    ADD COLUMN IF NOT EXISTS preferred_end_date DATE,
    ADD COLUMN IF NOT EXISTS subscribers_count BIGINT;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'content_factory_channels_period_preset_check'
    ) THEN
        ALTER TABLE content_factory_channels
            ADD CONSTRAINT content_factory_channels_period_preset_check
            CHECK (preferred_period_preset IS NULL OR preferred_period_preset IN ('7d', '30d', 'custom'));
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'content_factory_channels_period_days_check'
    ) THEN
        ALTER TABLE content_factory_channels
            ADD CONSTRAINT content_factory_channels_period_days_check
            CHECK (preferred_period_days IS NULL OR (preferred_period_days >= 1 AND preferred_period_days <= 365));
    END IF;
END $$;
