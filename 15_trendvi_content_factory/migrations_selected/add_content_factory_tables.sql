CREATE TABLE IF NOT EXISTS content_factory_channels (
    channel_id BIGSERIAL PRIMARY KEY,
    owner_id INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    social_network TEXT NOT NULL CHECK (social_network IN ('youtube', 'instagram', 'tiktok', 'vk', 'rutube', 'dzen')),
    channel_url TEXT NOT NULL,
    channel_external_id TEXT,
    channel_title TEXT,
    category TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_sync_at TIMESTAMPTZ,
    last_sync_status TEXT,
    last_sync_error TEXT,
    UNIQUE (owner_id, social_network, channel_url)
);

CREATE TABLE IF NOT EXISTS content_factory_video_stats (
    video_id BIGSERIAL PRIMARY KEY,
    owner_id INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    channel_id BIGINT NOT NULL REFERENCES content_factory_channels(channel_id) ON DELETE CASCADE,
    social_network TEXT NOT NULL CHECK (social_network IN ('youtube', 'instagram', 'tiktok', 'vk', 'rutube', 'dzen')),
    video_external_id TEXT,
    video_url TEXT NOT NULL,
    title TEXT NOT NULL,
    published_at TIMESTAMPTZ,
    captured_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    views BIGINT NOT NULL DEFAULT 0,
    likes BIGINT NOT NULL DEFAULT 0,
    comments BIGINT NOT NULL DEFAULT 0,
    shares BIGINT NOT NULL DEFAULT 0,
    saves BIGINT NOT NULL DEFAULT 0,
    duration_seconds INTEGER,
    extra JSONB NOT NULL DEFAULT '{}'::jsonb,
    UNIQUE (owner_id, social_network, video_url)
);

CREATE TABLE IF NOT EXISTS content_factory_report_history (
    report_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_id INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    period_days INTEGER NOT NULL CHECK (period_days IN (7, 30)),
    social_network TEXT CHECK (social_network IN ('youtube', 'instagram', 'tiktok', 'vk', 'rutube', 'dzen')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_content_factory_channels_owner
    ON content_factory_channels (owner_id, social_network, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_content_factory_video_stats_owner_time
    ON content_factory_video_stats (owner_id, captured_at DESC, social_network);

CREATE INDEX IF NOT EXISTS idx_content_factory_video_stats_sorting
    ON content_factory_video_stats (owner_id, social_network, views DESC, published_at DESC);

CREATE INDEX IF NOT EXISTS idx_content_factory_reports_owner_created
    ON content_factory_report_history (owner_id, created_at DESC);
