"""Tests unitaires — logique Spark sans SparkContext"""
import pytest
import math


def apply_price_alert(returns_pct: float) -> tuple:
    """Réplique la logique d'alerte Spark"""
    if returns_pct < -3.0:
        alert = "FLASH_CRASH"
    elif returns_pct > 3.0:
        alert = "SPIKE"
    else:
        alert = None

    if returns_pct < -8.0 or returns_pct > 8.0:
        severity = "CRITICAL"
    elif returns_pct < -3.0 or returns_pct > 3.0:
        severity = "HIGH"
    else:
        severity = "NONE"

    return alert, severity


def compute_vwap(prices: list, volumes: list) -> float:
    """VWAP = sum(price * volume) / sum(volume)"""
    total_pv = sum(p * v for p, v in zip(prices, volumes))
    total_v  = sum(volumes)
    return round(total_pv / total_v, 4) if total_v > 0 else 0.0


def compute_bollinger(vwap: float, stddev_pct: float) -> tuple:
    upper = round(vwap + 2 * stddev_pct * vwap / 100, 4)
    lower = round(vwap - 2 * stddev_pct * vwap / 100, 4)
    return upper, lower


class TestPriceAlertLogic:
    @pytest.mark.parametrize("ret,expected_alert,expected_sev", [
        (0.0,   None,          "NONE"),
        (1.5,   None,          "NONE"),
        (-1.5,  None,          "NONE"),
        (3.5,   "SPIKE",       "HIGH"),
        (-3.5,  "FLASH_CRASH", "HIGH"),
        (9.0,   "SPIKE",       "CRITICAL"),
        (-10.0, "FLASH_CRASH", "CRITICAL"),
    ])
    def test_alert_classification(self, ret, expected_alert, expected_sev):
        alert, sev = apply_price_alert(ret)
        assert alert == expected_alert, f"returns_pct={ret}"
        assert sev   == expected_sev,   f"returns_pct={ret}"

    def test_boundary_exactly_3pct(self):
        """Exactement ±3% ne déclenche pas d'alerte"""
        alert, _ = apply_price_alert(3.0)
        assert alert is None
        alert, _ = apply_price_alert(-3.0)
        assert alert is None

    def test_boundary_just_above_3pct(self):
        alert, _ = apply_price_alert(3.001)
        assert alert == "SPIKE"


class TestVWAP:
    def test_basic_vwap(self):
        prices  = [100.0, 101.0, 102.0]
        volumes = [1000,  2000,  1500]
        vwap = compute_vwap(prices, volumes)
        expected = (100*1000 + 101*2000 + 102*1500) / (1000+2000+1500)
        assert abs(vwap - round(expected, 4)) < 0.0001

    def test_vwap_zero_volume(self):
        assert compute_vwap([100.0], [0]) == 0.0

    def test_vwap_single_price(self):
        assert compute_vwap([150.0], [1000]) == 150.0

    def test_vwap_between_min_max(self):
        prices  = [90.0, 100.0, 110.0]
        volumes = [1000, 1000, 1000]
        vwap = compute_vwap(prices, volumes)
        assert min(prices) <= vwap <= max(prices)


class TestBollingerBands:
    def test_upper_gt_lower(self):
        upper, lower = compute_bollinger(100.0, 2.0)
        assert upper > lower

    def test_symmetric_around_vwap(self):
        vwap  = 100.0
        upper, lower = compute_bollinger(vwap, 2.0)
        assert abs((upper - vwap) - (vwap - lower)) < 0.001

    def test_zero_stddev(self):
        upper, lower = compute_bollinger(100.0, 0.0)
        assert upper == lower == 100.0


class TestOHLCConsistency:
    @pytest.mark.parametrize("o,h,l,c,valid", [
        (100, 105, 95, 102, True),
        (100, 99,  95, 102, False),  # high < open
        (100, 105, 106, 102, False), # low > high
        (100, 105, 95, 110, False),  # close > high
    ])
    def test_ohlc_validity(self, o, h, l, c, valid):
        is_valid = (l <= o <= h) and (l <= c <= h) and (l <= h)
        assert is_valid == valid
