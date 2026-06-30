CREATE TABLE IF NOT EXISTS outlier_search_runs (
    run_id BIGSERIAL PRIMARY KEY,
    owner_id INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    keyword TEXT NOT NULL,
    task_id TEXT,
    status TEXT NOT NULL DEFAULT 'success',
    total_results INTEGER NOT NULL DEFAULT 0,
    language TEXT,
    region_code TEXT,
    lookback_hours INTEGER,
    max_results INTEGER,
    content_type TEXT,
    candidate_pool INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS outlier_video_snapshots (
    snapshot_id BIGSERIAL PRIMARY KEY,
    owner_id INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    keyword TEXT NOT NULL,
    video_id TEXT NOT NULL,
    channel_id TEXT,
    channel_title TEXT,
    video_title TEXT,
    content_type TEXT,
    topic_cluster TEXT,
    views BIGINT NOT NULL DEFAULT 0,
    likes BIGINT NOT NULL DEFAULT 0,
    comments BIGINT NOT NULL DEFAULT 0,
    subscribers BIGINT NOT NULL DEFAULT 0,
    baseline_views BIGINT NOT NULL DEFAULT 0,
    outlier_score NUMERIC(10,4) NOT NULL DEFAULT 0,
    quality_score NUMERIC(10,4) NOT NULL DEFAULT 0,
    confidence_score NUMERIC(10,4) NOT NULL DEFAULT 0,
    engagement_rate NUMERIC(10,6) NOT NULL DEFAULT 0,
    relative_multiplier NUMERIC(10,4) NOT NULL DEFAULT 0,
    velocity_per_hour NUMERIC(12,4) NOT NULL DEFAULT 0,
    views_delta_24h BIGINT NOT NULL DEFAULT 0,
    momentum_score NUMERIC(10,4) NOT NULL DEFAULT 0,
    captured_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_outlier_runs_owner_created
    ON outlier_search_runs (owner_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_outlier_snapshots_owner_video_time
    ON outlier_video_snapshots (owner_id, video_id, captured_at DESC);

CREATE INDEX IF NOT EXISTS idx_outlier_snapshots_owner_topic_time
    ON outlier_video_snapshots (owner_id, topic_cluster, captured_at DESC);

CREATE INDEX IF NOT EXISTS idx_outlier_snapshots_keyword_time
    ON outlier_video_snapshots (keyword, captured_at DESC);
