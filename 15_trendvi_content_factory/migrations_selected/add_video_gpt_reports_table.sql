-- Migration: Add video_gpt_reports table for on-demand video analysis
-- Stores individual video GPT analysis (scenarios, duration analysis, trends, etc.)

CREATE TABLE IF NOT EXISTS video_gpt_reports (
    report_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    video_id VARCHAR(255) NOT NULL,
    analysis_id TEXT NOT NULL,
    owner_id BIGINT NOT NULL,
    
    -- GPT Report Content
    gpt_report TEXT,  -- Full GPT analysis (scenario, trends, keywords, etc.)
    scenario TEXT,    -- Extracted scenario for download
    
    -- Status
    is_ready BOOLEAN DEFAULT FALSE,
    status VARCHAR(50) DEFAULT 'pending',  -- pending, processing, ready, failed
    error_message TEXT,
    
    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    task_id VARCHAR(255),  -- Celery task ID for tracking
    
    FOREIGN KEY (analysis_id) REFERENCES competitor_analysis(competitor_analysis_id) ON DELETE CASCADE,
    FOREIGN KEY (owner_id) REFERENCES users(user_id) ON DELETE CASCADE
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_video_gpt_reports_analysis_id ON video_gpt_reports(analysis_id);
CREATE INDEX IF NOT EXISTS idx_video_gpt_reports_owner_id ON video_gpt_reports(owner_id);
CREATE INDEX IF NOT EXISTS idx_video_gpt_reports_video_id ON video_gpt_reports(video_id);
CREATE INDEX IF NOT EXISTS idx_video_gpt_reports_status ON video_gpt_reports(status);
CREATE INDEX IF NOT EXISTS idx_video_gpt_reports_is_ready ON video_gpt_reports(is_ready);
CREATE INDEX IF NOT EXISTS idx_video_gpt_reports_task_id ON video_gpt_reports(task_id);
