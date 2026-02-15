"""
技术指标工具函数
"""
from typing import Dict, List, Optional
import math


# ============================================================
# K线数据提取
# ============================================================

def get_closes_from_klines(klines: List) -> List[float]:
    """从K线数据提取收盘价"""
    return [float(k[4]) for k in klines]


def get_opens_from_klines(klines: List) -> List[float]:
    """从K线数据提取开盘价"""
    return [float(k[1]) for k in klines]


def get_highs_from_klines(klines: List) -> List[float]:
    """从K线数据提取最高价"""
    return [float(k[2]) for k in klines]


def get_lows_from_klines(klines: List) -> List[float]:
    """从K线数据提取最低价"""
    return [float(k[3]) for k in klines]


def get_volumes_from_klines(klines: List) -> List[float]:
    """从K线数据提取成交量"""
    return [float(k[5]) for k in klines]


# ============================================================
# 移动平均
# ============================================================

def calculate_sma(prices: List[float], period: int) -> float:
    """计算简单移动平均"""
    if len(prices) < period:
        return 0.0
    return sum(prices[-period:]) / period


def calculate_ema(prices: List[float], period: int, previous_ema: float = None) -> float:
    """计算指数移动平均（返回最新值）"""
    if len(prices) < period:
        return 0.0
    if previous_ema is None:
        return calculate_sma(prices[:period], period)
    multiplier = 2 / (period + 1)
    return (prices[-1] - previous_ema) * multiplier + previous_ema


def calculate_ema_series(prices: List[float], period: int) -> List[float]:
    """
    计算完整 EMA 序列
    返回与 prices 等长的列表，前 period-1 个值为 0.0
    """
    if len(prices) < period:
        return [0.0] * len(prices)

    result = [0.0] * len(prices)
    # 初始 EMA = 前 period 个价格的 SMA
    result[period - 1] = sum(prices[:period]) / period
    multiplier = 2 / (period + 1)

    for i in range(period, len(prices)):
        result[i] = (prices[i] - result[i - 1]) * multiplier + result[i - 1]

    return result


# ============================================================
# RSI
# ============================================================

def calculate_rsi(prices: List[float], period: int = 14) -> float:
    """计算 RSI（返回最新值）"""
    series = calculate_rsi_series(prices, period)
    return series[-1] if series else 50.0


def calculate_rsi_series(prices: List[float], period: int = 14) -> List[float]:
    """
    计算完整 RSI 序列（Wilder 平滑法）
    返回与 prices 等长的列表，前 period 个值为 50.0
    """
    n = len(prices)
    if n < period + 1:
        return [50.0] * n

    result = [50.0] * n

    # 第一段：用简单平均初始化
    gains = []
    losses = []
    for i in range(1, period + 1):
        change = prices[i] - prices[i - 1]
        gains.append(max(change, 0))
        losses.append(max(-change, 0))

    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period

    if avg_loss == 0:
        result[period] = 100.0
    else:
        rs = avg_gain / avg_loss
        result[period] = 100 - (100 / (1 + rs))

    # 后续：Wilder 平滑
    for i in range(period + 1, n):
        change = prices[i] - prices[i - 1]
        gain = max(change, 0)
        loss = max(-change, 0)

        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period

        if avg_loss == 0:
            result[i] = 100.0
        else:
            rs = avg_gain / avg_loss
            result[i] = 100 - (100 / (1 + rs))

    return result


# ============================================================
# MACD（修复：基于完整 EMA 序列计算）
# ============================================================

def calculate_macd(prices: List[float], fast_period: int = 12,
                   slow_period: int = 26, signal_period: int = 9) -> Dict:
    """
    计算 MACD 指标（返回完整序列）

    Returns:
        {
            "macd_line": List[float],      # MACD 线序列
            "signal_line": List[float],    # 信号线序列
            "histogram": List[float],      # 柱状图序列
            "macd": float,                 # 最新 MACD 值
            "signal": float,               # 最新信号线值
            "histogram_latest": float      # 最新柱状图值
        }
    """
    n = len(prices)
    if n < slow_period:
        return {
            "macd_line": [], "signal_line": [], "histogram": [],
            "macd": 0.0, "signal": 0.0, "histogram_latest": 0.0
        }

    fast_ema = calculate_ema_series(prices, fast_period)
    slow_ema = calculate_ema_series(prices, slow_period)

    # MACD 线 = 快线 EMA - 慢线 EMA
    macd_line = [0.0] * n
    for i in range(slow_period - 1, n):
        macd_line[i] = fast_ema[i] - slow_ema[i]

    # 信号线 = MACD 线的 EMA
    valid_macd = macd_line[slow_period - 1:]
    signal_series = calculate_ema_series(valid_macd, signal_period)

    signal_line = [0.0] * n
    for i, val in enumerate(signal_series):
        signal_line[slow_period - 1 + i] = val

    # 柱状图 = MACD 线 - 信号线
    histogram = [macd_line[i] - signal_line[i] for i in range(n)]

    return {
        "macd_line": macd_line,
        "signal_line": signal_line,
        "histogram": histogram,
        "macd": macd_line[-1],
        "signal": signal_line[-1],
        "histogram_latest": histogram[-1]
    }


# ============================================================
# 布林带
# ============================================================

def calculate_bollinger_bands(prices: List[float], period: int = 20,
                              std_dev: float = 2.0) -> Dict:
    """
    计算布林带

    Returns:
        {"upper": float, "middle": float, "lower": float, "bandwidth": float}
    """
    if len(prices) < period:
        return {"upper": 0.0, "middle": 0.0, "lower": 0.0, "bandwidth": 0.0}

    window = prices[-period:]
    middle = sum(window) / period
    variance = sum((p - middle) ** 2 for p in window) / period
    std = math.sqrt(variance)

    upper = middle + std_dev * std
    lower = middle - std_dev * std
    bandwidth = (upper - lower) / middle if middle > 0 else 0.0

    return {"upper": upper, "middle": middle, "lower": lower, "bandwidth": bandwidth}


# ============================================================
# ATR（平均真实波幅）
# ============================================================

def calculate_atr(klines: List, period: int = 14) -> float:
    """
    计算 ATR（基于 K 线的 high/low/close）

    Args:
        klines: K线数据列表
        period: ATR 周期
    """
    if len(klines) < period + 1:
        return 0.0

    highs = get_highs_from_klines(klines)
    lows = get_lows_from_klines(klines)
    closes = get_closes_from_klines(klines)

    true_ranges = []
    for i in range(1, len(klines)):
        tr = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1])
        )
        true_ranges.append(tr)

    if len(true_ranges) < period:
        return 0.0

    # Wilder 平滑
    atr = sum(true_ranges[:period]) / period
    for i in range(period, len(true_ranges)):
        atr = (atr * (period - 1) + true_ranges[i]) / period

    return atr


# ============================================================
# 成交量分析
# ============================================================

def calculate_volume_ratio(klines: List, period: int = 20) -> float:
    """
    计算量比：最新一根 K 线成交量 / 过去 N 根平均成交量
    >1 放量，<1 缩量
    """
    volumes = get_volumes_from_klines(klines)
    if len(volumes) < period + 1:
        return 1.0

    avg_vol = sum(volumes[-(period + 1):-1]) / period
    if avg_vol == 0:
        return 1.0
    return volumes[-1] / avg_vol


# ============================================================
# RSI 背离检测
# ============================================================

def detect_rsi_divergence(prices: List[float], rsi_values: List[float],
                          lookback: int = 10) -> str:
    """
    检测 RSI 背离

    - bearish_divergence（顶背离）：价格创新高，RSI 未创新高
    - bullish_divergence（底背离）：价格创新低，RSI 未创新低
    - none：无背离

    Args:
        prices: 价格序列
        rsi_values: RSI 序列（与 prices 等长）
        lookback: 回看周期
    """
    if len(prices) < lookback or len(rsi_values) < lookback:
        return "none"

    recent_prices = prices[-lookback:]
    recent_rsi = rsi_values[-lookback:]

    # 找价格和 RSI 的局部高点/低点
    price_high_idx = recent_prices.index(max(recent_prices))
    price_low_idx = recent_prices.index(min(recent_prices))

    # 顶背离：最新价格接近或超过区间高点，但 RSI 低于对应高点时的 RSI
    current_price = recent_prices[-1]
    current_rsi = recent_rsi[-1]
    peak_price = recent_prices[price_high_idx]
    peak_rsi = recent_rsi[price_high_idx]

    # 价格在高点附近（95%以上）且 RSI 明显低于高点时的 RSI
    if (current_price >= peak_price * 0.95
            and price_high_idx < lookback - 1
            and current_rsi < peak_rsi - 5):
        return "bearish_divergence"

    # 底背离：价格在低点附近，但 RSI 高于低点时的 RSI
    trough_price = recent_prices[price_low_idx]
    trough_rsi = recent_rsi[price_low_idx]

    if (current_price <= trough_price * 1.05
            and price_low_idx < lookback - 1
            and current_rsi > trough_rsi + 5):
        return "bullish_divergence"

    return "none"
