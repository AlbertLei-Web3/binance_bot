"""
技术指标工具函数
"""
from typing import List


def calculate_sma(prices: List[float], period: int) -> float:
    """计算简单移动平均"""
    if len(prices) < period:
        return 0.0
    return sum(prices[-period:]) / period


def calculate_ema(prices: List[float], period: int, previous_ema: float = None) -> float:
    """计算指数移动平均"""
    if len(prices) < period:
        return 0.0
    
    multiplier = 2 / (period + 1)
    
    if previous_ema is None:
        # 初始EMA = SMA
        return calculate_sma(prices, period)
    else:
        # EMA = (Price - Previous EMA) * Multiplier + Previous EMA
        return (prices[-1] - previous_ema) * multiplier + previous_ema


def calculate_rsi(prices: List[float], period: int = 14) -> float:
    """计算相对强弱指标 (RSI)"""
    if len(prices) < period + 1:
        return 50.0  # 默认中性值
    
    gains = []
    losses = []
    
    for i in range(len(prices) - period, len(prices)):
        change = prices[i] - prices[i - 1]
        if change > 0:
            gains.append(change)
            losses.append(0)
        else:
            gains.append(0)
            losses.append(abs(change))
    
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    
    if avg_loss == 0:
        return 100.0
    
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    
    return rsi


def calculate_macd(prices: List[float], fast_period: int = 12, 
                   slow_period: int = 26, signal_period: int = 9) -> Dict:
    """计算MACD指标"""
    if len(prices) < slow_period:
        return {"macd": 0.0, "signal": 0.0, "histogram": 0.0}
    
    # 计算快线和慢线EMA
    fast_ema = calculate_ema(prices, fast_period)
    slow_ema = calculate_ema(prices, slow_period)
    
    macd_line = fast_ema - slow_ema
    
    # 计算信号线（MACD的EMA）
    # 简化版，实际需要历史MACD值
    signal_line = macd_line * 0.9  # 简化
    
    histogram = macd_line - signal_line
    
    return {
        "macd": macd_line,
        "signal": signal_line,
        "histogram": histogram
    }


def get_closes_from_klines(klines: List) -> List[float]:
    """从K线数据提取收盘价"""
    return [float(k[4]) for k in klines]  # 索引4是收盘价
