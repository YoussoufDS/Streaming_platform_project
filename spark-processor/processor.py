"""
Spark Structured Streaming — Financial Market Processor
- Stream 1 → MongoDB       : ticks bruts
- Stream 2 → PostgreSQL    : OHLCV + VWAP + volatilité (fenêtres 1min/5min)
- Stream 3 → Kafka alerts  : flash crashes & spikes
"""
import os
from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    from_json, col, window, avg, stddev,
    sum as _sum, max as _max, min as _min,
    count, first, last, when, lit,
    current_timestamp, to_json, struct, expr
)
from pyspark.sql.types import (
    StructType, StructField,
    StringType, DoubleType, BooleanType, LongType, IntegerType
)

KAFKA_SERVERS = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
MONGO_URI     = os.environ.get("MONGO_URI",    "mongodb://mongodb:27017/")
POSTGRES_URI  = "jdbc:postgresql://postgres:5432/sensors_dw"

TICK_SCHEMA = StructType([
    StructField("symbol",       StringType()),
    StructField("asset_type",   StringType()),
    StructField("currency",     StringType()),
    StructField("timestamp",    StringType()),
    StructField("price",        DoubleType()),
    StructField("open",         DoubleType()),
    StructField("high",         DoubleType()),
    StructField("low",          DoubleType()),
    StructField("bid",          DoubleType()),
    StructField("ask",          DoubleType()),
    StructField("spread",       DoubleType()),
    StructField("returns_pct",  DoubleType()),
    StructField("sma5",         DoubleType()),
    StructField("sma20",        DoubleType()),
    StructField("realized_vol", DoubleType()),
    StructField("volume",       LongType()),
    StructField("is_anomaly",   BooleanType()),
    StructField("anomaly_type", StringType()),
    StructField("signal",       StringType()),
    StructField("tick_number",  IntegerType()),
])


def get_spark():
    pkgs = ",".join([
        "org.apache.spark:spark-sql-kafka-0-10_2.12:3.4.1",
        "org.mongodb.spark:mongo-spark-connector_2.12:10.2.0",
        "org.postgresql:postgresql:42.6.0",
    ])
    return SparkSession.builder \
        .appName("FinancialStreamProcessor") \
        .master("local[*]") \
        .config("spark.jars.packages", pkgs) \
        .config("spark.sql.streaming.checkpointLocation", "/tmp/checkpoints") \
        .config("spark.sql.shuffle.partitions", "4") \
        .getOrCreate()


def write_to_mongo(df, epoch_id):
    if df.count() == 0:
        return
    df.write \
        .format("mongodb") \
        .mode("append") \
        .option("connection.uri", MONGO_URI) \
        .option("database", "MarketDB") \
        .option("collection", "Ticks") \
        .save()


def write_ohlcv_to_postgres(df, epoch_id):
    if df.count() == 0:
        return
    df.write \
        .format("jdbc") \
        .option("url", POSTGRES_URI) \
        .option("user", "airflow") \
        .option("password", "airflow") \
        .option("dbtable", "ohlcv_aggregations") \
        .option("driver", "org.postgresql.Driver") \
        .mode("append") \
        .save()


def main():
    spark = get_spark()
    spark.sparkContext.setLogLevel("WARN")
    print("[SPARK] Démarrage du streaming financier...")

    # ── Lecture Kafka ──────────────────────────────────────────────────
    raw = spark.readStream \
        .format("kafka") \
        .option("kafka.bootstrap.servers", KAFKA_SERVERS) \
        .option("subscribe", "market.ticks") \
        .option("startingOffsets", "latest") \
        .option("failOnDataLoss", "false") \
        .load()

    # ── Parsing + enrichissement ───────────────────────────────────────
    parsed = raw.select(
        from_json(col("value").cast("string"), TICK_SCHEMA).alias("d"),
        col("timestamp").alias("kafka_ts")
    ).select("d.*", "kafka_ts") \
     .withColumn("event_time",       col("timestamp").cast("timestamp")) \
     .withColumn("processing_time",  current_timestamp()) \
     .withColumn("price_alert",
         when(col("returns_pct") < -3.0, lit("FLASH_CRASH"))
        .when(col("returns_pct") >  3.0, lit("SPIKE"))
        .otherwise(lit(None).cast(StringType()))
     ) \
     .withColumn("alert_severity",
         when(col("returns_pct") < -8.0,  lit("CRITICAL"))
        .when(col("returns_pct") < -3.0,  lit("HIGH"))
        .when(col("returns_pct") >  8.0,  lit("CRITICAL"))
        .when(col("returns_pct") >  3.0,  lit("HIGH"))
        .otherwise(lit("NONE"))
     )

    # ── Stream 1 : ticks bruts → MongoDB ──────────────────────────────
    q_mongo = parsed.writeStream \
        .foreachBatch(write_to_mongo) \
        .outputMode("append") \
        .option("checkpointLocation", "/tmp/checkpoints/mongo") \
        .trigger(processingTime="3 seconds") \
        .start()

    # ── Stream 2 : OHLCV + VWAP par fenêtre 1min → PostgreSQL ─────────
    ohlcv = parsed \
        .withWatermark("event_time", "5 minutes") \
        .groupBy(
            window("event_time", "1 minute", "30 seconds"),
            "symbol", "asset_type"
        ).agg(
            first("open").alias("open"),
            _max("high").alias("high"),
            _min("low").alias("low"),
            last("price").alias("close"),
            _sum("volume").alias("volume"),
            # VWAP = sum(price * volume) / sum(volume)
            (
                _sum(col("price") * col("volume")) / _sum("volume")
            ).alias("vwap"),
            avg("realized_vol").alias("avg_realized_vol"),
            avg("spread").alias("avg_spread"),
            count("*").alias("tick_count"),
            count(when(col("price_alert").isNotNull(), 1)).alias("alert_count"),
            avg("returns_pct").alias("avg_return_pct"),
            stddev("returns_pct").alias("stddev_return_pct"),
        ) \
        .withColumn("window_start", col("window.start")) \
        .withColumn("window_end",   col("window.end")) \
        .drop("window")

    q_postgres = ohlcv.writeStream \
        .foreachBatch(write_ohlcv_to_postgres) \
        .outputMode("update") \
        .option("checkpointLocation", "/tmp/checkpoints/postgres") \
        .trigger(processingTime="15 seconds") \
        .start()

    # ── Stream 3 : alertes → topic Kafka market.anomalies ─────────────
    alerts = parsed \
        .filter(col("price_alert").isNotNull()) \
        .select(
            col("symbol").alias("key"),
            to_json(struct(
                "symbol", "asset_type", "timestamp", "price",
                "returns_pct", "volume", "price_alert", "alert_severity"
            )).alias("value")
        )

    q_alerts = alerts.writeStream \
        .format("kafka") \
        .option("kafka.bootstrap.servers", KAFKA_SERVERS) \
        .option("topic", "market.anomalies") \
        .option("checkpointLocation", "/tmp/checkpoints/alerts") \
        .outputMode("append") \
        .trigger(processingTime="3 seconds") \
        .start()

    print("[SPARK] 3 streams actifs : MongoDB | PostgreSQL OHLCV | Kafka Alerts")
    spark.streams.awaitAnyTermination()


if __name__ == "__main__":
    main()
