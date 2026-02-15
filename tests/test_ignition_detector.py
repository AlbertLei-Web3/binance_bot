"""
引爆信号检测器测试
覆盖：冲高回落、放量暴跌、双确认逻辑、无信号场景
"""
import pytest
from strategies.ignition_detector import IgnitionDetector, DEFAULT_IGNITION_CONFIG
from strategies.signal_engine import SignalEngine


# ============================================================
# 辅助函数：构造 K 线数据
# ============================================================
# K 线格式: [open_time, open, high, low, close, volume, ...]

def make_kline(open_p, high, low, close, volume, ts=0):
    """构造单根 K 线"""
    return [ts, open_p, high, low, close, volume, 0, 0, 0, 0, 0, 0]


def make_normal_klines(n=10, base_price=100.0, base_vol=1000.0):
    """构造 N 根正常波动的 K 线（小幅震荡，稳定量能）"""
    klines = []
    for i in range(n):
        o = base_price + i * 0.1
        c = o + 0.05
        h = max(o, c) + 0.02
        l = min(o, c) - 0.02
        klines.append(make_kline(o, h, l, c, base_vol))
    return klines


# ============================================================
# 冲高回落形态测试
# ============================================================

class TestSpikeAndDrop:
    """冲高回落检测"""

    def _build_spike_klines(self, base_vol=1000.0):
        """构造冲高回落 K 线序列"""
        # 前 8 根正常 K 线
        klines = make_normal_klines(8, base_price=100.0, base_vol=base_vol)
        # 倒数第 2 根：冲高回落（长上影线 + 收阴 + 放量）
        # open=101, high=105, low=100.5, close=100.5 → 上影线=4.5, 实体=0.5
        klines.append(make_kline(101.0, 105.0, 100.5, 100.5, base_vol * 3))
        # 最后一根：缩量
        klines.append(make_kline(100.5, 100.8, 100.3, 100.4, base_vol * 0.3))
        return klines

    def test_spike_detected(self):
        """标准冲高回落应被检测到"""
        detector = IgnitionDetector()
        klines = self._build_spike_klines()
        assert detector._detect_spike_and_drop(klines, detector.cfg_5m) is True

    def test_no_spike_without_upper_shadow(self):
        """无上影线不应触发"""
        detector = IgnitionDetector()
        klines = make_normal_klines(10)
        assert detector._detect_spike_and_drop(klines, detector.cfg_5m) is False

    def test_no_spike_without_volume(self):
        """无放量不应触发"""
        detector = IgnitionDetector()
        klines = make_normal_klines(8, base_vol=1000.0)
        # 冲高回落形态但量能不足（与均量持平）
        klines.append(make_kline(101.0, 105.0, 100.5, 100.5, 1000.0))
        klines.append(make_kline(100.5, 100.8, 100.3, 100.4, 300.0))
        assert detector._detect_spike_and_drop(klines, detector.cfg_5m) is False

    def test_no_spike_without_shrink(self):
        """后续未缩量不应触发"""
        detector = IgnitionDetector()
        klines = make_normal_klines(8, base_vol=1000.0)
        klines.append(make_kline(101.0, 105.0, 100.5, 100.5, 3000.0))
        # 最后一根量能仍然很大（未缩量）
        klines.append(make_kline(100.5, 100.8, 100.3, 100.4, 2500.0))
        assert detector._detect_spike_and_drop(klines, detector.cfg_5m) is False


# ============================================================
# 放量暴跌形态测试
# ============================================================

class TestVolumeCrash:
    """放量暴跌检测"""

    def test_single_big_bearish_candle(self):
        """单根大阴线放量应被检测到"""
        detector = IgnitionDetector()
        klines = make_normal_klines(8, base_price=100.0, base_vol=1000.0)
        # 大阴线：open=102, close=100（跌 1.96%），实体占比高，放量
        klines.append(make_kline(102.0, 102.2, 99.8, 100.0, 3000.0))
        klines.append(make_kline(100.0, 100.2, 99.8, 99.9, 1000.0))
        assert detector._detect_volume_crash(klines, detector.cfg_5m) is True

    def test_consecutive_bearish_candles(self):
        """连续阴线累计跌幅达标应被检测到"""
        detector = IgnitionDetector()
        klines = make_normal_klines(7, base_price=100.0, base_vol=1000.0)
        # 连续 3 根阴线，累计跌幅 > 2%
        klines.append(make_kline(101.0, 101.1, 100.3, 100.4, 1000.0))
        klines.append(make_kline(100.4, 100.5, 99.8, 99.9, 1000.0))
        klines.append(make_kline(99.9, 100.0, 98.8, 98.9, 1000.0))
        assert detector._detect_volume_crash(klines, detector.cfg_5m) is True

    def test_no_crash_normal_market(self):
        """正常行情不应触发"""
        detector = IgnitionDetector()
        klines = make_normal_klines(10)
        assert detector._detect_volume_crash(klines, detector.cfg_5m) is False


# ============================================================
# 双确认逻辑测试
# ============================================================

class TestDualConfirmation:
    """5m + 15m 双周期确认"""

    def _build_spike_klines(self, base_vol=1000.0):
        klines = make_normal_klines(8, base_price=100.0, base_vol=base_vol)
        klines.append(make_kline(101.0, 105.0, 100.5, 100.5, base_vol * 3))
        klines.append(make_kline(100.5, 100.8, 100.3, 100.4, base_vol * 0.3))
        return klines

    def _build_crash_klines(self, base_vol=1000.0):
        klines = make_normal_klines(8, base_price=100.0, base_vol=base_vol)
        klines.append(make_kline(102.0, 102.2, 99.8, 100.0, base_vol * 3))
        klines.append(make_kline(100.0, 100.2, 99.8, 99.9, base_vol))
        return klines

    def test_both_patterns_confirmed(self):
        """两种形态都在双周期确认 → strength=0.95"""
        detector = IgnitionDetector()
        # 构造同时包含冲高回落和放量暴跌的 K 线
        # 使用放量暴跌 + 冲高回落混合
        klines_5m = make_normal_klines(6, base_vol=1000.0)
        # 先加大阴线放量（crash）
        klines_5m.append(make_kline(102.0, 102.2, 99.8, 100.0, 3000.0))
        # 再加冲高回落（spike）
        klines_5m.append(make_kline(100.0, 104.0, 99.8, 99.8, 3000.0))
        klines_5m.append(make_kline(99.8, 100.0, 99.5, 99.6, 500.0))

        klines_15m = make_normal_klines(6, base_vol=1000.0)
        klines_15m.append(make_kline(102.0, 102.2, 99.2, 99.5, 3000.0))
        klines_15m.append(make_kline(99.5, 104.0, 99.0, 99.0, 3000.0))
        klines_15m.append(make_kline(99.0, 99.2, 98.8, 98.9, 500.0))

        signal = detector.detect(klines_5m, klines_15m)
        if signal:
            assert signal.strength >= 0.85

    def test_spike_only_confirmed(self):
        """仅冲高回落双确认 → strength=0.85"""
        detector = IgnitionDetector()
        spike_5m = self._build_spike_klines()
        spike_15m = self._build_spike_klines()
        signal = detector.detect(spike_5m, spike_15m)
        assert signal is not None
        assert signal.strength == 0.85
        assert signal.name == "ignition_signal"

    def test_single_timeframe_no_signal(self):
        """仅单周期触发不应产生信号"""
        detector = IgnitionDetector()
        spike_5m = self._build_spike_klines()
        normal_15m = make_normal_klines(10)
        signal = detector.detect(spike_5m, normal_15m)
        assert signal is None

    def test_no_signal_normal_market(self):
        """正常行情无信号"""
        detector = IgnitionDetector()
        normal_5m = make_normal_klines(10)
        normal_15m = make_normal_klines(10)
        signal = detector.detect(normal_5m, normal_15m)
        assert signal is None


# ============================================================
# has_any_ignition 快速接口测试
# ============================================================

class TestHasAnyIgnition:

    def test_returns_true_on_signal(self):
        detector = IgnitionDetector()
        klines = make_normal_klines(8, base_vol=1000.0)
        klines.append(make_kline(101.0, 105.0, 100.5, 100.5, 3000.0))
        klines.append(make_kline(100.5, 100.8, 100.3, 100.4, 300.0))
        assert detector.has_any_ignition(klines, klines) is True

    def test_returns_false_on_normal(self):
        detector = IgnitionDetector()
        normal = make_normal_klines(10)
        assert detector.has_any_ignition(normal, normal) is False


# ============================================================
# SignalEngine 集成测试
# ============================================================

class TestSignalEngineIntegration:

    def test_should_enter_require_ignition(self):
        """require_ignition=True 时无引爆信号应拒绝入场"""
        from strategies.signal_engine import Signal, SignalType
        engine = SignalEngine()
        # 构造 3 个普通信号，得分足够
        signals = [
            Signal("rsi_overbought", SignalType.TECHNICAL, 0.8, "SHORT", "test", 1.5),
            Signal("macd_death_cross", SignalType.TECHNICAL, 0.7, "SHORT", "test", 1.3),
            Signal("price_pullback", SignalType.PRICE_ACTION, 0.7, "SHORT", "test", 1.2),
        ]
        # 不要求引爆 → 可入场
        assert engine.should_enter(signals, min_score=0.1, min_signals=2) is True
        # 要求引爆 → 拒绝
        assert engine.should_enter(signals, min_score=0.1, min_signals=2,
                                   require_ignition=True) is False

    def test_should_enter_with_ignition(self):
        """有引爆信号时 require_ignition=True 应允许入场"""
        from strategies.signal_engine import Signal, SignalType
        engine = SignalEngine()
        signals = [
            Signal("rsi_overbought", SignalType.TECHNICAL, 0.8, "SHORT", "test", 1.5),
            Signal("macd_death_cross", SignalType.TECHNICAL, 0.7, "SHORT", "test", 1.3),
            Signal("ignition_signal", SignalType.VOLUME, 0.9, "SHORT", "test", 1.4),
        ]
        assert engine.should_enter(signals, min_score=0.1, min_signals=2,
                                   require_ignition=True) is True
