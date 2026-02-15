"""
引爆信号检测器
检测 5m/15m K线上的剧烈波动形态，作为做空入场的短周期确认信号

两种形态：
1. 冲高回落（spike_and_drop）：长上影线 + 放量 + 后续缩量
2. 放量暴跌（volume_crash）：大阴线放量 或 连续阴线累计跌幅达标
"""
from dataclasses import dataclass
from typing import Dict, List, Optional

from utils.indicators import (
    get_opens_from_klines, get_closes_from_klines,
    get_highs_from_klines, get_lows_from_klines,
    get_volumes_from_klines,
)
from utils.logger import setup_logger

logger = setup_logger("ignition_detector")


@dataclass
class IgnitionResult:
    """引爆检测结果（不依赖 signal_engine，避免循环导入）"""
    strength: float
    description: str


# 默认阈值配置（5m 更灵敏，15m 更宽松）
DEFAULT_IGNITION_CONFIG = {
    "5m": {
        "spike_upper_shadow_ratio": 1.5,   # 上影线 >= 实体 N 倍
        "spike_surge_pct": 0.015,           # 冲高幅度 >= 1.5%
        "spike_volume_ratio": 2.0,          # 放量倍数
        "spike_shrink_ratio": 0.6,          # 后续缩量比
        "crash_drop_pct": 0.015,            # 单根阴线跌幅
        "crash_body_ratio": 0.6,            # 实体占比
        "crash_volume_ratio": 2.0,          # 放量倍数
        "crash_consecutive_drop_pct": 0.02, # 连续阴线累计跌幅
        "crash_consecutive_count": 3,       # 连续阴线根数
    },
    "15m": {
        "spike_upper_shadow_ratio": 1.5,
        "spike_surge_pct": 0.025,
        "spike_volume_ratio": 2.0,
        "spike_shrink_ratio": 0.6,
        "crash_drop_pct": 0.025,
        "crash_body_ratio": 0.6,
        "crash_volume_ratio": 2.0,
        "crash_consecutive_drop_pct": 0.035,
        "crash_consecutive_count": 3,
    },
    "weight": 1.4,
}

class IgnitionDetector:
    """引爆信号检测器：5m + 15m 双周期确认"""

    def __init__(self, config: Dict = None):
        merged = {**DEFAULT_IGNITION_CONFIG, **(config or {})}
        self.cfg_5m: Dict = merged["5m"]
        self.cfg_15m: Dict = merged["15m"]
        self.weight: float = merged.get("weight", 1.4)

    # ----------------------------------------------------------
    # 公开接口
    # ----------------------------------------------------------

    def detect(self, klines_5m: List, klines_15m: List) -> Optional[IgnitionResult]:
        """
        主入口：双周期确认检测

        同一形态在 5m 和 15m 都检测到才算触发。
        - 两种形态都触发 → strength=0.95
        - 仅冲高回落 → strength=0.85
        - 仅放量暴跌 → strength=0.90
        """
        spike_5m = self._detect_spike_and_drop(klines_5m, self.cfg_5m)
        spike_15m = self._detect_spike_and_drop(klines_15m, self.cfg_15m)
        crash_5m = self._detect_volume_crash(klines_5m, self.cfg_5m)
        crash_15m = self._detect_volume_crash(klines_15m, self.cfg_15m)

        # 双周期确认：同一形态在两个周期都出现
        spike_confirmed = spike_5m and spike_15m
        crash_confirmed = crash_5m and crash_15m

        if not spike_confirmed and not crash_confirmed:
            return None

        if spike_confirmed and crash_confirmed:
            strength = 0.95
            desc = "引爆信号：冲高回落+放量暴跌（5m/15m双确认）"
        elif spike_confirmed:
            strength = 0.85
            desc = "引爆信号：冲高回落（5m/15m双确认）"
        else:
            strength = 0.90
            desc = "引爆信号：放量暴跌（5m/15m双确认）"

        logger.info(f"★ {desc}, strength={strength}")

        return IgnitionResult(strength=strength, description=desc)

    def has_any_ignition(self, klines_5m: List, klines_15m: List) -> bool:
        """快速判断接口：是否存在任何引爆信号"""
        return self.detect(klines_5m, klines_15m) is not None

    # ----------------------------------------------------------
    # 冲高回落检测
    # ----------------------------------------------------------

    def _detect_spike_and_drop(self, klines: List, cfg: Dict) -> bool:
        """
        冲高回落形态检测：
        1. 上影线 >= 实体 × N 倍
        2. 冲高幅度（(high - close) / close）>= 阈值
        3. 收盘低于开盘（收阴）
        4. 该根 K 线放量（相对前 N 根均量）
        5. 后续 K 线缩量
        """
        if not klines or len(klines) < 5:
            return False

        opens = get_opens_from_klines(klines)
        closes = get_closes_from_klines(klines)
        highs = get_highs_from_klines(klines)
        lows = get_lows_from_klines(klines)
        volumes = get_volumes_from_klines(klines)

        # 检查倒数第 2 根（留最后一根做缩量确认）
        idx = -2
        o, c, h, l = opens[idx], closes[idx], highs[idx], lows[idx]
        body = abs(c - o)
        upper_shadow = h - max(o, c)

        if body == 0:
            body = 0.0001  # 避免除零

        # 条件 1：上影线 >= 实体 × 倍数
        if upper_shadow < body * cfg["spike_upper_shadow_ratio"]:
            return False

        # 条件 2：冲高幅度
        if c == 0:
            return False
        surge_pct = (h - c) / c
        if surge_pct < cfg["spike_surge_pct"]:
            return False

        # 条件 3：收阴（收盘 <= 开盘）
        if c > o:
            return False

        # 条件 4：放量（相对前 10 根均量）
        lookback = min(10, len(volumes) - 2)
        if lookback <= 0:
            return False
        avg_vol = sum(volumes[-(lookback + 2):-2]) / lookback
        if avg_vol == 0:
            return False
        if volumes[idx] < avg_vol * cfg["spike_volume_ratio"]:
            return False

        # 条件 5：后续缩量（最后一根成交量 < 放量根 × 缩量比）
        if volumes[-1] > volumes[idx] * cfg["spike_shrink_ratio"]:
            return False

        return True

    # ----------------------------------------------------------
    # 放量暴跌检测
    # ----------------------------------------------------------

    def _detect_volume_crash(self, klines: List, cfg: Dict) -> bool:
        """
        放量暴跌形态检测（满足任一即可）：

        形态 A - 单根大阴线：
          1. 跌幅 >= 阈值
          2. 实体占比 >= 0.6
          3. 放量 >= 2x

        形态 B - 连续阴线：
          连续 N 根阴线，累计跌幅达标
        """
        if not klines or len(klines) < 5:
            return False

        opens = get_opens_from_klines(klines)
        closes = get_closes_from_klines(klines)
        highs = get_highs_from_klines(klines)
        lows = get_lows_from_klines(klines)
        volumes = get_volumes_from_klines(klines)

        # --- 形态 A：单根大阴线 ---
        for offset in (-1, -2):
            idx = offset
            o, c, h, l = opens[idx], closes[idx], highs[idx], lows[idx]
            full_range = h - l
            if o == 0 or full_range == 0:
                continue

            drop_pct = (o - c) / o
            body = abs(c - o)
            body_ratio = body / full_range

            # 跌幅 + 实体占比 + 放量
            if drop_pct < cfg["crash_drop_pct"]:
                continue
            if body_ratio < cfg["crash_body_ratio"]:
                continue

            lookback = min(10, len(volumes) + offset)
            if lookback <= 0:
                continue
            avg_vol = sum(volumes[offset - lookback:offset]) / lookback
            if avg_vol == 0:
                continue
            if volumes[idx] >= avg_vol * cfg["crash_volume_ratio"]:
                return True

        # --- 形态 B：连续阴线累计跌幅 ---
        count = cfg["crash_consecutive_count"]
        if len(klines) >= count:
            recent_opens = opens[-count:]
            recent_closes = closes[-count:]

            all_bearish = all(
                recent_closes[i] < recent_opens[i]
                for i in range(count)
            )
            if all_bearish and recent_opens[0] > 0:
                total_drop = (recent_opens[0] - recent_closes[-1]) / recent_opens[0]
                if total_drop >= cfg["crash_consecutive_drop_pct"]:
                    return True

        return False
