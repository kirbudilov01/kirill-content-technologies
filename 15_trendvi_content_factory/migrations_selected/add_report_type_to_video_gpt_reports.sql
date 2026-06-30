BEGIN;

ALTER TABLE video_gpt_reports
ADD COLUMN IF NOT EXISTS report_type VARCHAR(20) DEFAULT 'producer';

UPDATE video_gpt_reports
SET report_type = CASE
    WHEN scenario IS NOT NULL AND (gpt_report IS NULL OR TRIM(gpt_report) = '') THEN 'scenario'
    ELSE 'producer'
END
WHERE report_type IS NULL OR TRIM(report_type) = '';

CREATE INDEX IF NOT EXISTS idx_video_gpt_reports_report_type
    ON video_gpt_reports(report_type);

COMMIT;
