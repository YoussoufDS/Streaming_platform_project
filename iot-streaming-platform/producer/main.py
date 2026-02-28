"""
Financial Market Data Generator — Mouvement Brownien Géométrique
Simule un marché réaliste : stocks, crypto, forex
avec volatilité, volume, crashs et spikes aléatoires
"""
import random
import math
import time
import os
from datetime import datetime, timezone
from typing import Dict
from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse
import uvicorn

app = FastAPI(
    title="Financial Market Data Generator",
    description="Simule des données de marché réalistes via Mouvement Brownien Géométrique",
    version="3.0.0"
)

# ── Paramètres de simulation ───────────────────────────────────────────────────
TICK_INTERVAL   = float(os.environ.get("TICK_INTERVAL", 1.0))   # secondes entre ticks
CRASH_PROB      = float(os.environ.get("CRASH_PROB",   0.002))  # 0.2% chance de crash par tick
SPIKE_PROB      = float(os.environ.get("SPIKE_PROB",   0.005))  # 0.5% chance de spike
ANOMALY_RATE    = float(os.environ.get("ANOMALY_RATE", 0.03))   # 3% événements extrêmes

# ── Univers d'actifs financiers ───────────────────────────────────────────────
ASSETS: Dict[str, dict] = {
    # Stocks tech
    "AAPL":  {"price": 182.50, "volatility": 0.015, "drift": 0.0001,  "type": "stock",  "currency": "USD"},
    "TSLA":  {"price": 245.00, "volatility": 0.035, "drift": 0.0002,  "type": "stock",  "currency": "USD"},
    "MSFT":  {"price": 375.20, "volatility": 0.012, "drift": 0.0001,  "type": "stock",  "currency": "USD"},
    "NVDA":  {"price": 495.80, "volatility": 0.040, "drift": 0.0003,  "type": "stock",  "currency": "USD"},
    "GOOGL": {"price": 140.30, "volatility": 0.018, "drift": 0.0001,  "type": "stock",  "currency": "USD"},
    # Crypto
    "BTC-USD": {"price": 43500.0, "volatility": 0.055, "drift": 0.0003, "type": "crypto", "currency": "USD"},
    "ETH-USD": {"price": 2250.0,  "volatility": 0.060, "drift": 0.0002, "type": "crypto", "currency": "USD"},
    "SOL-USD": {"price": 98.50,   "volatility": 0.075, "drift": 0.0004, "type": "crypto", "currency": "USD"},
    # Forex
    "EUR-USD": {"price": 1.0850,  "volatility": 0.004, "drift": 0.00001, "type": "forex", "currency": "USD"},
    "CAD-USD": {"price": 0.7420,  "volatility": 0.003, "drift": 0.00001, "type": "forex", "currency": "USD"},
}

# État courant des prix (évolue à chaque tick)
current_prices: Dict[str, float] = {sym: info["price"] for sym, info in ASSETS.items()}
price_history:  Dict[str, list]  = {sym: [info["price"]] * 20 for sym, info in ASSETS.items()}
tick_count = 0


def gbm_next_price(symbol: str) -> float:
    """
    Mouvement Brownien Géométrique :
    S(t+dt) = S(t) * exp((μ - σ²/2)*dt + σ*√dt*Z)
    où Z ~ N(0,1), μ = drift, σ = volatilité
    """
    params    = ASSETS[symbol]
    S         = current_prices[symbol]
    mu        = params["drift"]
    sigma     = params["volatility"]
    dt        = TICK_INTERVAL / 86400  # fraction de journée

    # Terme brownien
    Z         = random.gauss(0, 1)
    drift_term = (mu - 0.5 * sigma ** 2) * dt
    diff_term  = sigma * math.sqrt(dt) * Z
    new_price  = S * math.exp(drift_term + diff_term)

    # Événements extrêmes
    roll = random.random()
    if roll < CRASH_PROB:
        # Flash crash : -5% à -15%
        new_price *= random.uniform(0.85, 0.95)
    elif roll < CRASH_PROB + SPIKE_PROB:
        # Spike haussier : +5% à +12%
        new_price *= random.uniform(1.05, 1.12)

    # Prix minimal (évite prix négatif)
    new_price = max(new_price, ASSETS[symbol]["price"] * 0.05)
    return round(new_price, 4 if ASSETS[symbol]["type"] == "forex" else 2)


def compute_indicators(symbol: str, current: float) -> dict:
    """Calcule les indicateurs techniques sur l'historique glissant."""
    history = price_history[symbol]

    # Returns
    prev      = history[-1] if history else current
    returns   = (current - prev) / prev if prev != 0 else 0.0

    # SMA 5 et 20
    sma5  = round(sum(history[-5:])  / min(len(history), 5),  2)
    sma20 = round(sum(history[-20:]) / min(len(history), 20), 2)

    # Volatilité réalisée (std des 10 derniers returns)
    if len(history) >= 2:
        rets = [(history[i] - history[i-1]) / history[i-1]
                for i in range(max(1, len(history)-10), len(history))]
        realized_vol = round(math.sqrt(sum(r**2 for r in rets) / len(rets)) * math.sqrt(252), 4)
    else:
        realized_vol = ASSETS[symbol]["volatility"]

    # Bid/Ask spread (réaliste par type d'actif)
    spread_pct = {"stock": 0.0002, "crypto": 0.0005, "forex": 0.00015}.get(ASSETS[symbol]["type"], 0.0002)
    spread     = current * spread_pct
    bid        = round(current - spread / 2, 4)
    ask        = round(current + spread / 2, 4)

    # Volume simulé (corrélé à la volatilité absolue)
    base_volume = {"stock": 1_000_000, "crypto": 500, "forex": 10_000_000}.get(ASSETS[symbol]["type"], 100_000)
    volume = int(base_volume * random.lognormvariate(0, 0.5) * (1 + abs(returns) * 20))

    # Détection anomalie
    is_anomaly   = abs(returns) > 0.03  # variation > 3% en 1 tick
    anomaly_type = None
    if is_anomaly:
        anomaly_type = "flash_crash" if returns < 0 else "price_spike"

    return {
        "bid":          bid,
        "ask":          ask,
        "spread":       round(spread, 6),
        "returns_pct":  round(returns * 100, 4),
        "sma5":         sma5,
        "sma20":        sma20,
        "realized_vol": realized_vol,
        "volume":       volume,
        "is_anomaly":   is_anomaly,
        "anomaly_type": anomaly_type,
        "signal":       "BUY" if sma5 > sma20 else "SELL",
    }


def generate_tick(symbol: str) -> dict:
    """Génère un tick complet pour un symbole donné."""
    new_price = gbm_next_price(symbol)
    current_prices[symbol] = new_price
    price_history[symbol].append(new_price)
    if len(price_history[symbol]) > 100:
        price_history[symbol].pop(0)

    indicators = compute_indicators(symbol, new_price)

    return {
        "symbol":       symbol,
        "asset_type":   ASSETS[symbol]["type"],
        "currency":     ASSETS[symbol]["currency"],
        "timestamp":    datetime.now(timezone.utc).isoformat(),
        "price":        new_price,
        "open":         price_history[symbol][-min(5, len(price_history[symbol]))],
        "high":         round(max(price_history[symbol][-5:]), 2),
        "low":          round(min(price_history[symbol][-5:]), 2),
        **indicators,
        "tick_number":  tick_count,
    }


# ── Endpoints FastAPI ─────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {
        "status":      "ok",
        "assets":      len(ASSETS),
        "ticks_served": tick_count,
        "crash_prob":  CRASH_PROB,
        "spike_prob":  SPIKE_PROB,
    }

@app.get("/tick")
def get_tick(symbol: str = Query(default=None)):
    """Retourne un tick pour un symbole (aléatoire si non précisé)."""
    global tick_count
    sym = symbol if symbol in ASSETS else random.choice(list(ASSETS.keys()))
    tick_count += 1
    return JSONResponse(generate_tick(sym))

@app.get("/tick/batch")
def get_batch(count: int = Query(default=10, le=50)):
    """Retourne N ticks pour des symboles aléatoires."""
    global tick_count
    ticks = []
    for _ in range(count):
        sym = random.choice(list(ASSETS.keys()))
        ticks.append(generate_tick(sym))
        tick_count += 1
    return ticks

@app.get("/tick/all")
def get_all_ticks():
    """Retourne un tick pour CHAQUE actif en une seule requête."""
    global tick_count
    result = {}
    for sym in ASSETS:
        result[sym] = generate_tick(sym)
        tick_count += 1
    return result

@app.get("/prices")
def get_current_prices():
    """Snapshot des prix courants."""
    return {
        sym: {
            "price":       current_prices[sym],
            "asset_type":  ASSETS[sym]["type"],
            "initial_price": ASSETS[sym]["price"],
            "pnl_pct":     round((current_prices[sym] / ASSETS[sym]["price"] - 1) * 100, 2),
        }
        for sym in ASSETS
    }

@app.get("/assets")
def list_assets():
    """Liste de tous les actifs disponibles."""
    return {
        "assets": list(ASSETS.keys()),
        "by_type": {
            "stocks": [s for s, a in ASSETS.items() if a["type"] == "stock"],
            "crypto":  [s for s, a in ASSETS.items() if a["type"] == "crypto"],
            "forex":   [s for s, a in ASSETS.items() if a["type"] == "forex"],
        }
    }

@app.get("/market/summary")
def market_summary():
    """Résumé du marché : gainers, losers, volatilité."""
    ticks = {sym: generate_tick(sym) for sym in ASSETS}
    sorted_by_return = sorted(ticks.items(), key=lambda x: x[1]["returns_pct"], reverse=True)
    return {
        "timestamp":    datetime.now(timezone.utc).isoformat(),
        "top_gainers":  [{"symbol": s, "return_pct": t["returns_pct"]} for s, t in sorted_by_return[:3]],
        "top_losers":   [{"symbol": s, "return_pct": t["returns_pct"]} for s, t in sorted_by_return[-3:]],
        "anomalies":    [{"symbol": s, "type": t["anomaly_type"]} for s, t in ticks.items() if t["is_anomaly"]],
        "total_volume": sum(t["volume"] for t in ticks.values()),
        "market_mood":  "BULLISH" if sum(1 for t in ticks.values() if t["returns_pct"] > 0) > len(ASSETS) / 2 else "BEARISH",
    }


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=5000, reload=False)
