"""
多周期分析器 - 分析日K、4H、1H、30M、15M 多周期数据
"""
from typing import Dict, List, Optional
from core.market import get_klines
from utils.indicators import (
    get_closes_from_klines, get_highs_from_klines, get_lows_from_klines,
    get_opens_from_klines, get_volumes_from_klines,
    calculate_rsi_series, calculate_bollinger_bands, calculate_ema_series,
    calculate_volume_ratio,
)
from utils.logger import setup_logger

logger = setup_logger("multi_timeframe")


class MultiTimeframeAnalyzer:
    """
    多周期分析器

    分析维度：
    - 日K（1d）：霸榜天数、累计涨幅、高位滞涨
    - 4H：高位滞涨、顶部形态
    - 1H：RSI 超买、布林带位置
    - 30M：量价背离
    - 15M：暴跌信号（核心）
    """

    def __init__(self, config: Dict = None):
        """
        初始化多周期分析器

        Args:
            config: 配置字典，包含技术指标阈值
        """
        self.config = config or {}
        indicators_cfg = self.config.get("indicators", {})
        self.rsi_overbought = indicators_cfg.get("rsi_overbought", 70)
        self.rsi_extreme = indicators_cfg.get("rsi_extreme", 80)

    def analyze(self, symbol: str, pump_days: int = 0, total_gain: float = 0) -> Dict:
        """
        分析指定币种的多周期数据

        Args:
            symbol: 交易对
            pump_days: 霸榜天数
            total_gain: 累计涨幅

        Returns:
            多周期分析结果
        """
        result = {
            "symbol": symbol,
            "daily": self._analyze_daily(symbol, pump_days, total_gain),
            "4h": self._analyze_4h(symbol),
            "1h": self._analyze_1h(symbol),
            "30m": self._analyze_30m(symbol),
            "15m": self._analyze_15m(symbol),
        }
        return result

    def _analyze_daily(self, symbol: str, pump_days: int, total_gain: float) -> Dict:
        """分析日线"""
        try:
            klines = get_klines(symbol, interval="1d", limit=30)
            if not klines or len(klines) < 10:
                return {"error": "数据不足"}

            closes = get_closes_from_klines(klines)
            highs = get_highs_from_klines(klines)
            lows = get_lows_from_klines(klines)

            # 计算涨幅
            recent_high = max(highs[-7:])  # 近7日最高
            recent_low = min(lows[-7:])    # 近7日最低
            current_price = closes[-1]

            # 检查高位滞涨
            stagnation = self._check_stagnation(highs, closes)

            return {
                "pump_days": pump_days,
                "total_gain": total_gain,
                "current_price": current_price,
                "recent_high": recent_high,
                "recent_low": recent_low,
                "stagnation": stagnation,
                "stagnation_days": stagnation.get("days", 0) if stagnation else 0,
            }
        except Exception as e:
            logger.debug(f"{symbol} 日线分析失败: {e}")
            return {"error": str(e)}

    def _analyze_4h(self, symbol: str) -> Dict:
        """分析 4 小时线"""
        try:
            klines = get_klines(symbol, interval="4h", limit=50)
            if not klines or len(klines) < 20:
                return {"error": "数据不足"}

            closes = get_closes_from_klines(klines)
            highs = get_highs_from_klines(klines)
            opens = get_opens_from_klines(klines)

            # 检查顶部形态
            top_pattern = self._check_top_pattern(highs, closes)

            # 检查高位滞涨
            stagnation = self._check_stagnation(highs, closes, lookback=6)

            return {
                "top_pattern": top_pattern,
                "stagnation": stagnation,
                "trend": self._get_trend(closes),
            }
        except Exception as e:
            logger.debug(f"{symbol} 4H 分析失败: {e}")
            return {"error": str(e)}

    def _analyze_1h(self, symbol: str) -> Dict:
        """分析 1 小时线 - RSI 和布林带"""
        try:
            klines = get_klines(symbol, interval="1h", limit=100)
            if not klines or len(klines) < 30:
                return {"error": "数据不足"}

            closes = get_closes_from_klines(klines)

            # RSI
            rsi_values = calculate_rsi_series(closes, 14)
            current_rsi = rsi_values[-1] if rsi_values else 50

            # 布林带
            bb_data = calculate_bollinger_bands(closes, 20, 2)
            upper_bb = bb_data.get("upper", [])[-1] if bb_data.get("upper") else 0
            middle_bb = bb_data.get("middle", [])[-1] if bb_data.get("middle") else 0
            current_price = closes[-1]

            # 布林带位置
            above_upper_bb = current_price >= upper_bb if upper_bb > 0 else False
            bb_position = "above_upper" if above_upper_bb else (
                "near_upper" if current_price >= upper_bb * 0.98 else "normal"
            )

            return {
                "rsi": round(current_rsi, 2),
                "rsi_overbought": current_rsi >= self.rsi_overbought,
                "rsi_extreme": current_rsi >= self.rsi_extreme,
                "upper_bb": round(upper_bb, 6),
                "middle_bb": round(middle_bb, 6),
                "current_price": current_price,
                "above_upper_bb": above_upper_bb,
                "bb_position": bb_position,
            }
        except Exception as e:
            logger.debug(f"{symbol} 1H 分析失败: {e}")
            return {"error": str(e)}

    def _analyze_30m(self, symbol: str) -> Dict:
        """分析 30 分钟线 - 量价背离"""
        try:
            klines = get_klines(symbol, interval="30m", limit=50)
            if not klines or len(klines) < 20:
                return {"error": "数据不足"}

            closes = get_closes_from_klines(klines)
            volumes = get_volumes_from_klines(klines)

            # 检查量价背离
            divergence = self._check_volume_divergence(closes, volumes)

            return {
                "volume_divergence": divergence,
                "trend": self._get_trend(closes),
            }
        except Exception as e:
            logger.debug(f"{symbol} 30M 分析失败: {e}")
            return {"error": str(e)}

    def _analyze_15m(self, symbol: str) -> Dict:
        """分析 15 分钟线 - 暴跌信号"""
        try:
            klines = get_klines(symbol, interval="15m", limit=50)
            if not klines or len(klines) < 10:
                return {"error": "数据不足"}

            opens = get_opens_from_klines(klines)
            closes = get_closes_from_klines(klines)
            highs = get_highs_from_klines(klines)
            lows = get_lows_from_klines(klines)
            volumes = get_volumes_from_klines(klines)

            # 计算最新一根 K 线的跌幅
            current_open = opens[-1]
            current_close = closes[-1]
            current_high = highs[-1]
            current_low = lows[-1]
            current_volume = volumes[-1]

            # 跌幅计算
            drop_pct = 0
            if current_open > 0:
                drop_pct = (current_open - current_close) / current_open

            # 实体占比
            body = abs(current_close - current_open)
            full_range = current_high - current_low
            body_ratio = body / full_range if full_range > 0 else 0

            # 放量倍数
            avg_volume = sum(volumes[-10:-1]) / 9 if len(volumes) > 1 else current_volume
            volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1

            # 判断是否暴跌
            signal_cfg = self.config.get("signal_15m", {})
            crash_threshold = signal_cfg.get("crash_threshold", 0.05)
            volume_ratio_min = signal_cfg.get("volume_ratio_min", 1.5)

            is_crash = (
                drop_pct >= crash_threshold and
                volume_ratio >= volume_ratio_min and
                current_close < current_open  # 确保是阴线
            )

            return {
                "drop_pct": round(drop_pct, 4),
                "body_ratio": round(body_ratio, 4),
                "volume_ratio": round(volume_ratio, 2),
                "is_crash": is_crash,
                "current_price": current_close,
                "current_open": current_open,
                "current_high": current_high,
                "current_low": current_low,
            }
        except Exception as e:
            logger.debug(f"{symbol} 15M 分析失败: {e}")
            return {"error": str(e)}

    def _check_stagnation(self, highs: List[float], closes: List[float],
                          lookback: int = 4) -> Optional[Dict]:
        """检查高位滞涨"""
        if len(highs) < lookback + 1:
            return None

        recent_highs = highs[-lookback:]
        prev_high = max(highs[-(lookback + 5):-lookback]) if len(highs) > lookback + 5 else max(highs[:-lookback])

        # 检查是否连续未创新高
        no_new_high_count = sum(1 for h in recent_highs if h < prev_high)

        if no_new_high_count >= lookback - 1:
            return {
                "detected": True,
                "days": lookback,
                "prev_high": prev_high,
                "current_high": max(recent_highs),
            }
        return None

    def _check_top_pattern(self, highs: List[float], closes: List[float]) -> Optional[Dict]:
        """检查顶部形态（M头、头肩顶等）"""
        if len(highs) < 20:
            return None

        # 简化：检查双顶
        recent = highs[-20:]
        max_val = max(recent)
        max_idx = recent.index(max_val)

        # 检查是否有两个接近的高点
        for i, h in enumerate(recent):
            if i != max_idx and abs(h - max_val) / max_val < 0.02:  # 差异 < 2%
                return {
                    "type": "double_top",
                    "high1": max_val,
                    "high2": h,
                }
        return None

    def _check_volume_divergence(self, closes: List[float], volumes: List[float]) -> Optional[Dict]:
        """检查量价背离"""
        if len(closes) < 10 or len(volumes) < 10:
            return None

        recent_closes = closes[-5:]
        recent_volumes = volumes[-5:]
        prev_volumes = volumes[-10:-5]

        price_rising = recent_closes[-1] > recent_closes[0]
        avg_recent_vol = sum(recent_volumes) / len(recent_volumes)
        avg_prev_vol = sum(prev_volumes) / len(prev_volumes)

        if avg_prev_vol == 0:
            return None

        vol_ratio = avg_recent_vol / avg_prev_vol

        # 上涨缩量
        if price_rising and vol_ratio < 0.7:
            return {
                "type": "rising_shrink",
                "vol_ratio": round(vol_ratio, 2),
            }

        # 下跌放量
        if not price_rising and vol_ratio > 1.5:
            return {
                "type": "falling_expand",
                "vol_ratio": round(vol_ratio, 2),
            }

        return None

    def _get_trend(self, closes: List[float]) -> str:
        """判断趋势"""
        if len(closes) < 5:
            return "unknown"

        recent = closes[-5:]
        if recent[-1] > recent[0] * 1.02:
            return "up"
        elif recent[-1] < recent[0] * 0.98:
            return "down"
        else:
            return "sideways"
