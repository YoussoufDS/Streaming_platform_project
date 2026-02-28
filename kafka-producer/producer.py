"""
Kafka Producer — Données financières
Consomme l'API FastAPI et publie sur 3 topics Kafka :
  - market.ticks     : chaque tick brut
  - market.anomalies : uniquement les événements extrêmes
  - market.batch     : snapshot toutes les 10s (tous les actifs)
"""
import time, os, json, requests
from kafka import KafkaProducer
from kafka.admin import KafkaAdminClient, NewTopic
from kafka.errors import NoBrokersAvailable, TopicAlreadyExistsError

KAFKA_SERVERS    = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
SCHEMA_REG_URL   = os.environ.get("SCHEMA_REGISTRY_URL", "http://localhost:8085")
API_BASE         = os.environ.get("SENSOR_API_URL", "http://localhost:5000")
TICK_INTERVAL    = float(os.environ.get("SEND_INTERVAL", 1.0))

TOPICS = [
    NewTopic("market.ticks",     num_partitions=5, replication_factor=1),
    NewTopic("market.anomalies", num_partitions=1, replication_factor=1),
    NewTopic("market.batch",     num_partitions=1, replication_factor=1),
]


def wait_for_api(retries=20):
    for i in range(retries):
        try:
            r = requests.get(f"{API_BASE}/health", timeout=3)
            if r.status_code == 200:
                print(f"[API] FastAPI prêt : {r.json()}")
                return True
        except Exception:
            pass
        print(f"[API] Attente FastAPI... ({i+1}/{retries})")
        time.sleep(3)
    raise RuntimeError("FastAPI inaccessible")


def create_topics():
    try:
        admin = KafkaAdminClient(bootstrap_servers=KAFKA_SERVERS.split(","))
        admin.create_topics(TOPICS)
        print(f"[TOPICS] Créés : {[t.name for t in TOPICS]}")
    except TopicAlreadyExistsError:
        print("[TOPICS] Topics déjà existants — OK")
    except Exception as e:
        print(f"[TOPICS] {e}")


def create_producer(retries=15):
    for i in range(retries):
        try:
            p = KafkaProducer(
                bootstrap_servers=KAFKA_SERVERS.split(","),
                value_serializer=lambda v: json.dumps(v).encode("utf-8"),
                key_serializer=lambda k: k.encode("utf-8") if k else None,
                acks="all",
                compression_type="gzip",
                linger_ms=5,
            )
            print(f"[KAFKA] Connecté sur {KAFKA_SERVERS}")
            return p
        except NoBrokersAvailable:
            print(f"[KAFKA] Pas encore prêt ({i+1}/{retries})...")
            time.sleep(5)
    raise RuntimeError("Kafka inaccessible")


def get_tick():
    r = requests.get(f"{API_BASE}/tick", timeout=5)
    r.raise_for_status()
    return r.json()


def get_all_ticks():
    r = requests.get(f"{API_BASE}/tick/all", timeout=5)
    r.raise_for_status()
    return r.json()


if __name__ == "__main__":
    wait_for_api()
    create_topics()
    producer = create_producer()

    sent_ticks = 0
    sent_anomalies = 0
    batch_interval = 10   # snapshot global toutes les 10s
    last_batch_time = time.time()

    print(f"[INFO] Streaming démarré — tick toutes les {TICK_INTERVAL}s")

    while True:
        try:
            # ── Tick individuel ─────────────────────────────────────────
            tick = get_tick()
            producer.send("market.ticks", value=tick, key=tick["symbol"])
            sent_ticks += 1

            # ── Anomalie → topic dédié ──────────────────────────────────
            if tick.get("is_anomaly"):
                producer.send("market.anomalies", value=tick, key=tick["symbol"])
                sent_anomalies += 1
                print(f"🚨 ANOMALIE | {tick['symbol']} | {tick['anomaly_type']} | "
                      f"price={tick['price']} | return={tick['returns_pct']}%")

            # ── Batch snapshot toutes les 10s ───────────────────────────
            if time.time() - last_batch_time >= batch_interval:
                snapshot = get_all_ticks()
                producer.send("market.batch", value=snapshot, key="snapshot")
                last_batch_time = time.time()
                print(f"[BATCH] Snapshot envoyé — {len(snapshot)} actifs")

            # ── Stats toutes les 100 ticks ──────────────────────────────
            if sent_ticks % 100 == 0:
                print(f"[STATS] {sent_ticks} ticks | {sent_anomalies} anomalies | "
                      f"dernier: {tick['symbol']} @ {tick['price']} "
                      f"({tick['returns_pct']:+.3f}%)")

        except Exception as e:
            print(f"[ERR] {e}")

        time.sleep(TICK_INTERVAL)
