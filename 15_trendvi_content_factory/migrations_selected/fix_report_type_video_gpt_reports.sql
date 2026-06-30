-- Fix legacy report_type values in video_gpt_reports
-- Scenario rows should have report_type='scenario'
-- Producer rows should have report_type='producer'

BEGIN;

-- Set scenario where scenario text exists and gpt_report is empty
UPDATE video_gpt_reports
SET report_type = 'scenario'
WHERE (report_type IS NULL OR report_type <> 'scenario')
  AND scenario IS NOT NULL
  AND (gpt_report IS NULL OR TRIM(gpt_report) = '');

-- Set producer where gpt_report exists
UPDATE video_gpt_reports
SET report_type = 'producer'
WHERE (report_type IS NULL OR report_type <> 'producer')
  AND gpt_report IS NOT NULL
  AND TRIM(gpt_report) <> '';

COMMIT;
