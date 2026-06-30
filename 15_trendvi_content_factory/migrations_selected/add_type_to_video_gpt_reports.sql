-- Migration: Add report type field to video_gpt_reports table
-- This helps differentiate between scenario and producer reports

ALTER TABLE video_gpt_reports
    ADD COLUMN IF NOT EXISTS report_type VARCHAR(50) DEFAULT 'producer';

-- Create index for faster queries by type
CREATE INDEX IF NOT EXISTS idx_video_gpt_reports_type ON video_gpt_reports(report_type);
