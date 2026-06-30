-- Add format_structure_shorts and format_structure_videos content types to competitor_gpt_reports
-- Safe to run multiple times

ALTER TABLE competitor_gpt_reports
DROP CONSTRAINT IF EXISTS competitor_gpt_reports_content_type_check;

ALTER TABLE competitor_gpt_reports
ADD CONSTRAINT competitor_gpt_reports_content_type_check
CHECK (content_type IN (
    'shorts', 'videos', 'all', 'viral_shorts',
    'client', 'strategy', 'demand',
    'format_structure', 'format_structure_shorts', 'format_structure_videos',
    'evergreen_structure', 'views_share', 'duration_structure', 'velocity_trend'
));
