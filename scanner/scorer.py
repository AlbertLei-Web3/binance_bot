"""
综合评分器 - 整合霸榜天数、技术指标、多周期信号，计算综合评分和资金建议
"""
from typing import Dict, List, Optional
from utils.logger import setup_logger

logger = setup_logger("scorer")


class Scorer:
    """
    综合评分器

    评分维度：
    1. 霸榜天数（40%）
    2. 技术指标（35%）- RSI、布林带
    3. 15分钟信号（25%）- 暴跌信号

    综合评分 → 仓位建议
    """

    # 默认评分权重
    DEFAULT_WEIGHTS = {
        "pump_days": 0.40,
        "technical": 0.35,
        "signal_15m": 0.25,
    }

    # 默认仓位建议映射
    DEFAULT_POSITION_ADVICE = [
        {"min_score": 1.5, "advice": "10%", "description": "激进"},
        {"min_score": 1.2, "advice": "8%", "description": "标准"},
        {"min_score": 0.9, "advice": "5%", "description": "保守"},
        {"min_score": 0.0, "advice": "观望", "description": "不操作"},
    ]

    def __init__(self, config: Dict = None):
        """
        初始化评分器

        Args:
            config: 配置字典
        """
        self.config = config or {}

        # 评分权重
        scoring_cfg = self.config.get("scoring", {})
        self.weights = {
            k: scoring_cfg.get(f"{k}_weight", v)
            for k, v in self.DEFAULT_WEIGHTS.items()
        }

        # 仓位建议映射
        self.position_advice = self.config.get("position_advice", self.DEFAULT_POSITION_ADVICE)

    def calculate_score(self, pump_days: int, mtf_analysis: Dict,
                        signal_15m: Optional[Dict] = None) -> Dict:
        """
        计算综合评分

        Args:
            pump_days: 霸榜天数
            mtf_analysis: 多周期分析结果
            signal_15m: 15分钟暴跌信号（可选）

        Returns:
            评分结果字典
        """
        # 1. 霸榜天数得分
        pump_score = self._calc_pump_score(pump_days)

        # 2. 技术指标得分
        tech_score = self._calc_technical_score(mtf_analysis)

        # 3. 15分钟信号得分
        signal_score = self._calc_signal_15m_score(signal_15m)

        # 加权综合评分
        total_score = (
            pump_score * self.weights["pump_days"] +
            tech_score * self.weights["technical"] +
            signal_score * self.weights["signal_15m"]
        )

        # 获取仓位建议
        position_info = self._get_position_advice(total_score)

        # 收集所有触发的信号
        signals = self._collect_signals(pump_days, mtf_analysis, signal_15m)

        return {
            "total_score": round(total_score, 2),
            "pump_score": round(pump_score, 2),
            "tech_score": round(tech_score, 2),
            "signal_score": round(signal_score, 2),
            "position_advice": position_info["advice"],
            "position_level": position_info["description"],
            "signals": signals,
        }

    def _calc_pump_score(self, pump_days: int) -> float:
        """
        计算霸榜天数得分

        逻辑：霸榜天数越多，做空信号越强
        - 3 天 = 0.6
        - 4 天 = 0.8
        - 5 天 = 1.0
        - 6 天 = 1.2
        - 7+ 天 = 1.5（封顶）
        """
        if pump_days < 3:
            return 0.0

        # 线性增长，封顶 1.5
        score = 0.6 + (pump_days - 3) * 0.2
        return min(score, 1.5)

    def _calc_technical_score(self, mtf_analysis: Dict) -> float:
        """
        计算技术指标得分

        维度：
        - 1H RSI 超买
        - 1H 布林带上轨突破
        - 4H 高位滞涨
        - 30M 量价背离
        """
        score = 0.0
        signals = []

        # 1H 分析
        h1 = mtf_analysis.get("1h", {})
        if h1.get("rsi_overbought"):
            score += 0.4
            signals.append("RSI超买")
        if h1.get("rsi_extreme"):
            score += 0.2
            signals.append("RSI极度超买")
        if h1.get("above_upper_bb"):
            score += 0.3
            signals.append("突破布林上轨")

        # 4H 分析
        h4 = mtf_analysis.get("4h", {})
        if h4.get("stagnation"):
            score += 0.3
            signals.append("4H滞涨")

        # 30M 分析
        m30 = mtf_analysis.get("30m", {})
        if m30.get("volume_divergence"):
            score += 0.2
            signals.append("量价背离")

        return min(score, 1.5)

    def _calc_signal_15m_score(self, signal_15m: Optional[Dict]) -> float:
        """
        计算15分钟暴跌信号得分

        维度：
        - 是否暴跌（跌幅 ≥ 5%）
        - 放量程度
        - 实体占比
        """
        if not signal_15m or not signal_15m.get("is_crash"):
            return 0.0

        drop_pct = signal_15m.get("drop_pct", 0)
        volume_ratio = signal_15m.get("volume_ratio", 0)

        # 跌幅得分
        drop_score = min(drop_pct / 0.08, 1.0)  # 8% 满分

        # 放量得分
        vol_score = min((volume_ratio - 1) / 2, 1.0)  # 3x 满分

        # 综合得分
        score = 1.0 + drop_score * 0.3 + vol_score * 0.2
        return min(score, 1.5)

    def _get_position_advice(self, score: float) -> Dict:
        """
        根据评分获取仓位建议

        Args:
            score: 综合评分

        Returns:
            仓位建议信息
        """
        for advice in self.position_advice:
            if score >= advice["min_score"]:
                return {
                    "advice": advice["advice"],
                    "description": advice["description"],
                }
        return {"advice": "观望", "description": "不操作"}

    def _collect_signals(self, pump_days: int, mtf_analysis: Dict,
                         signal_15m: Optional[Dict]) -> List[str]:
        """收集所有触发的信号"""
        signals = []

        # 霸榜天数
        if pump_days >= 7:
            signals.append(f"霸榜{pump_days}天（激进）")
        elif pump_days >= 5:
            signals.append(f"霸榜{pump_days}天（标准）")
        elif pump_days >= 3:
            signals.append(f"霸榜{pump_days}天（保守）")

        # 1H 信号
        h1 = mtf_analysis.get("1h", {})
        if h1.get("rsi_extreme"):
            signals.append(f"RSI {h1.get('rsi', 0):.0f}（极度超买）")
        elif h1.get("rsi_overbought"):
            signals.append(f"RSI {h1.get('rsi', 0):.0f}（超买）")
        if h1.get("above_upper_bb"):
            signals.append("突破布林上轨")

        # 4H 信号
        h4 = mtf_analysis.get("4h", {})
        if h4.get("stagnation"):
            signals.append("4H高位滞涨")

        # 30M 信号
        m30 = mtf_analysis.get("30m", {})
        div = m30.get("volume_divergence")
        if div:
            signals.append(f"量价背离({div.get('type')})")

        # 15M 信号
        if signal_15m and signal_15m.get("is_crash"):
            drop = signal_15m.get("drop_pct", 0)
            vol = signal_15m.get("volume_ratio", 0)
            signals.append(f"15M暴跌{drop:.1%}放量{vol:.1f}x")

        return signals

    def score_symbol(self, symbol: str, pump_info: Dict, mtf_analysis: Dict,
                     signal_15m: Optional[Dict] = None) -> Dict:
        """
        对单个币种进行完整评分

        Args:
            symbol: 交易对
            pump_info: 霸榜信息
            mtf_analysis: 多周期分析
            signal_15m: 15分钟信号

        Returns:
            完整评分结果
        """
        pump_days = pump_info.get("pump_days", 0)

        score_result = self.calculate_score(pump_days, mtf_analysis, signal_15m)

        return {
            "symbol": symbol,
            "pump_days": pump_days,
            "total_gain": pump_info.get("total_gain", 0),
            "last_price": pump_info.get("last_price", 0) or mtf_analysis.get("daily", {}).get("current_price", 0),
            **score_result,
            "mtf_analysis": mtf_analysis,
            "signal_15m": signal_15m,
        }

    def rank_symbols(self, scored_symbols: List[Dict]) -> List[Dict]:
        """
        对评分后的币种进行排名

        Args:
            scored_symbols: 评分后的币种列表

        Returns:
            排名后的列表
        """
        return sorted(scored_symbols, key=lambda x: x["total_score"], reverse=True)
