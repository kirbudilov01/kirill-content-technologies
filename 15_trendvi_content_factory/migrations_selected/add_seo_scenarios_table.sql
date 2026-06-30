BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Таблица для хранения SEO сценариев
CREATE TABLE IF NOT EXISTS seo_scenarios (
    scenario_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    analysis_id TEXT REFERENCES competitor_analysis(competitor_analysis_id) ON DELETE SET NULL,
    type VARCHAR(20) NOT NULL CHECK (type IN ('video', 'shorts')),
    title VARCHAR(200) NOT NULL,
    request TEXT NOT NULL,
    response TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Индексы для быстрого поиска
CREATE INDEX IF NOT EXISTS idx_seo_scenarios_user_id ON seo_scenarios(user_id);
CREATE INDEX IF NOT EXISTS idx_seo_scenarios_analysis_id ON seo_scenarios(analysis_id);
CREATE INDEX IF NOT EXISTS idx_seo_scenarios_created_at ON seo_scenarios(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_seo_scenarios_type ON seo_scenarios(type);

-- Триггер для автоматического обновления updated_at
CREATE OR REPLACE FUNCTION update_seo_scenarios_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_update_seo_scenarios_updated_at ON seo_scenarios;
CREATE TRIGGER trigger_update_seo_scenarios_updated_at
    BEFORE UPDATE ON seo_scenarios
    FOR EACH ROW
    EXECUTE FUNCTION update_seo_scenarios_updated_at();

COMMIT;
