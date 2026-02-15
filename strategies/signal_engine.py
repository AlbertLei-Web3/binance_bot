"""
信号引擎 - 多重确认信号检测与加权评分系统
用于山寨币做空策略的入场时机判断
"""
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional

from utils.indicators import (
    get_closes_from_klines, get_highs_from_klines, get_lows_from_klines,
    get_opens_from_klines, get_volumes_from_klines,
    calculate_ema_series, calculate_rsi_series, calculate_macd,
    calculate_bollinger_bands, calculate_atr, calculate_volume_ratio,
    detect_rsi_divergence,
)


class SignalType(Enum):
    """信号类型"""
    TECHNICAL = "TECHNICAL"        # 技术指标
    PRICE_ACTION = "PRICE_ACTION"  # 价格行为
    VOLUME = "VOLUME"              # 成交量


@dataclass
class Signal:
    """单个信号"""
    name: str
    signal_type: SignalType
    strength: float          # 0.0 - 1.0
    direction: str           # "SHORT" / "LONG"
    description: str
    weight: float = 1.0      # 评分权重


# 信号权重配置（做空方向）
SHORT_SIGNAL_WEIGHTS = {
    "rsi_overbought":    1.5,   # RSI 超买 + 顶背离（高权重）
    "macd_death_cross":  1.3,   # MACD 死叉
    "price_below_ema":   1.0,   # 跌破 EMA
    "bearish_candle":    1.0,   # 大阴线/长上影线
    "price_pullback":    1.2,   # 从高点回落
    "failed_new_high":   1.1,   # 无法创新高
    "volume_divergence": 1.3,   # 量价背离
}


class SignalEngine:
    """
    信号引擎：分析 K 线数据，生成做空信号列表并评分
    """

    def __init__(self, weights: Dict[str, float] = None):
        self.weights = weights or SHORT_SIGNAL_WEIGHTS

    # ----------------------------------------------------------
    # 公开接口
    # ----------------------------------------------------------

    def analyze(self, klines: List, current_price: float) -> List[Signal]:
        """分析所有信号，返回触发的信号列表"""
        closes = get_closes_from_klines(klines)
        opens = get_opens_from_klines(klines)
        highs = get_highs_from_klines(klines)
        lows = get_lows_from_klines(klines)
        volumes = get_volumes_from_klines(klines)

        if len(closes) < 30:
            return []

        rsi_values = calculate_rsi_series(closes, 14)
        macd_data = calculate_macd(closes)
        ema20 = calculate_ema_series(closes, 20)
        ema50 = calculate_ema_series(closes, 50)

        signals: List[Signal] = []

        checkers = [
            self._check_rsi_overbought(closes, rsi_values),
            self._check_macd_death_cross(macd_data),
            self._check_price_below_ema(closes, current_price, ema20, ema50),
            self._check_bearish_candle(opens, closes, highs, lows),
            self._check_price_pullback(highs, current_price),
            self._check_failed_new_high(highs),
            self._check_volume_divergence(closes, volumes),
        ]

        for sig in checkers:
            if sig is not None:
                sig.weight = self.weights.get(sig.name, 1.0)
                signals.append(sig)

        return signals

    def get_signal_score(self, signals: List[Signal]) -> float:
        """
        计算综合信号评分（加权平均）
        返回 0.0 - 1.0
        """
        if not signals:
            return 0.0
        total_weight = sum(s.weight for s in signals)
        weighted_sum = sum(s.strength * s.weight for s in signals)
        # 归一化：除以所有可能信号的总权重
        max_weight = sum(self.weights.values())
        return weighted_sum / max_weight if max_weight > 0 else 0.0

    def should_enter(self, signals: List[Signal],
                     min_score: float = 0.6,
                     min_signals: int = 3) -> bool:
        """是否满足入场条件"""
        if len(signals) < min_signals:
            return False
        return self.get_signal_score(signals) >= min_score


    # ----------------------------------------------------------
    # 信号检测方法（做空方向）
    # ----------------------------------------------------------

    def _check_rsi_overbought(self, closes: List[float],
                               rsi_values: List[float]) -> Optional[Signal]:
        """RSI ≥ 70 且出现顶背离"""
        if len(rsi_values) < 14:
            return None

        current_rsi = rsi_values[-1]
        if current_rsi < 70:
            return None

        divergence = detect_rsi_divergence(closes, rsi_values, lookback=10)
        has_divergence = divergence == "bearish_divergence"

        # RSI ≥ 70 基础强度 0.6，有顶背离提升到 0.9
        strength = 0.9 if has_divergence else 0.6
        desc = f"RSI={current_rsi:.1f}"
        if has_divergence:
            desc += "，顶背离确认"

        return Signal(
            name="rsi_overbought",
            signal_type=SignalType.TECHNICAL,
            strength=strength,
            direction="SHORT",
            description=desc,
        )

    def _check_macd_death_cross(self, macd_data: Dict) -> Optional[Signal]:
        """MACD 死叉（MACD 线跌破信号线，柱状图转负）"""
        macd_line = macd_data.get("macd_line", [])
        signal_line = macd_data.get("signal_line", [])
        histogram = macd_data.get("histogram", [])

        if len(histogram) < 3:
            return None

        # 当前柱状图为负，且前一根为正或零（刚发生死叉）
        if histogram[-1] >= 0:
            return None

        just_crossed = histogram[-2] >= 0
        strength = 0.8 if just_crossed else 0.5

        return Signal(
            name="macd_death_cross",
            signal_type=SignalType.TECHNICAL,
            strength=strength,
            direction="SHORT",
            description=f"MACD死叉，柱状图={histogram[-1]:.4f}",
        )

    def _check_price_below_ema(self, closes: List[float], current_price: float,
                                ema20: List[float],
                                ema50: List[float]) -> Optional[Signal]:
        """价格跌破 EMA20 或 EMA50"""
        below_ema20 = ema20[-1] > 0 and current_price < ema20[-1]
        below_ema50 = ema50[-1] > 0 and current_price < ema50[-1]

        if not below_ema20 and not below_ema50:
            return None

        if below_ema20 and below_ema50:
            strength = 0.9
            desc = "价格跌破EMA20和EMA50"
        elif below_ema20:
            strength = 0.6
            desc = f"价格跌破EMA20({ema20[-1]:.2f})"
        else:
            strength = 0.7
            desc = f"价格跌破EMA50({ema50[-1]:.2f})"

        return Signal(
            name="price_below_ema",
            signal_type=SignalType.TECHNICAL,
            strength=strength,
            direction="SHORT",
            description=desc,
        )


    def _check_bearish_candle(self, opens: List[float], closes: List[float],
                               highs: List[float],
                               lows: List[float]) -> Optional[Signal]:
        """大阴线或长上影线"""
        if len(closes) < 2:
            return None

        o, c, h, l = opens[-1], closes[-1], highs[-1], lows[-1]
        body = abs(c - o)
        full_range = h - l
        if full_range == 0:
            return None

        is_bearish_body = c < o and body / full_range > 0.6
        upper_shadow = h - max(o, c)
        is_long_upper = upper_shadow / full_range > 0.5

        if not is_bearish_body and not is_long_upper:
            return None

        if is_bearish_body and is_long_upper:
            strength = 0.85
            desc = "大阴线+长上影线"
        elif is_bearish_body:
            strength = 0.7
            desc = f"大阴线（实体占比{body / full_range:.0%}）"
        else:
            strength = 0.65
            desc = f"长上影线（上影占比{upper_shadow / full_range:.0%}）"

        return Signal(
            name="bearish_candle",
            signal_type=SignalType.PRICE_ACTION,
            strength=strength,
            direction="SHORT",
            description=desc,
        )

    def _check_price_pullback(self, highs: List[float],
                               current_price: float) -> Optional[Signal]:
        """价格从近期高点回落 5%-10%+"""
        if len(highs) < 10:
            return None

        recent_high = max(highs[-20:]) if len(highs) >= 20 else max(highs)
        if recent_high == 0:
            return None

        pullback_pct = (recent_high - current_price) / recent_high

        if pullback_pct < 0.05:
            return None

        # 回落 5%-10% 强度 0.6-0.8，>10% 强度 0.9
        if pullback_pct >= 0.10:
            strength = 0.9
        else:
            strength = 0.6 + (pullback_pct - 0.05) * 4  # 线性插值

        return Signal(
            name="price_pullback",
            signal_type=SignalType.PRICE_ACTION,
            strength=min(strength, 1.0),
            direction="SHORT",
            description=f"从高点{recent_high:.2f}回落{pullback_pct:.1%}",
        )

    def _check_failed_new_high(self, highs: List[float]) -> Optional[Signal]:
        """连续多根 K 线无法创新高"""
        if len(highs) < 6:
            return None

        # 检查最近 5 根 K 线是否都低于之前的最高点
        peak = max(highs[:-5]) if len(highs) > 5 else max(highs[:1])
        recent = highs[-5:]
        failed_count = sum(1 for h in recent if h < peak)

        if failed_count < 4:
            return None

        strength = 0.7 if failed_count == 4 else 0.85
        return Signal(
            name="failed_new_high",
            signal_type=SignalType.PRICE_ACTION,
            strength=strength,
            direction="SHORT",
            description=f"连续{failed_count}根K线未创新高",
        )


    def _check_volume_divergence(self, closes: List[float],
                                  volumes: List[float]) -> Optional[Signal]:
        """
        量价背离：
        - 上涨时成交量萎缩（上涨乏力）
        - 下跌时成交量放大（确认反转）
        """
        if len(closes) < 10 or len(volumes) < 10:
            return None

        # 最近 5 根 K 线的价格方向和成交量趋势
        recent_closes = closes[-5:]
        recent_volumes = volumes[-5:]
        prev_volumes = volumes[-10:-5]

        price_rising = recent_closes[-1] > recent_closes[0]
        avg_recent_vol = sum(recent_volumes) / len(recent_volumes)
        avg_prev_vol = sum(prev_volumes) / len(prev_volumes)

        if avg_prev_vol == 0:
            return None

        vol_change = avg_recent_vol / avg_prev_vol

        # 上涨缩量：价格上涨但成交量萎缩
        if price_rising and vol_change < 0.7:
            return Signal(
                name="volume_divergence",
                signal_type=SignalType.VOLUME,
                strength=0.75,
                direction="SHORT",
                description=f"上涨缩量（量比{vol_change:.2f}）",
            )

        # 下跌放量：价格下跌且成交量放大
        if not price_rising and vol_change > 1.5:
            return Signal(
                name="volume_divergence",
                signal_type=SignalType.VOLUME,
                strength=0.8,
                direction="SHORT",
                description=f"下跌放量（量比{vol_change:.2f}）",
            )

        return None
