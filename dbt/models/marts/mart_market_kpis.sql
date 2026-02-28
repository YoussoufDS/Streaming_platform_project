-- Mart : KPIs marché par symbole et heure
{{ config(materialized='table', indexes=[{'columns': ['symbol', 'hour_bucket']}]) }}

WITH hourly AS (
    SELECT
        DATE_TRUNC('hour', window_start) AS hour_bucket,
        symbol,
        asset_type,
        -- Prix
        FIRST_VALUE(open)  OVER w AS hour_open,
        MAX(high)          OVER w AS hour_high,
        MIN(low)           OVER w AS hour_low,
        LAST_VALUE(close)  OVER w AS hour_close,
        -- Volume & VWAP
        SUM(volume)        OVER w AS hour_volume,
        AVG(vwap)          OVER w AS avg_vwap,
        -- Risque
        AVG(realized_vol)  OVER w AS avg_volatility,
        SUM(alert_count)   OVER w AS total_alerts,
        SUM(tick_count)    OVER w AS total_ticks,
        AVG(alert_rate_pct)OVER w AS avg_alert_rate
    FROM {{ ref('stg_ohlcv') }}
    WINDOW w AS (PARTITION BY symbol, DATE_TRUNC('hour', window_start)
                 ORDER BY window_start
                 ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING)
)
SELECT DISTINCT
    hour_bucket,
    symbol,
    asset_type,
    hour_open,
    hour_high,
    hour_low,
    hour_close,
    ROUND(((hour_close - hour_open) / NULLIF(hour_open,0) * 100)::NUMERIC, 2) AS hour_return_pct,
    hour_volume,
    ROUND(avg_vwap::NUMERIC, 4)       AS avg_vwap,
    ROUND(avg_volatility::NUMERIC, 6) AS avg_volatility,
    total_alerts,
    total_ticks,
    ROUND(avg_alert_rate::NUMERIC, 2) AS avg_alert_rate_pct,
    CASE
        WHEN avg_alert_rate > 10 THEN 'HIGH_RISK'
        WHEN avg_alert_rate > 5  THEN 'MEDIUM_RISK'
        ELSE                          'NORMAL'
    END AS risk_level
FROM hourly
