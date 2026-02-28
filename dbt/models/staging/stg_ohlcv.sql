{{ config(materialized='view') }}
SELECT
    window_start, window_end, symbol, asset_type,
    ROUND(open::NUMERIC,4)  AS open,
    ROUND(high::NUMERIC,4)  AS high,
    ROUND(low::NUMERIC,4)   AS low,
    ROUND(close::NUMERIC,4) AS close,
    volume,
    ROUND(vwap::NUMERIC,4)  AS vwap,
    ROUND(avg_realized_vol::NUMERIC,6)  AS realized_vol,
    ROUND(avg_spread::NUMERIC,6)        AS avg_spread,
    tick_count, alert_count,
    ROUND(avg_return_pct::NUMERIC,4)    AS avg_return_pct,
    ROUND(stddev_return_pct::NUMERIC,4) AS stddev_return_pct,
    ROUND((alert_count::NUMERIC / NULLIF(tick_count,0)) * 100, 2) AS alert_rate_pct,
    created_at
FROM {{ source('sensors_dw', 'ohlcv_aggregations') }}
WHERE close > 0 AND volume > 0 AND high >= low
