ALTER TABLE content_factory_projects
    DROP CONSTRAINT IF EXISTS content_factory_projects_social_network_check;

ALTER TABLE content_factory_projects
    DROP CONSTRAINT IF EXISTS content_factory_projects_social_network_allowed;

ALTER TABLE content_factory_projects
    ADD CONSTRAINT content_factory_projects_social_network_allowed
    CHECK (social_network IN ('youtube', 'instagram', 'tiktok', 'x', 'vk', 'ok', 'rutube', 'likee', 'dzen'));

ALTER TABLE content_factory_channels
    DROP CONSTRAINT IF EXISTS content_factory_channels_social_network_check;

ALTER TABLE content_factory_channels
    DROP CONSTRAINT IF EXISTS content_factory_channels_social_network_allowed;

ALTER TABLE content_factory_channels
    ADD CONSTRAINT content_factory_channels_social_network_allowed
    CHECK (social_network IN ('youtube', 'instagram', 'tiktok', 'x', 'vk', 'ok', 'rutube', 'likee', 'dzen'));

ALTER TABLE content_factory_video_stats
    DROP CONSTRAINT IF EXISTS content_factory_video_stats_social_network_check;

ALTER TABLE content_factory_video_stats
    DROP CONSTRAINT IF EXISTS content_factory_video_stats_social_network_allowed;

ALTER TABLE content_factory_video_stats
    ADD CONSTRAINT content_factory_video_stats_social_network_allowed
    CHECK (social_network IN ('youtube', 'instagram', 'tiktok', 'x', 'vk', 'ok', 'rutube', 'likee', 'dzen'));

ALTER TABLE content_factory_report_history
    DROP CONSTRAINT IF EXISTS content_factory_report_history_social_network_check;

ALTER TABLE content_factory_report_history
    DROP CONSTRAINT IF EXISTS content_factory_report_history_social_network_allowed;

ALTER TABLE content_factory_report_history
    ADD CONSTRAINT content_factory_report_history_social_network_allowed
    CHECK (social_network IN ('youtube', 'instagram', 'tiktok', 'x', 'vk', 'ok', 'rutube', 'likee', 'dzen'));