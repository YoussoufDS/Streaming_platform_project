# 🏦 Financial Streaming Platform

> Pipeline de données financières temps réel — Mouvement Brownien Géométrique · Kafka · Spark · dbt · Airflow · Grafana

![Python](https://img.shields.io/badge/Python-3.11-blue?logo=python)
![Kafka](https://img.shields.io/badge/Apache%20Kafka-7.5-black?logo=apachekafka)
![Spark](https://img.shields.io/badge/Apache%20Spark-3.4-orange?logo=apachespark)
![Airflow](https://img.shields.io/badge/Apache%20Airflow-2.8-red?logo=apacheairflow)
![dbt](https://img.shields.io/badge/dbt-1.8-orange?logo=dbt)
![Docker](https://img.shields.io/badge/Docker-Compose-blue?logo=docker)
![MongoDB](https://img.shields.io/badge/MongoDB-6.0-green?logo=mongodb)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15-blue?logo=postgresql)
![Grafana](https://img.shields.io/badge/Grafana-10.2-orange?logo=grafana)

---

## 📋 Description

Plateforme complète de streaming financier temps réel simulant le comportement de **10 actifs financiers** (actions, cryptomonnaies, paires forex) à l'aide du **Mouvement Brownien Géométrique (GBM)**. Les données transitent par un pipeline moderne de bout en bout, de la génération à la visualisation.

**Actifs simulés :** AAPL · TSLA · MSFT · NVDA · GOOGL · BTC-USD · ETH-USD · SOL-USD · EUR-USD · CAD-USD

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                     COUCHE INGESTION                                 │
│  FastAPI (GBM) ──► Kafka Producer ──► Schema Registry               │
└───────────────────────────┬─────────────────────────────────────────┘
                            │ market.ticks (85,000+ messages)
┌───────────────────────────▼─────────────────────────────────────────┐
│                   COUCHE STREAMING (Spark)                           │
│   Stream 1: Raw Ticks ──► MongoDB (MarketDB.Ticks)                  │
│   Stream 2: OHLCV + VWAP ──► PostgreSQL (sensors_dw)               │
│   Stream 3: Anomalies ──► Kafka (market.anomalies)                  │
└──────────┬──────────────────────────┬───────────────────────────────┘
           │                          │
┌──────────▼──────────┐   ┌───────────▼────────────────────────────────┐
│   COUCHE BATCH      │   │          COUCHE QUALITÉ                     │
│   Airflow (DAG      │   │  Great Expectations (5 checks)             │
│   horaire)          │   │  dbt (3 modèles: stg, marts)               │
│   ──► dbt ──►       │   │  pipeline_reports (PostgreSQL)             │
│   generate_report   │   └────────────────────────────────────────────┘
└──────────┬──────────┘
           │
┌──────────▼──────────────────────────────────────────────────────────┐
│                  COUCHE MONITORING                                    │
│         Prometheus ──► Grafana (Dashboards temps réel)              │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 🛠️ Stack Technologique

| Composant | Technologie | Version | Rôle |
|-----------|-------------|---------|------|
| **Générateur** | FastAPI + GBM | 3.0 | Simulation prix financiers |
| **Messaging** | Apache Kafka | 7.5.0 | Transport événements |
| **Schéma** | Schema Registry | 7.5.0 | Validation Avro |
| **Streaming** | Apache Spark | 3.4.1 | Traitement temps réel |
| **NoSQL** | MongoDB | 6.0 | Stockage ticks bruts |
| **SQL** | PostgreSQL | 15 | Agrégats OHLCV + rapports |
| **Batch** | Apache Airflow | 2.8.0 | Orchestration horaire |
| **Transform** | dbt | 1.8.7 | Modèles analytiques |
| **Qualité** | Great Expectations | Custom | 5 checks qualité |
| **Monitoring** | Prometheus + Grafana | 10.2 | Dashboards temps réel |
| **UI Kafka** | Kafka UI | 0.7.2 | Visualisation topics |
| **UI MongoDB** | Mongo Express | Latest | Inspection données |
| **Infra** | Docker Compose | 28.5 | Orchestration locale |

---

## 🧮 Modèle GBM (Mouvement Brownien Géométrique)

```
S(t+dt) = S(t) × exp[(μ - σ²/2)dt + σ√dt × Z]
```

| Paramètre | Description | Actions | Crypto | Forex |
|-----------|-------------|---------|--------|-------|
| **μ** | Drift (tendance) | 0.0001 | 0.0002 | 0.00005 |
| **σ** | Volatilité | 0.015 | 0.04 | 0.005 |
| **dt** | Intervalle temps | 1/252 | 1/365 | 1/252 |
| **Z** | Aléatoire N(0,1) | random | random | random |

---

## 🚀 Démarrage Rapide

### Prérequis
- Docker Desktop ≥ 24.0
- 8 GB RAM minimum (16 GB recommandé)
- Git

### Installation

```bash
# 1. Cloner le repo
git clone https://github.com/YoussoufDS/financial-streaming-platform-Project.git
cd financial-streaming-platform-Project/iot-streaming-platform

# 2. Copier les variables d'environnement
cp .env.example .env

# 3. Lancer toute la stack (5-10 min première fois)
docker compose up -d

# 4. Vérifier que tout tourne
docker compose ps
```

---

## 🖥️ Interfaces Disponibles

| Service | URL | Credentials |
|---------|-----|-------------|
| **FastAPI Docs** | http://localhost:5000/docs | — |
| **Kafka UI** | http://localhost:8080 | — |
| **Schema Registry** | http://localhost:8085 | — |
| **Mongo Express** | http://localhost:8081 | admin / admin123 |
| **Airflow** | http://localhost:8090 | admin / admin |
| **Grafana** | http://localhost:3000 | admin / admin |
| **Prometheus** | http://localhost:9090 | — |
| **PostgreSQL** | localhost:5432 | airflow / airflow |
| **MongoDB** | localhost:27017 | — |

---

## 📊 Captures d'écran

### FastAPI — Générateur GBM
![FastAPI](docs/screenshots/FastAPI.png)

### Apache Kafka UI — 85,000+ messages
![Kafka](docs/screenshots/Apache_Kafka_UI.png)

### Apache Airflow — DAG financier
![Airflow](docs/screenshots/Airflow_DAG_Financial_batch_pipeline.png)

### Grafana — Dashboard Prix Temps Réel
![Grafana](docs/screenshots/Graphana2_Price_dashboard.png)

### MongoDB — Ticks Temps Réel
![MongoDB](docs/screenshots/Mongo_Express.png)

---

## 🧪 Tests

```bash
# Tests logique Spark (39 tests)
pytest tests/test_spark_logic.py -v

# Tests FastAPI (dans Docker)
docker compose cp tests/test_producer.py data-generator:/app/test_producer.py
docker compose exec data-generator pytest /app/test_producer.py -v

# Avec couverture
pytest tests/ --cov=producer --cov-report=html
```

**Résultats :** 39/39 tests passés ✅

| Suite | Tests | Résultat |
|-------|-------|----------|
| TestPriceAlertLogic | 9 | ✅ PASS |
| TestVWAP | 4 | ✅ PASS |
| TestBollingerBands | 3 | ✅ PASS |
| TestOHLCConsistency | 4 | ✅ PASS |
| TestHealthEndpoint | 2 | ✅ PASS |
| TestTickEndpoint | 7 | ✅ PASS |
| TestGBMProperties | 3 | ✅ PASS |

---

## 📁 Structure du Projet

```
iot-streaming-platform/
├── producer/                    # FastAPI + GBM
│   ├── main.py                  # 7 endpoints, 10 actifs
│   └── Dockerfile
├── kafka-producer/              # Producteur Kafka
│   ├── producer.py              # Envoi market.ticks
│   └── Dockerfile
├── spark-processor/             # Spark Structured Streaming
│   ├── processor.py             # 3 streams parallèles
│   └── Dockerfile
├── airflow/
│   ├── Dockerfile               # + dbt-postgres
│   └── dags/
│       └── financial_batch_pipeline.py  # 4 tâches
├── dbt/
│   ├── models/
│   │   ├── staging/
│   │   │   ├── stg_ohlcv.sql    # Vue nettoyée
│   │   │   └── sources.yml
│   │   └── marts/
│   │       ├── mart_market_kpis.sql     # KPIs horaires
│   │       └── mart_anomaly_report.sql  # Rapport anomalies
│   └── dbt_project.yml
├── scripts/
│   └── postgres-init.sql        # Initialisation DB
├── monitoring/
│   ├── prometheus/
│   └── grafana/
├── tests/
│   ├── test_producer.py         # 19 tests FastAPI
│   └── test_spark_logic.py      # 20 tests Spark
├── docker-compose.yml           # 15 services
└── README.md
```

---

## 🔄 Pipeline Airflow — DAG `financial_batch_pipeline`

```
validate_data_quality ──► dbt_run ──► dbt_test ──► generate_report
     (5 checks GE)      (3 modèles)  (4 tests)    (rapport PostgreSQL)
```

**Checks Great Expectations :**
1. ✅ Fraîcheur des données (< 2 heures)
2. ✅ Plages de prix valides par symbole
3. ✅ Volume positif
4. ✅ Cohérence OHLC
5. ✅ Couverture symboles (≥ 8/10)

---

## 🌀 Modèles dbt

| Modèle | Type | Description |
|--------|------|-------------|
| `stg_ohlcv` | View | Données nettoyées + Bollinger Bands |
| `mart_market_kpis` | Table | KPIs horaires par symbole + classification risque |
| `mart_anomaly_report` | Table | Rapport quotidien anomalies |

---

## ⚠️ Notes & Perspectives

### Dérive des prix GBM
Le GBM est un processus stochastique sans retour à la moyenne. Après plusieurs heures de simulation, les prix s'éloignent des valeurs initiales réalistes. Les plages de validation Great Expectations ont été élargies pour ce projet éducatif.

**Perspectives pour les contributeurs :**
- Implémenter un modèle **Ornstein-Uhlenbeck** (retour à la moyenne) pour des prix plus réalistes
- Ajouter des **événements de marché** (annonces, crises) via des sauts de prix
- Intégrer des **données réelles** via l'API Yahoo Finance ou Alpha Vantage
- Déployer sur **AWS EC2** avec Terraform + GitHub Actions CI/CD (ECR → EC2 via SSM)
- Ajouter un **dashboard Grafana** complet avec alertes
- Implémenter **Apache Flink** pour comparer avec Spark Structured Streaming

---

## 👤 Auteur

**Abdouramane Youssouf**
Data & AI Specialist | Montréal, QC
GitHub: [@YoussoufDS](https://github.com/YoussoufDS)

---

## 📄 Licence

MIT License — Libre pour usage éducatif et personnel.
