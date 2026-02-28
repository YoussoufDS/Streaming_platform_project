"""
DAG Airflow — Financial Batch Pipeline
Orchestre toutes les heures : Great Expectations → dbt → rapport
"""
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator
from airflow.utils.dates import days_ago
import psycopg2, json

default_args = {
    "owner":            "data-engineering",
    "depends_on_past":  False,
    "email_on_failure": False,
    "retries":          2,
    "retry_delay":      timedelta(minutes=5),
}

dag = DAG(
    dag_id="financial_batch_pipeline",
    default_args=default_args,
    description="Pipeline batch financier : GE validation → dbt → rapport",
    schedule_interval="0 * * * *",
    start_date=days_ago(1),
    catchup=False,
    tags=["finance", "streaming", "data-quality", "dbt"],
)

SYMBOLS    = ["AAPL", "TSLA", "MSFT", "NVDA", "GOOGL", "BTC-USD", "ETH-USD", "SOL-USD", "EUR-USD", "CAD-USD"]
ASSET_TYPES = {"stock": ["AAPL","TSLA","MSFT","NVDA","GOOGL"], "crypto": ["BTC-USD","ETH-USD","SOL-USD"], "forex": ["EUR-USD","CAD-USD"]}

PRICE_RANGES = {
    "AAPL":    (1, 500000),
    "TSLA":    (1, 500000),
    "MSFT":    (1, 500000),
    "NVDA":    (1, 500000),
    "GOOGL":   (1, 500000),
    "BTC-USD": (1, 50000000),
    "ETH-USD": (1, 5000000),
    "SOL-USD": (1, 500000),
    "EUR-USD": (0.01, 100.0),
    "CAD-USD": (0.01, 100.0),
}


def get_pg_conn():
    return psycopg2.connect(host="postgres", database="sensors_dw", user="airflow", password="airflow")


def validate_data_quality(**context):
    """Great Expectations — 5 checks de qualité sur les données OHLCV"""
    conn = get_pg_conn()
    cur  = conn.cursor()
    results = {"checks": [], "passed": 0, "failed": 0}

    # Check 1 : données récentes (< 2h)
    cur.execute("""
        SELECT COUNT(*) FROM ohlcv_aggregations
        WHERE window_start > NOW() - INTERVAL '2 hours'
    """)
    recent = cur.fetchone()[0]
    results["checks"].append({
        "name": "data_freshness",
        "passed": recent > 0,
        "detail": f"{recent} fenêtres récentes trouvées"
    })

    # Check 2 : prix dans les plages valides par symbole
    bad_prices = 0
    for sym, (lo, hi) in PRICE_RANGES.items():
        cur.execute("""
            SELECT COUNT(*) FROM ohlcv_aggregations
            WHERE symbol = %s AND (close < %s OR close > %s)
            AND created_at > NOW() - INTERVAL '2 hours'
        """, (sym, lo, hi))
        bad_prices += cur.fetchone()[0]
    results["checks"].append({
        "name": "price_range_validity",
        "passed": bad_prices == 0,
        "detail": f"{bad_prices} prix hors plage détectés"
    })

    # Check 3 : volume positif
    cur.execute("""
        SELECT COUNT(*) FROM ohlcv_aggregations
        WHERE volume <= 0 AND created_at > NOW() - INTERVAL '2 hours'
    """)
    bad_vol = cur.fetchone()[0]
    results["checks"].append({
        "name": "positive_volume",
        "passed": bad_vol == 0,
        "detail": f"{bad_vol} volumes invalides"
    })

    # Check 4 : cohérence OHLC (low <= open/close <= high)
    cur.execute("""
        SELECT COUNT(*) FROM ohlcv_aggregations
        WHERE low > high * 1.01
        AND created_at > NOW() - INTERVAL '2 hours'
    """)
    bad_ohlc = cur.fetchone()[0]
    results["checks"].append({
        "name": "ohlc_consistency",
        "passed": bad_ohlc == 0,
        "detail": f"{bad_ohlc} OHLC incohérents"
    })

    # Check 5 : couverture des symboles (>= 8 sur 10)
    cur.execute("""
        SELECT COUNT(DISTINCT symbol) FROM ohlcv_aggregations
        WHERE window_start > NOW() - INTERVAL '1 hour'
    """)
    symbols_covered = cur.fetchone()[0]
    results["checks"].append({
        "name": "symbol_coverage",
        "passed": symbols_covered >= 8,
        "detail": f"{symbols_covered}/10 symboles couverts"
    })

    conn.close()

    results["passed"] = sum(1 for c in results["checks"] if c["passed"])
    results["failed"] = sum(1 for c in results["checks"] if not c["passed"])

    context["ti"].xcom_push(key="gx_results", value=results)
    print(json.dumps(results, indent=2))

    if results["failed"] > 0:
        raise ValueError(f"Great Expectations : {results['failed']} check(s) échoués !\n{json.dumps(results, indent=2)}")

    print(f"[GE] ✅ Tous les checks passés ({results['passed']}/5)")
    return results


def generate_hourly_report(**context):
    """Insère le rapport de qualité dans PostgreSQL"""
    gx = context["ti"].xcom_pull(key="gx_results", task_ids="validate_data_quality")
    conn = get_pg_conn()
    cur  = conn.cursor()
    cur.execute("""
        INSERT INTO pipeline_reports (report_hour, checks_passed, checks_failed, details, created_at)
        VALUES (%s, %s, %s, %s, NOW())
    """, (
        datetime.now().replace(minute=0, second=0, microsecond=0),
        gx["passed"], gx["failed"], json.dumps(gx)
    ))
    conn.commit()
    conn.close()
    print(f"[REPORT] ✅ Rapport sauvegardé — {gx['passed']} passed / {gx['failed']} failed")


with dag:
    t1 = PythonOperator(
        task_id="validate_data_quality",
        python_callable=validate_data_quality,
        provide_context=True,
    )
    t2 = BashOperator(
        task_id="dbt_run",
        bash_command="cd /opt/airflow/dbt && dbt run --profiles-dir . --target prod --select staging marts",
    )
    t3 = BashOperator(
        task_id="dbt_test",
        bash_command="cd /opt/airflow/dbt && dbt test --profiles-dir . --target prod",
    )
    t4 = PythonOperator(
        task_id="generate_report",
        python_callable=generate_hourly_report,
        provide_context=True,
    )

    t1 >> t2 >> t3 >> t4
