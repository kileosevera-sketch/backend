
-- Sprint 2: Improve complaint_insights for AI/NLP analysis

ALTER TABLE complaint_insights
ADD COLUMN IF NOT EXISTS processed_text TEXT;

ALTER TABLE complaint_insights
ADD COLUMN IF NOT EXISTS model_version VARCHAR(50);

ALTER TABLE complaint_insights
ADD COLUMN IF NOT EXISTS confidence NUMERIC(5,4);


