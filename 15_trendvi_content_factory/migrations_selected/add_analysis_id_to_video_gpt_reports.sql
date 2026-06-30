-- Migration: Complete schema update with all missing columns and logging tables
-- Run this on existing databases to bring them in sync with init.sql

-- ========================================
-- USERS TABLE ADDITIONS
-- ========================================
ALTER TABLE users 
    ADD COLUMN IF NOT EXISTS email TEXT UNIQUE,
    ADD COLUMN IF NOT EXISTS rate_type TEXT DEFAULT 'free',
    ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    ADD COLUMN IF NOT EXISTS last_login_at TIMESTAMP WITH TIME ZONE,
    ADD COLUMN IF NOT EXISTS competitor_analysis_limit INTEGER DEFAULT 5,
    ADD COLUMN IF NOT EXISTS video_gpt_reports_limit INTEGER DEFAULT 10,
    ADD COLUMN IF NOT EXISTS video_gpt_reports_usages INTEGER DEFAULT 0,
    ADD COLUMN IF NOT EXISTS gpt_reports_limit INTEGER DEFAULT 20,
    ADD COLUMN IF NOT EXISTS gpt_reports_usages INTEGER DEFAULT 0,
    ADD COLUMN IF NOT EXISTS total_tokens_used_lifetime BIGINT DEFAULT 0,
    ADD COLUMN IF NOT EXISTS total_api_calls_lifetime BIGINT DEFAULT 0,
    ADD COLUMN IF NOT EXISTS total_reports_generated INTEGER DEFAULT 0,
    ADD COLUMN IF NOT EXISTS total_revenue_generated NUMERIC(10,2) DEFAULT 0,
    ADD COLUMN IF NOT EXISTS last_payment_at TIMESTAMP WITH TIME ZONE,
    ADD COLUMN IF NOT EXISTS subscription_status TEXT DEFAULT 'inactive',
    ADD COLUMN IF NOT EXISTS telegram_chat_id BIGINT;

CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_rate_type ON users(rate_type);
CREATE INDEX IF NOT EXISTS idx_users_created_at ON users(created_at);
CREATE INDEX IF NOT EXISTS idx_users_telegram_chat_id ON users(telegram_chat_id);

-- ========================================
-- PAYMENTS TABLE ADDITIONS
-- ========================================
ALTER TABLE payments
    ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'pending';

CREATE INDEX IF NOT EXISTS idx_payments_created_at ON payments(created_at);
CREATE INDEX IF NOT EXISTS idx_payments_status ON payments(status);

-- ========================================
-- API_KEYS TABLE FIX
-- ========================================
ALTER TABLE api_keys
    ADD COLUMN IF NOT EXISTS active BOOLEAN DEFAULT TRUE;

CREATE INDEX IF NOT EXISTS idx_api_keys_active ON api_keys(active);

-- ========================================
-- COMPETITOR_ANALYSIS TABLE ADDITIONS
-- ========================================
ALTER TABLE competitor_analysis
    ADD COLUMN IF NOT EXISTS telegram_chat_id BIGINT;

CREATE INDEX IF NOT EXISTS idx_competitor_analysis_owner_id ON competitor_analysis(owner_id);
CREATE INDEX IF NOT EXISTS idx_competitor_analysis_telegram_chat_id ON competitor_analysis(telegram_chat_id);

-- ========================================
-- COMPETITOR_GPT_REPORTS TABLE ADDITIONS
-- ========================================
ALTER TABLE competitor_gpt_reports
    ADD COLUMN IF NOT EXISTS metrics JSONB,
    ADD COLUMN IF NOT EXISTS input_tokens INTEGER DEFAULT 0,
    ADD COLUMN IF NOT EXISTS output_tokens INTEGER DEFAULT 0,
    ADD COLUMN IF NOT EXISTS total_tokens INTEGER DEFAULT 0;

-- Add 'all' to content_type check constraint if possible (may need manual intervention)
ALTER TABLE competitor_gpt_reports
    ADD COLUMN IF NOT EXISTS tmp_content_type TEXT;

-- ========================================
-- VIDEO_GPT_REPORTS TABLE ADDITIONS
-- ========================================
ALTER TABLE video_gpt_reports
    ADD COLUMN IF NOT EXISTS gpt_report TEXT,
    ADD COLUMN IF NOT EXISTS scenario TEXT,
    ADD COLUMN IF NOT EXISTS report_type VARCHAR(50) DEFAULT 'producer';

-- ========================================
-- VIDEO_METRIC_SNAPSHOTS TABLE FIX (er column already exists, just verify)
-- ========================================
-- The 'er' column should already be in the table

-- ========================================
-- CREATE ALL MISSING LOGGING TABLES
-- ========================================

CREATE TABLE IF NOT EXISTS projects (
    project_id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    channel_youtube_id TEXT NOT NULL,
    channel_name TEXT NOT NULL,
    channel_url TEXT,
    subscribers_at_creation BIGINT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    is_active BOOLEAN DEFAULT TRUE
);
CREATE INDEX IF NOT EXISTS idx_projects_user_id ON projects(user_id);
CREATE INDEX IF NOT EXISTS idx_projects_created_at ON projects(created_at);

CREATE TABLE IF NOT EXISTS video_analysis_log (
    log_id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    project_id INTEGER REFERENCES projects(project_id) ON DELETE CASCADE,
    video_id TEXT NOT NULL,
    video_title TEXT,
    video_url TEXT,
    duration_seconds INTEGER,
    status TEXT NOT NULL,
    gpt_tokens_used INTEGER DEFAULT 0,
    gpt_cost NUMERIC(10,4),
    analysis_text TEXT,
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE
);
CREATE INDEX IF NOT EXISTS idx_video_analysis_log_user_id ON video_analysis_log(user_id);
CREATE INDEX IF NOT EXISTS idx_video_analysis_log_status ON video_analysis_log(status);

CREATE TABLE IF NOT EXISTS quota_usage_log (
    log_id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    quota_type TEXT NOT NULL,
    action TEXT NOT NULL,
    previous_value INTEGER,
    current_value INTEGER,
    limit_value INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_quota_usage_log_user_id ON quota_usage_log(user_id);

CREATE TABLE IF NOT EXISTS payments_detailed_log (
    log_id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    payment_id TEXT NOT NULL,
    amount NUMERIC(10,2) NOT NULL,
    currency TEXT DEFAULT 'USD',
    payment_method TEXT,
    status TEXT NOT NULL,
    package_type TEXT,
    tokens_granted INTEGER DEFAULT 0,
    credits_granted INTEGER DEFAULT 0,
    subscription_months INTEGER DEFAULT 0,
    error_details TEXT,
    ip_address TEXT,
    user_agent TEXT,
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_payments_detailed_log_user_id ON payments_detailed_log(user_id);
CREATE INDEX IF NOT EXISTS idx_payments_detailed_log_status ON payments_detailed_log(status);

CREATE TABLE IF NOT EXISTS api_usage_log (
    log_id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(user_id) ON DELETE CASCADE,
    api_type TEXT,
    endpoint TEXT NOT NULL,
    method TEXT NOT NULL,
    response_status INTEGER,
    response_time_ms INTEGER,
    results_count INTEGER DEFAULT 0,
    error_code TEXT,
    error_message TEXT,
    request_size INTEGER,
    response_size INTEGER,
    ip_address TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_api_usage_log_user_id ON api_usage_log(user_id);
CREATE INDEX IF NOT EXISTS idx_api_usage_log_created_at ON api_usage_log(created_at);

CREATE TABLE IF NOT EXISTS telegram_activity_log (
    log_id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    telegram_chat_id BIGINT NOT NULL,
    action TEXT NOT NULL,
    message_type TEXT,
    status TEXT,
    error_message TEXT,
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_telegram_activity_log_user_id ON telegram_activity_log(user_id);

CREATE TABLE IF NOT EXISTS user_sessions_log (
    session_id TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    ip_address TEXT,
    user_agent TEXT,
    device_type TEXT DEFAULT 'web',
    country TEXT,
    city TEXT,
    latitude NUMERIC(9,6),
    longitude NUMERIC(9,6),
    login_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    logout_at TIMESTAMP WITH TIME ZONE,
    last_activity_at TIMESTAMP WITH TIME ZONE,
    duration_minutes INTEGER,
    is_active BOOLEAN DEFAULT TRUE
);
CREATE INDEX IF NOT EXISTS idx_user_sessions_log_user_id ON user_sessions_log(user_id);

CREATE TABLE IF NOT EXISTS system_events_log (
    log_id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(user_id) ON DELETE CASCADE,
    event_type TEXT NOT NULL,
    description TEXT NOT NULL,
    old_value TEXT,
    new_value TEXT,
    triggered_by TEXT,
    details JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_system_events_log_event_type ON system_events_log(event_type);

CREATE TABLE IF NOT EXISTS reports_generation_log (
    log_id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    project_id INTEGER REFERENCES projects(project_id) ON DELETE CASCADE,
    report_type TEXT NOT NULL,
    status TEXT NOT NULL,
    videos_analyzed INTEGER DEFAULT 0,
    gpt_tokens_used INTEGER DEFAULT 0,
    gpt_cost NUMERIC(10,4),
    duration_seconds INTEGER,
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE
);
CREATE INDEX IF NOT EXISTS idx_reports_generation_log_user_id ON reports_generation_log(user_id);

CREATE TABLE IF NOT EXISTS integrations_log (
    log_id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    integration_type TEXT NOT NULL,
    status TEXT NOT NULL,
    external_id TEXT,
    error_message TEXT,
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_integrations_log_user_id ON integrations_log(user_id);

CREATE TABLE IF NOT EXISTS content_analysis_details (
    analysis_id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    project_id INTEGER REFERENCES projects(project_id) ON DELETE CASCADE,
    video_id TEXT NOT NULL,
    analysis_type TEXT NOT NULL,
    keywords TEXT[],
    trending_topics TEXT[],
    sentiment_score NUMERIC(3,2),
    engagement_prediction NUMERIC(5,2),
    viral_score NUMERIC(5,2),
    seo_score NUMERIC(5,2),
    readability_score NUMERIC(5,2),
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_content_analysis_details_user_id ON content_analysis_details(user_id);

CREATE TABLE IF NOT EXISTS error_tracking (
    error_id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(user_id) ON DELETE CASCADE,
    error_type TEXT NOT NULL,
    error_message TEXT NOT NULL,
    error_code TEXT,
    stack_trace TEXT,
    endpoint TEXT,
    method TEXT,
    request_body JSONB,
    response_status INTEGER,
    severity TEXT DEFAULT 'medium',
    ip_address TEXT,
    user_agent TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_error_tracking_severity ON error_tracking(severity);
CREATE INDEX IF NOT EXISTS idx_error_tracking_created_at ON error_tracking(created_at);

CREATE TABLE IF NOT EXISTS user_action_timeline (
    action_id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    action_type TEXT NOT NULL,
    duration_ms INTEGER,
    prev_action TEXT,
    time_since_prev_action_ms INTEGER,
    feature_used TEXT,
    success BOOLEAN DEFAULT TRUE,
    performance_rating TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_user_action_timeline_user_id ON user_action_timeline(user_id);

CREATE TABLE IF NOT EXISTS audience_insights (
    insight_id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    project_id INTEGER REFERENCES projects(project_id) ON DELETE CASCADE,
    age_group TEXT[],
    countries TEXT[],
    cities TEXT[],
    interests TEXT[],
    device_types TEXT[],
    viewer_retention NUMERIC(5,2),
    average_view_duration_seconds INTEGER,
    audience_growth_rate NUMERIC(5,2),
    subscriber_source TEXT,
    click_through_rate NUMERIC(5,2),
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_audience_insights_user_id ON audience_insights(user_id);

CREATE TABLE IF NOT EXISTS financial_metrics (
    metric_id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    project_id INTEGER REFERENCES projects(project_id) ON DELETE CASCADE,
    period TEXT NOT NULL,
    estimated_revenue NUMERIC(10,2),
    estimated_cpm NUMERIC(10,2),
    estimated_rpm NUMERIC(10,2),
    ad_revenue NUMERIC(10,2),
    sponsorship_revenue NUMERIC(10,2),
    merchandise_revenue NUMERIC(10,2),
    total_views BIGINT,
    total_watch_hours INTEGER,
    revenue_per_1k_views NUMERIC(10,2),
    ytb_payout_status TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_financial_metrics_user_id ON financial_metrics(user_id);

CREATE TABLE IF NOT EXISTS notification_log (
    notification_id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    notification_type TEXT NOT NULL,
    subject TEXT NOT NULL,
    content TEXT NOT NULL,
    status TEXT NOT NULL,
    sent_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    recipient_email TEXT,
    click_through_url TEXT,
    campaign_id TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_notification_log_user_id ON notification_log(user_id);

CREATE TABLE IF NOT EXISTS recommendations_log (
    recommendation_id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    project_id INTEGER REFERENCES projects(project_id) ON DELETE CASCADE,
    recommendation_type TEXT NOT NULL,
    recommendation_text TEXT NOT NULL,
    priority TEXT,
    estimated_impact TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_recommendations_log_user_id ON recommendations_log(user_id);

CREATE TABLE IF NOT EXISTS feedback_log (
    feedback_id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    feedback_type TEXT NOT NULL,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    rating INTEGER,
    category TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_feedback_log_user_id ON feedback_log(user_id);

CREATE TABLE IF NOT EXISTS gpt_reports (
    report_id TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    report_type TEXT NOT NULL,
    report_content TEXT,
    tokens_used INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_gpt_reports_user_id ON gpt_reports(user_id);

-- ========================================
-- VERIFICATION
-- ========================================
SELECT '✅ Complete migration successfully applied!' as status;
SELECT COUNT(*) as total_tables FROM information_schema.tables WHERE table_schema = 'public';
SELECT COUNT(*) as total_indexes FROM information_schema.indexes WHERE table_schema = 'public';
