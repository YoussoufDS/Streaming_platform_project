-- ╔══════════════════════════════════════════════════════╗
-- ║   PostgreSQL Init — Financial Streaming Platform     ║
-- ╚══════════════════════════════════════════════════════╝

CREATE DATABASE sensors_dw;
\c sensors_dw;

-- ── Table : agrégats OHLCV depuis Spark ────────────────────────────────────
CREATE TABLE IF NOT EXISTS ohlcv_aggregations (
    id              SERIAL PRIMARY KEY,
    window_start    TIMESTAMP NOT NULL,
    window_end      TIMESTAMP NOT NULL,
    symbol          VARCHAR(20) NOT NULL,
    asset_type      VARCHAR(20),
    open            DOUBLE PRECISION,
    high            DOUBLE PRECISION,
    low             DOUBLE PRECISION,
    close           DOUBLE PRECISION,
    volume          BIGINT,
    vwap            DOUBLE PRECISION,
    avg_realized_vol DOUBLE PRECISION,
    avg_spread      DOUBLE PRECISION,
    tick_count      INTEGER,
    alert_count     INTEGER,
    avg_return_pct  DOUBLE PRECISION,
    stddev_return_pct DOUBLE PRECISION,
    created_at      TIMESTAMP DEFAULT NOW()
);

-- ── Table : rapports de qualité Airflow ───────────────────────────────────
CREATE TABLE IF NOT EXISTS pipeline_reports (
    id             SERIAL PRIMARY KEY,
    report_hour    TIMESTAMP NOT NULL,
    checks_passed  INTEGER,
    checks_failed  INTEGER,
    details        JSONB,
    created_at     TIMESTAMP DEFAULT NOW()
);

-- ── Index ─────────────────────────────────────────────────────────────────
CREATE INDEX idx_ohlcv_symbol_window ON ohlcv_aggregations(symbol, window_start);
CREATE INDEX idx_ohlcv_asset_type    ON ohlcv_aggregations(asset_type, window_start);
CREATE INDEX idx_report_hour         ON pipeline_reports(report_hour);
