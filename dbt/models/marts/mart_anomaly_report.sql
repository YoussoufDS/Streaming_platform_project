-- Mart : rapport quotidien des anomalies par actif
{{ config(materialized='table') }}

SELECT
    DATE_TRUNC('day', window_start) AS trading_day,
    symbol,
    asset_type,
    COUNT(*)                              AS total_windows,
    SUM(tick_count)                       AS total_ticks,
    SUM(alert_count)                      AS total_anomalies,
    ROUND(AVG(alert_rate_pct)::NUMERIC,2) AS avg_anomaly_rate_pct,
    ROUND(MAX(high)::NUMERIC, 4)          AS day_high,
    ROUND(MIN(low)::NUMERIC, 4)           AS day_low,
    ROUND(AVG(vwap)::NUMERIC, 4)          AS day_avg_vwap,
    ROUND(AVG(realized_vol)::NUMERIC, 6)  AS avg_daily_vol,
    ROUND(MAX(stddev_return_pct)::NUMERIC,4) AS max_return_stddev
FROM {{ ref('stg_ohlcv') }}
GROUP BY 1, 2, 3
ORDER BY 1 DESC, total_anomalies DESC
