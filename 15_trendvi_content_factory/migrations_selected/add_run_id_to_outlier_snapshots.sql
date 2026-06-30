-- Link outlier_video_snapshots to their originating search run
-- so that history results can be loaded without re-running the search.
ALTER TABLE outlier_video_snapshots
    ADD COLUMN IF NOT EXISTS run_id BIGINT
        REFERENCES outlier_search_runs(run_id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_outlier_snapshots_run_id
    ON outlier_video_snapshots (run_id);
