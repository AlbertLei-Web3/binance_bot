"""
报告生成器 - 生成 Markdown 格式的做空信号报告
"""
import os
from datetime import datetime
from typing import Dict, List, Optional
from utils.logger import setup_logger

logger = setup_logger("reporter")


class Reporter:
    """
    报告生成器

    生成 Markdown 格式报告，包含：
    - 霸榜排名
    - 技术指标
    - 15分钟暴跌信号
    - 资金建议
    """

    def __init__(self, output_dir: str = "reports"):
        """
        初始化报告生成器

        Args:
            output_dir: 报告输出目录
        """
        self.output_dir = output_dir

    def generate_report(self, ranked_symbols: List[Dict],
                        crash_signals: List[Dict] = None,
                        title: str = None) -> str:
        """
        生成 Markdown 报告

        Args:
            ranked_symbols: 排名后的币种列表
            crash_signals: 暴跌信号列表
            title: 报告标题

        Returns:
            Markdown 格式报告内容
        """
        now = datetime.now()
        report_title = title or f"山寨币做空信号报告 - {now.strftime('%Y-%m-%d %H:%M')}"

        md_lines = [
            f"# {report_title}",
            "",
            f"**生成时间**: {now.strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "---",
            "",
            "## 📊 霸榜排名",
            "",
        ]

        # 表头
        md_lines.append("| 排名 | 币种 | 霸榜天数 | 累计涨幅 | RSI | 布林带 | 综合评分 | 建议仓位 |")
        md_lines.append("|:----:|:-----|:--------:|:--------:|:---:|:------:|:--------:|:--------:|")

        # 表格内容
        for i, s in enumerate(ranked_symbols, 1):
            symbol = s.get("symbol", "")
            pump_days = s.get("pump_days", 0)
            total_gain = s.get("total_gain", 0)
            score = s.get("total_score", 0)
            position = s.get("position_advice", "-")

            # 从多周期分析中获取技术指标
            h1 = s.get("mtf_analysis", {}).get("1h", {})
            rsi = h1.get("rsi", "-")
            rsi_str = f"{rsi:.0f}" if isinstance(rsi, (int, float)) else rsi
            bb_pos = h1.get("bb_position", "-")
            bb_str = "突破上轨" if bb_pos == "above_upper" else ("接近上轨" if bb_pos == "near_upper" else "正常")

            md_lines.append(
                f"| {i} | {symbol} | {pump_days} 天 | {total_gain:.1%} | "
                f"{rsi_str} | {bb_str} | **{score:.2f}** | {position} |"
            )

        md_lines.append("")

        # 暴跌信号部分
        if crash_signals:
            md_lines.extend([
                "",
                "---",
                "",
                "## ⚠️ 15分钟暴跌信号",
                "",
            ])

            for sig in crash_signals:
                symbol = sig.get("symbol", "")
                drop_pct = sig.get("drop_pct", 0)
                volume_ratio = sig.get("volume_ratio", 0)
                timestamp = sig.get("timestamp", "")

                # 查找对应的评分信息
                score_info = next(
                    (s for s in ranked_symbols if s.get("symbol") == symbol),
                    {}
                )
                position = score_info.get("position_advice", "-")
                pump_days = score_info.get("pump_days", 0)

                md_lines.extend([
                    f"### 🔴 {symbol}",
                    "",
                    f"- **跌幅**: {drop_pct:.2%}",
                    f"- **放量**: {volume_ratio:.1f}x",
                    f"- **霸榜天数**: {pump_days} 天",
                    f"- **建议仓位**: {position}",
                    f"- **时间**: {timestamp}",
                    "",
                    "**建议**: 可考虑建立头仓",
                    "",
                ])

        # 详细分析部分（前3名）
        if ranked_symbols:
            md_lines.extend([
                "",
                "---",
                "",
                "## 📈 详细分析",
                "",
            ])

            for s in ranked_symbols[:3]:
                md_lines.extend(self._generate_detail_section(s))

        # 操作建议
        md_lines.extend([
            "",
            "---",
            "",
            "## 💡 操作建议",
            "",
            "### 仓位管理",
            "",
            "| 状态 | 头仓 | 补仓1 | 补仓2 | 补仓3 | 累计 |",
            "|:----:|:----:|:-----:|:-----:|:-----:|:----:|",
            "| 分配 | 5% | 1.25% | 1.25% | 1.25% | 8.75% |",
            "| 分配 | 6.25% | 1.56% | 1.56% | 1.56% | 10.94% |",
            "",
            "### 风控规则",
            "",
            "- **止损**: 价格上涨 30%（P0 × 1.3）",
            "- **止盈**: 任意入场价下跌 40%",
            "- **补仓**: 价格上涨 8%/15%/25% 时分别补仓",
            "- **超时**: 持仓超过 48 小时自动平仓",
            "",
        ])

        md_lines.extend([
            "---",
            "",
            "*报告由 Binance Bot 自动生成*",
        ])

        return "\n".join(md_lines)

    def _generate_detail_section(self, symbol_data: Dict) -> List[str]:
        """生成单个币种的详细分析部分"""
        symbol = symbol_data.get("symbol", "")
        signals = symbol_data.get("signals", [])
        mtf = symbol_data.get("mtf_analysis", {})

        lines = [
            f"### {symbol}",
            "",
            f"**综合评分**: {symbol_data.get('total_score', 0):.2f}",
            f"**建议仓位**: {symbol_data.get('position_advice', '-')}",
            "",
            "**触发信号**:",
            "",
        ]

        for sig in signals:
            lines.append(f"- {sig}")

        lines.append("")

        # 多周期详情
        lines.append("| 周期 | 信号 | 详情 |")
        lines.append("|:----:|:----:|:-----|")

        # 日K
        daily = mtf.get("daily", {})
        if daily:
            lines.append(
                f"| 日K | {'滞涨' if daily.get('stagnation') else '上涨'} | "
                f"霸榜 {daily.get('pump_days', 0)} 天，累计 {daily.get('total_gain', 0):.1%} |"
            )

        # 4H
        h4 = mtf.get("4h", {})
        if h4 and not h4.get("error"):
            stagnation = "滞涨" if h4.get("stagnation") else "-"
            top = "顶部形态" if h4.get("top_pattern") else "-"
            lines.append(f"| 4H | {stagnation} / {top} | 趋势: {h4.get('trend', '-')} |")

        # 1H
        h1 = mtf.get("1h", {})
        if h1 and not h1.get("error"):
            rsi_status = "超买" if h1.get("rsi_overbought") else "正常"
            bb_status = "突破上轨" if h1.get("above_upper_bb") else "正常"
            lines.append(f"| 1H | RSI {rsi_status} | {h1.get('rsi', 0):.0f}, 布林 {bb_status} |")

        # 30M
        m30 = mtf.get("30m", {})
        if m30 and not m30.get("error"):
            div = m30.get("volume_divergence")
            div_str = f"量价背离({div.get('type')})" if div else "-"
            lines.append(f"| 30M | {div_str} | 趋势: {m30.get('trend', '-')} |")

        # 15M
        sig_15m = symbol_data.get("signal_15m")
        if sig_15m and sig_15m.get("is_crash"):
            lines.append(
                f"| **15M** | **暴跌** | **{sig_15m.get('drop_pct', 0):.2%} 放量 {sig_15m.get('volume_ratio', 0):.1f}x** |"
            )
        else:
            m15 = mtf.get("15m", {})
            if m15 and not m15.get("error"):
                lines.append(f"| 15M | 正常 | 跌幅 {m15.get('drop_pct', 0):.2%} |")

        lines.append("")
        lines.append("")

        return lines

    def save_report(self, content: str, filename: str = None) -> str:
        """
        保存报告到文件

        Args:
            content: 报告内容
            filename: 文件名（不含路径）

        Returns:
            保存的文件路径
        """
        now = datetime.now()
        date_dir = now.strftime("%Y-%m-%d")

        if not filename:
            filename = f"report_{now.strftime('%H-%M')}.md"

        # 创建日期目录
        full_dir = os.path.join(self.output_dir, date_dir)
        os.makedirs(full_dir, exist_ok=True)

        filepath = os.path.join(full_dir, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)

        logger.info(f"报告已保存: {filepath}")
        return filepath

    def generate_and_save(self, ranked_symbols: List[Dict],
                          crash_signals: List[Dict] = None,
                          title: str = None) -> str:
        """
        生成并保存报告

        Args:
            ranked_symbols: 排名后的币种列表
            crash_signals: 暴跌信号列表
            title: 报告标题

        Returns:
            保存的文件路径
        """
        content = self.generate_report(ranked_symbols, crash_signals, title)
        return self.save_report(content)
