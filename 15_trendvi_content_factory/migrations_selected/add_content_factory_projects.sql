CREATE TABLE IF NOT EXISTS content_factory_projects (
    project_id BIGSERIAL PRIMARY KEY,
    owner_id INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    description TEXT,
    social_network TEXT NOT NULL DEFAULT 'youtube' CHECK (social_network IN ('youtube', 'instagram', 'tiktok', 'vk', 'rutube', 'dzen')),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_collection_at TIMESTAMPTZ
);

ALTER TABLE content_factory_channels
    ADD COLUMN IF NOT EXISTS project_id BIGINT REFERENCES content_factory_projects(project_id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_content_factory_projects_owner
    ON content_factory_projects (owner_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_content_factory_channels_project
    ON content_factory_channels (owner_id, project_id, created_at DESC);
