CREATE TABLE IF NOT EXISTS reports (
  id TEXT PRIMARY KEY,
  text TEXT,
  text_hash TEXT,
  timestamp TEXT,
  language TEXT,
  region TEXT,
  region_tier TEXT,
  segment_id TEXT,
  source TEXT,
  source_url TEXT,
  dup_count INTEGER DEFAULT 1
);
CREATE INDEX IF NOT EXISTS idx_reports_ts ON reports(timestamp);
CREATE INDEX IF NOT EXISTS idx_reports_hash ON reports(text_hash);

CREATE TABLE IF NOT EXISTS embeddings (
  report_id TEXT PRIMARY KEY,
  vector BLOB
);

CREATE TABLE IF NOT EXISTS lineages (
  variant_id TEXT PRIMARY KEY,
  parent_id TEXT,
  label TEXT,
  first_seen TEXT,
  last_seen TEXT,
  report_count INTEGER,
  languages TEXT,
  regions TEXT,
  centroid BLOB
);

CREATE TABLE IF NOT EXISTS lineage_members (
  report_id TEXT,
  variant_id TEXT,
  assigned_at TEXT
);

CREATE TABLE IF NOT EXISTS rt_estimates (
  variant_id TEXT,
  as_of TEXT,
  rt REAL,
  rt_lower REAL,
  rt_upper REAL,
  status TEXT,
  n_reports INTEGER
);

CREATE TABLE IF NOT EXISTS posts (
  id TEXT PRIMARY KEY,
  created_at TEXT,
  title TEXT,
  technique_layer TEXT,
  variant_layer TEXT,
  action_steps TEXT,
  language TEXT,
  target_segment TEXT,
  variant_id TEXT,
  supporting_report_count INTEGER,
  rt_at_publish REAL,
  rt_lower_bound REAL,
  template_assisted INTEGER,
  state TEXT,
  approved_by TEXT
);
CREATE INDEX IF NOT EXISTS idx_posts_created ON posts(created_at DESC);

CREATE TABLE IF NOT EXISTS traces (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TEXT,
  stage TEXT,
  input_summary TEXT,
  decision TEXT,
  score REAL,
  latency_ms INTEGER,
  tokens INTEGER
);

CREATE TABLE IF NOT EXISTS loop_state (
  key TEXT PRIMARY KEY,
  value TEXT
);
