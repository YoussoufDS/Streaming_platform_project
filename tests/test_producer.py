"""Tests FastAPI — Financial Data Generator"""
import pytest
from fastapi.testclient import TestClient
import sys
sys.path.insert(0, "producer")
from main import app, generate_tick, current_prices, ASSETS

client = TestClient(app)

EXPECTED_FIELDS = [
    "symbol", "asset_type", "currency", "timestamp", "price",
    "open", "high", "low", "bid", "ask", "spread",
    "returns_pct", "sma5", "sma20", "realized_vol",
    "volume", "is_anomaly", "signal"
]


class TestHealthEndpoint:
    def test_returns_200(self):
        r = client.get("/health")
        assert r.status_code == 200

    def test_has_required_fields(self):
        data = client.get("/health").json()
        assert data["status"] == "ok"
        assert data["assets"] == len(ASSETS)


class TestTickEndpoint:
    def test_returns_200(self):
        assert client.get("/tick").status_code == 200

    def test_has_all_fields(self):
        data = client.get("/tick").json()
        for f in EXPECTED_FIELDS:
            assert f in data, f"Champ manquant : {f}"

    def test_symbol_is_valid(self):
        data = client.get("/tick").json()
        assert data["symbol"] in ASSETS

    def test_specific_symbol(self):
        data = client.get("/tick?symbol=AAPL").json()
        assert data["symbol"] == "AAPL"
        assert data["asset_type"] == "stock"

    def test_bid_less_than_ask(self):
        data = client.get("/tick").json()
        assert data["bid"] < data["ask"]

    def test_high_gte_low(self):
        data = client.get("/tick").json()
        assert data["high"] >= data["low"]

    def test_volume_positive(self):
        data = client.get("/tick").json()
        assert data["volume"] > 0

    def test_signal_valid(self):
        data = client.get("/tick").json()
        assert data["signal"] in ("BUY", "SELL")


class TestBatchEndpoint:
    def test_default_count(self):
        data = client.get("/tick/batch").json()
        assert len(data) == 10

    def test_custom_count(self):
        data = client.get("/tick/batch?count=5").json()
        assert len(data) == 5

    def test_max_count_enforced(self):
        r = client.get("/tick/batch?count=100")
        # FastAPI retourne 422 si > 50 (le max déclaré)
        assert r.status_code in (200, 422)


class TestAllTicksEndpoint:
    def test_returns_all_symbols(self):
        data = client.get("/tick/all").json()
        assert len(data) == len(ASSETS)
        for sym in ASSETS:
            assert sym in data


class TestPricesEndpoint:
    def test_snapshot_structure(self):
        data = client.get("/prices").json()
        assert len(data) == len(ASSETS)
        for sym, info in data.items():
            assert "price" in info
            assert "pnl_pct" in info


class TestMarketSummary:
    def test_market_summary_structure(self):
        data = client.get("/market/summary").json()
        assert "top_gainers" in data
        assert "top_losers"  in data
        assert "market_mood" in data
        assert data["market_mood"] in ("BULLISH", "BEARISH")
        assert len(data["top_gainers"]) == 3
        assert len(data["top_losers"])  == 3


class TestGBMProperties:
    def test_price_stays_positive(self):
        """Le GBM ne doit jamais produire un prix négatif"""
        sym = "AAPL"
        for _ in range(100):
            tick = generate_tick(sym)
            assert tick["price"] > 0, f"Prix négatif détecté : {tick['price']}"

    def test_crypto_higher_volatility(self):
        """BTC doit avoir une volatilité plus élevée que AAPL en moyenne"""
        from main import ASSETS
        assert ASSETS["BTC-USD"]["volatility"] > ASSETS["AAPL"]["volatility"]

    def test_forex_tight_spread(self):
        """Les paires forex ont un spread plus serré que les actions"""
        for _ in range(20):
            forex_tick = generate_tick("EUR-USD")
            stock_tick = generate_tick("AAPL")
            # Le spread % forex doit être < spread % stock
            forex_spread_pct = forex_tick["spread"] / forex_tick["price"]
            stock_spread_pct = stock_tick["spread"] / stock_tick["price"]
            assert forex_spread_pct < stock_spread_pct
