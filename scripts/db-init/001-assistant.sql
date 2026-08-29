-- Tabla de idempotencia compartida por los workflows (fase 2+).
-- La fase 1 (News) deduplica con los datos estáticos del propio workflow,
-- pero dejamos la tabla creada para no tener que migrar más adelante.
CREATE TABLE IF NOT EXISTS assistant_processed_items (
  item_key     TEXT PRIMARY KEY,
  source       TEXT NOT NULL,
  title        TEXT,
  payload      JSONB NOT NULL DEFAULT '{}'::jsonb,
  processed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_assistant_processed_source_at
  ON assistant_processed_items (source, processed_at DESC);
