-- 0111_inventory_intelligence_recommendations: demand forecasting, product
-- recommendation rollups and recommendation attribution.
--
-- Both pipelines are deliberately classical and inspectable. Forecasts use
-- rolling demand plus weekday seasonality; recommendations use co-purchase,
-- cosine similarity, category affinity, recency and popularity. Cron jobs
-- write immutable run-scoped rows and only expose completed runs, so a failed
-- refresh can never replace the last known-good result with a partial one.
--
-- D1-safe: no BEGIN TRANSACTION / SAVEPOINT, no TEMP tables.
PRAGMA foreign_keys = ON;

CREATE INDEX idx_order_items_variant_order
  ON order_items(variant_id, order_id);

CREATE INDEX idx_order_items_product_order
  ON order_items(product_id, order_id);

CREATE TABLE demand_forecast_runs (
  id TEXT PRIMARY KEY,
  status TEXT NOT NULL CHECK (status IN ('running', 'completed', 'failed')),
  model_version TEXT NOT NULL,
  horizon_days INTEGER NOT NULL CHECK (horizon_days BETWEEN 1 AND 90),
  variants_processed INTEGER NOT NULL DEFAULT 0 CHECK (variants_processed >= 0),
  forecasts_written INTEGER NOT NULL DEFAULT 0 CHECK (forecasts_written >= 0),
  started_at TEXT NOT NULL,
  completed_at TEXT,
  error_message TEXT
);

CREATE INDEX idx_demand_forecast_runs_status_time
  ON demand_forecast_runs(status, completed_at DESC);

CREATE TABLE inventory_forecast_settings (
  variant_id TEXT PRIMARY KEY,
  lead_time_days INTEGER NOT NULL DEFAULT 7 CHECK (lead_time_days BETWEEN 1 AND 90),
  safety_stock_days INTEGER NOT NULL DEFAULT 2 CHECK (safety_stock_days BETWEEN 0 AND 30),
  updated_at TEXT NOT NULL,
  updated_by TEXT,
  FOREIGN KEY (variant_id) REFERENCES product_variants(id) ON DELETE CASCADE,
  FOREIGN KEY (updated_by) REFERENCES users(id) ON DELETE SET NULL
);

CREATE TABLE demand_forecasts (
  run_id TEXT NOT NULL,
  product_id TEXT NOT NULL,
  variant_id TEXT NOT NULL,
  forecast_date TEXT NOT NULL,
  predicted_units REAL NOT NULL CHECK (predicted_units >= 0),
  lower_units REAL NOT NULL CHECK (lower_units >= 0),
  upper_units REAL NOT NULL CHECK (upper_units >= lower_units),
  seasonality_multiplier REAL NOT NULL CHECK (seasonality_multiplier > 0),
  created_at TEXT NOT NULL,
  PRIMARY KEY (run_id, variant_id, forecast_date),
  FOREIGN KEY (run_id) REFERENCES demand_forecast_runs(id) ON DELETE CASCADE,
  FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE,
  FOREIGN KEY (variant_id) REFERENCES product_variants(id) ON DELETE CASCADE
);

CREATE INDEX idx_demand_forecasts_variant_date
  ON demand_forecasts(variant_id, forecast_date, run_id);

CREATE TABLE demand_forecast_summaries (
  run_id TEXT NOT NULL,
  product_id TEXT NOT NULL,
  variant_id TEXT NOT NULL,
  avg_daily_7 REAL NOT NULL CHECK (avg_daily_7 >= 0),
  avg_daily_30 REAL NOT NULL CHECK (avg_daily_30 >= 0),
  available_units INTEGER NOT NULL,
  lead_time_days INTEGER NOT NULL CHECK (lead_time_days BETWEEN 1 AND 90),
  safety_stock_days INTEGER NOT NULL CHECK (safety_stock_days BETWEEN 0 AND 30),
  days_until_stockout REAL,
  projected_stockout_date TEXT,
  reorder_recommended INTEGER NOT NULL CHECK (reorder_recommended IN (0, 1)),
  recommended_order_units INTEGER NOT NULL CHECK (recommended_order_units >= 0),
  data_days INTEGER NOT NULL CHECK (data_days >= 0),
  created_at TEXT NOT NULL,
  PRIMARY KEY (run_id, variant_id),
  FOREIGN KEY (run_id) REFERENCES demand_forecast_runs(id) ON DELETE CASCADE,
  FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE,
  FOREIGN KEY (variant_id) REFERENCES product_variants(id) ON DELETE CASCADE
);

CREATE INDEX idx_demand_forecast_summaries_reorder
  ON demand_forecast_summaries(run_id, reorder_recommended, days_until_stockout);

CREATE TABLE recommendation_runs (
  id TEXT PRIMARY KEY,
  status TEXT NOT NULL CHECK (status IN ('running', 'completed', 'failed')),
  model_version TEXT NOT NULL,
  lookback_days INTEGER NOT NULL CHECK (lookback_days BETWEEN 7 AND 730),
  orders_processed INTEGER NOT NULL DEFAULT 0 CHECK (orders_processed >= 0),
  products_processed INTEGER NOT NULL DEFAULT 0 CHECK (products_processed >= 0),
  associations_written INTEGER NOT NULL DEFAULT 0 CHECK (associations_written >= 0),
  started_at TEXT NOT NULL,
  completed_at TEXT,
  error_message TEXT
);

CREATE INDEX idx_recommendation_runs_status_time
  ON recommendation_runs(status, completed_at DESC);

CREATE TABLE product_cooccurrence (
  run_id TEXT NOT NULL,
  source_product_id TEXT NOT NULL,
  recommended_product_id TEXT NOT NULL,
  co_purchase_count INTEGER NOT NULL CHECK (co_purchase_count >= 0),
  source_order_count INTEGER NOT NULL CHECK (source_order_count >= 0),
  recommended_order_count INTEGER NOT NULL CHECK (recommended_order_count >= 0),
  confidence REAL NOT NULL CHECK (confidence >= 0),
  lift REAL NOT NULL CHECK (lift >= 0),
  cosine_similarity REAL NOT NULL CHECK (cosine_similarity >= 0),
  category_match REAL NOT NULL CHECK (category_match BETWEEN 0 AND 1),
  popularity_score REAL NOT NULL CHECK (popularity_score BETWEEN 0 AND 1),
  recency_score REAL NOT NULL CHECK (recency_score BETWEEN 0 AND 1),
  blended_score REAL NOT NULL CHECK (blended_score >= 0),
  rank INTEGER NOT NULL CHECK (rank > 0),
  reason TEXT NOT NULL CHECK (reason IN ('frequently_bought_together', 'similar_product')),
  created_at TEXT NOT NULL,
  PRIMARY KEY (run_id, source_product_id, recommended_product_id),
  FOREIGN KEY (run_id) REFERENCES recommendation_runs(id) ON DELETE CASCADE,
  FOREIGN KEY (source_product_id) REFERENCES products(id) ON DELETE CASCADE,
  FOREIGN KEY (recommended_product_id) REFERENCES products(id) ON DELETE CASCADE,
  CHECK (source_product_id <> recommended_product_id)
);

CREATE INDEX idx_product_cooccurrence_lookup
  ON product_cooccurrence(run_id, source_product_id, rank);

CREATE TABLE recommendation_product_scores (
  run_id TEXT NOT NULL,
  product_id TEXT NOT NULL,
  units_7d INTEGER NOT NULL CHECK (units_7d >= 0),
  units_30d INTEGER NOT NULL CHECK (units_30d >= 0),
  order_count INTEGER NOT NULL CHECK (order_count >= 0),
  popularity_score REAL NOT NULL CHECK (popularity_score BETWEEN 0 AND 1),
  recency_score REAL NOT NULL CHECK (recency_score BETWEEN 0 AND 1),
  last_order_at TEXT,
  rank INTEGER NOT NULL CHECK (rank > 0),
  created_at TEXT NOT NULL,
  PRIMARY KEY (run_id, product_id),
  FOREIGN KEY (run_id) REFERENCES recommendation_runs(id) ON DELETE CASCADE,
  FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
);

CREATE INDEX idx_recommendation_product_scores_rank
  ON recommendation_product_scores(run_id, rank);

CREATE TABLE recommendation_events (
  id TEXT PRIMARY KEY,
  visitor_session_id TEXT NOT NULL,
  source_product_id TEXT,
  recommended_product_id TEXT NOT NULL,
  recommendation_run_id TEXT,
  placement TEXT NOT NULL CHECK (placement IN ('product', 'cart', 'homepage', 'category', 'shop', 'order')),
  event_type TEXT NOT NULL CHECK (event_type IN ('impression', 'click', 'add_to_cart')),
  created_at TEXT NOT NULL,
  FOREIGN KEY (source_product_id) REFERENCES products(id) ON DELETE SET NULL,
  FOREIGN KEY (recommended_product_id) REFERENCES products(id) ON DELETE CASCADE,
  FOREIGN KEY (recommendation_run_id) REFERENCES recommendation_runs(id) ON DELETE SET NULL
);

CREATE INDEX idx_recommendation_events_time_type
  ON recommendation_events(created_at, event_type);

CREATE INDEX idx_recommendation_events_product_time
  ON recommendation_events(recommended_product_id, created_at);

CREATE TABLE recommendation_attributions (
  id TEXT PRIMARY KEY,
  order_id TEXT NOT NULL,
  order_item_id TEXT NOT NULL UNIQUE,
  source_product_id TEXT,
  recommended_product_id TEXT NOT NULL,
  recommendation_run_id TEXT,
  placement TEXT NOT NULL CHECK (placement IN ('product', 'cart', 'homepage', 'category', 'shop', 'order')),
  quantity INTEGER NOT NULL CHECK (quantity > 0),
  attributed_revenue_minor INTEGER NOT NULL CHECK (attributed_revenue_minor >= 0),
  created_at TEXT NOT NULL,
  FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE,
  FOREIGN KEY (order_item_id) REFERENCES order_items(id) ON DELETE CASCADE,
  FOREIGN KEY (source_product_id) REFERENCES products(id) ON DELETE SET NULL,
  FOREIGN KEY (recommended_product_id) REFERENCES products(id) ON DELETE RESTRICT,
  FOREIGN KEY (recommendation_run_id) REFERENCES recommendation_runs(id) ON DELETE SET NULL
);

CREATE INDEX idx_recommendation_attributions_time
  ON recommendation_attributions(created_at, order_id);
