"""
15分钟暴跌检测器 - 实时监控15分钟K线，检测跌幅 ≥ 5% 的暴跌信号
"""
from typing import Dict, List, Optional
from datetime import datetime
from core.market import get_klines
from utils.indicators import (
    get_closes_from_klines, get_opens_from_klines, get_highs_from_klines,
    get_lows_from_klines, get_volumes_from_klines,
)
from utils.logger import setup_logger

logger = setup_logger("signal_15m")


class Signal15M:
    """
    15分钟暴跌信号检测器

    核心逻辑：
    - 跌幅 ≥ 5% 触发
    - 放量确认（≥ 1.5x）
    - 实体占比 ≥ 50%
    """

    # 默认阈值
    DEFAULT_CRASH_THRESHOLD = 0.05      # 5% 跌幅
    DEFAULT_VOLUME_RATIO_MIN = 1.5      # 1.5 倍放量
    DEFAULT_BODY_RATIO_MIN = 0.5        # 50% 实体占比

    def __init__(self, config: Dict = None):
        """
        初始化15分钟信号检测器

        Args:
            config: 配置字典
        """
        self.config = config or {}
        signal_cfg = self.config.get("signal_15m", {})

        self.crash_threshold = signal_cfg.get("crash_threshold", self.DEFAULT_CRASH_THRESHOLD)
        self.volume_ratio_min = signal_cfg.get("volume_ratio_min", self.DEFAULT_VOLUME_RATIO_MIN)
        self.body_ratio_min = signal_cfg.get("body_ratio_min", self.DEFAULT_BODY_RATIO_MIN)

    def detect_crash(self, symbol: str) -> Optional[Dict]:
        """
        检测暴跌信号

        Args:
            symbol: 交易对

        Returns:
            暴跌信号详情，未触发返回 None
        """
        try:
            klines = get_klines(symbol, interval="15m", limit=30)
            if not klines or len(klines) < 10:
                return None

            opens = get_opens_from_klines(klines)
            closes = get_closes_from_klines(klines)
            highs = get_highs_from_klines(klines)
            lows = get_lows_from_klines(klines)
            volumes = get_volumes_from_klines(klines)

            # 分析最新一根 K 线
            result = self._analyze_candle(
                opens[-1], closes[-1], highs[-1], lows[-1], volumes[-1],
                volumes[-10:-1]  # 前10根K线的成交量
            )

            if result:
                result["symbol"] = symbol
                result["timestamp"] = datetime.now().isoformat()
                logger.info(
                    f"⚠️ {symbol} 暴跌信号: 跌幅={result['drop_pct']:.2%}, "
                    f"放量={result['volume_ratio']:.1f}x"
                )

            return result

        except Exception as e:
            logger.debug(f"{symbol} 暴跌检测失败: {e}")
            return None

    def _analyze_candle(self, open_price: float, close_price: float,
                        high: float, low: float, volume: float,
                        prev_volumes: List[float]) -> Optional[Dict]:
        """
        分析单根 K 线

        Args:
            open_price: 开盘价
            close_price: 收盘价
            high: 最高价
            low: 最低价
            volume: 成交量
            prev_volumes: 前几根K线的成交量列表

        Returns:
            暴跌信号详情或 None
        """
        # 必须是阴线
        if close_price >= open_price:
            return None

        # 计算跌幅
        drop_pct = (open_price - close_price) / open_price
        if drop_pct < self.crash_threshold:
            return None

        # 计算实体占比
        body = abs(close_price - open_price)
        full_range = high - low
        body_ratio = body / full_range if full_range > 0 else 0
        if body_ratio < self.body_ratio_min:
            return None

        # 计算放量倍数
        avg_volume = sum(prev_volumes) / len(prev_volumes) if prev_volumes else volume
        volume_ratio = volume / avg_volume if avg_volume > 0 else 1
        if volume_ratio < self.volume_ratio_min:
            return None

        # 触发暴跌信号
        return {
            "is_crash": True,
            "open_price": open_price,
            "close_price": close_price,
            "high": high,
            "low": low,
            "drop_pct": round(drop_pct, 4),
            "body_ratio": round(body_ratio, 4),
            "volume_ratio": round(volume_ratio, 2),
            "volume": volume,
            "avg_volume": avg_volume,
        }

    def scan_symbols(self, symbols: List[str]) -> List[Dict]:
        """
        批量扫描多个币种

        Args:
            symbols: 交易对列表

        Returns:
            触发暴跌信号的币种列表
        """
        signals = []
        for symbol in symbols:
            result = self.detect_crash(symbol)
            if result:
                signals.append(result)
        return signals

    def get_signal_strength(self, signal: Dict) -> float:
        """
        计算信号强度（0.0 - 1.0）

        Args:
            signal: 暴跌信号

        Returns:
            信号强度
        """
        if not signal or not signal.get("is_crash"):
            return 0.0

        drop_pct = signal.get("drop_pct", 0)
        volume_ratio = signal.get("volume_ratio", 0)
        body_ratio = signal.get("body_ratio", 0)

        # 跌幅得分：5% = 0.5, 8% = 0.8, 10%+ = 1.0
        drop_score = min(drop_pct / 0.10, 1.0)

        # 放量得分：1.5x = 0.5, 2x = 0.7, 3x+ = 1.0
        vol_score = min((volume_ratio - 1) / 2, 1.0)

        # 实体得分：0.5 = 0.5, 0.7 = 0.7, 0.9+ = 1.0
        body_score = min(body_ratio / 0.9, 1.0)

        # 加权平均
        strength = drop_score * 0.5 + vol_score * 0.3 + body_score * 0.2
        return round(strength, 2)
