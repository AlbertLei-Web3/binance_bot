"""
报告生成器 - 生成 Markdown 格式的做空信号报告（Obsidian 优化版）
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
        self.output_dir = output_dir

    def generate_report(self, ranked_symbols: List[Dict],
                        crash_signals: List[Dict] = None,
                        title: str = None) -> str:
        """生成 Markdown 报告（Obsidian 优化格式）"""
        now = datetime.now()
        date_str = now.strftime('%Y-%m-%d')
        time_str = now.strftime('%H:%M')

        # YAML front matter（Obsidian 支持）
        md_lines = [
            "---",
            f"title: 做空信号报告 {date_str}",
            f"date: {now.strftime('%Y-%m-%d %H:%M:%S')}",
            "tags: [加密货币, 做空, 交易信号]",
            "---",
            "",
            f"# 做空信号报告",
            "",
            f"> 生成时间：{date_str} {time_str}",
            "",
        ]

        # ========== 摘要卡片 ==========
        total_symbols = len(ranked_symbols)
        high_score = [s for s in ranked_symbols if s.get("total_score", 0) >= 1.0]
        crash_count = len(crash_signals) if crash_signals else 0

        md_lines.extend([
            "## 摘要",
            "",
            f"| 项目 | 数量 |",
            f"|:-----|:----:|",
            f"| 关注币种 | {total_symbols} |",
            f"| 高分币种 | {len(high_score)} |",
            f"| 暴跌信号 | {crash_count} |",
            "",
        ])

        # ========== 暴跌信号（优先显示）==========
        if crash_signals:
            md_lines.extend([
                "---",
                "",
                "## 暴跌信号",
                "",
                "> [!danger] 15分钟周期检测到暴跌，可考虑入场",
                "",
            ])

            for sig in crash_signals:
                symbol = sig.get("symbol", "")
                drop_pct = sig.get("drop_pct", 0)
                volume_ratio = sig.get("volume_ratio", 0)

                score_info = next(
                    (s for s in ranked_symbols if s.get("symbol") == symbol), {}
                )
                pump_days = score_info.get("pump_days", 0)
                position = score_info.get("position_advice", "-")

                md_lines.extend([
                    f"### {symbol}",
                    "",
                    f"| 指标 | 数值 |",
                    f"|:-----|:----:|",
                    f"| 跌幅 | **{drop_pct:.1%}** |",
                    f"| 放量 | {volume_ratio:.1f}x |",
                    f"| 霸榜天数 | {pump_days} 天 |",
                    f"| 建议仓位 | {position} |",
                    "",
                ])

        # ========== 霸榜排名 ==========
        md_lines.extend([
            "---",
            "",
            "## 霸榜排名",
            "",
        ])

        # 分组：高分 / 中分 / 低分
        high = [s for s in ranked_symbols if s.get("total_score", 0) >= 1.0]
        medium = [s for s in ranked_symbols if 0.5 <= s.get("total_score", 0) < 1.0]
        low = [s for s in ranked_symbols if s.get("total_score", 0) < 0.5]

        if high:
            md_lines.extend([
                "> [!tip] 高分币种（评分 >= 1.0）",
                "",
                "| 币种 | 天数 | 涨幅 | 评分 | 仓位 |",
                "|:-----|:----:|:----:|:----:|:----:|",
            ])
            for s in high:
                md_lines.append(
                    f"| [[{s['symbol']}]] | {s.get('pump_days', 0)} | "
                    f"{s.get('total_gain', 0):.0%} | **{s.get('total_score', 0):.1f}** | "
                    f"{s.get('position_advice', '-')} |"
                )
            md_lines.append("")

        if medium:
            md_lines.extend([
                "> [!note] 中分币种（评分 0.5-1.0）",
                "",
                "| 币种 | 天数 | 涨幅 | 评分 | 仓位 |",
                "|:-----|:----:|:----:|:----:|:----:|",
            ])
            for s in medium:
                md_lines.append(
                    f"| [[{s['symbol']}]] | {s.get('pump_days', 0)} | "
                    f"{s.get('total_gain', 0):.0%} | {s.get('total_score', 0):.1f} | "
                    f"{s.get('position_advice', '-')} |"
                )
            md_lines.append("")

        if low:
            md_lines.extend([
                "> [!info] 低分币种（评分 < 0.5）- 暂不关注",
                "",
                "| 币种 | 天数 | 涨幅 | 评分 |",
                "|:-----|:----:|:----:|:----:|",
            ])
            for s in low:
                md_lines.append(
                    f"| {s['symbol']} | {s.get('pump_days', 0)} | "
                    f"{s.get('total_gain', 0):.0%} | {s.get('total_score', 0):.1f} |"
                )
            md_lines.append("")

        # ========== 详细分析（仅高分和中分）==========
        detailed_symbols = high + medium
        if detailed_symbols:
            md_lines.extend([
                "---",
                "",
                "## 详细分析",
                "",
            ])

            for s in detailed_symbols[:5]:  # 最多显示5个
                md_lines.extend(self._generate_detail_section(s))

        # ========== 操作建议 ==========
        md_lines.extend([
            "---",
            "",
            "## 操作建议",
            "",
            "### 仓位分配",
            "",
            "| 类型 | 头仓 | 补1 | 补2 | 补3 | 合计 |",
            "|:-----|:----:|:---:|:---:|:---:|:----:|",
            "| 保守 | 5% | 1.25% | 1.25% | 1.25% | 8.75% |",
            "| 标准 | 6.25% | 1.56% | 1.56% | 1.56% | 10.94% |",
            "| 激进 | 10% | 2.5% | 2.5% | 2.5% | 17.5% |",
            "",
            "### 风控规则",
            "",
            "| 规则 | 触发条件 |",
            "|:-----|:---------|",
            "| 止损 | 价格上涨 30% |",
            "| 止盈 | 任意入场价下跌 40% |",
            "| 补仓 | 价格上涨 8%/15%/25% |",
            "| 超时 | 持仓超过 48 小时 |",
            "",
        ])

        md_lines.extend([
            "---",
            "",
            "#交易 #做空 #币安",
        ])

        return "\n".join(md_lines)

    def _generate_detail_section(self, symbol_data: Dict) -> List[str]:
        """生成单个币种的详细分析"""
        symbol = symbol_data.get("symbol", "")
        score = symbol_data.get("total_score", 0)
        position = symbol_data.get("position_advice", "-")
        signals = symbol_data.get("signals", [])
        mtf = symbol_data.get("mtf_analysis", {})

        lines = [
            f"### {symbol}",
            "",
            f"**评分**: {score:.2f} | **仓位**: {position}",
            "",
        ]

        # 触发信号
        if signals:
            lines.append("**触发信号**:")
            for sig in signals:
                lines.append(f"- {sig}")
            lines.append("")

        # 多周期表格
        lines.extend([
            "| 周期 | 状态 | 详情 |",
            "|:----:|:----:|:-----|",
        ])

        # 日K
        daily = mtf.get("daily", {})
        if daily and not daily.get("error"):
            status = "滞涨" if daily.get("stagnation") else "上涨"
            lines.append(
                f"| 日K | {status} | 霸榜 {daily.get('pump_days', 0)} 天，"
                f"累计 {daily.get('total_gain', 0):.0%} |"
            )

        # 4H
        h4 = mtf.get("4h", {})
        if h4 and not h4.get("error"):
            status = "滞涨" if h4.get("stagnation") else "-"
            top = "顶" if h4.get("top_pattern") else "-"
            lines.append(f"| 4H | {status}/{top} | 趋势: {h4.get('trend', '-')} |")

        # 1H
        h1 = mtf.get("1h", {})
        if h1 and not h1.get("error"):
            rsi = h1.get("rsi", 0)
            rsi_status = "超买" if h1.get("rsi_overbought") else "正常"
            bb_status = "突破" if h1.get("above_upper_bb") else "正常"
            lines.append(f"| 1H | RSI {rsi_status} | {rsi:.0f}, 布林 {bb_status} |")

        # 30M
        m30 = mtf.get("30m", {})
        if m30 and not m30.get("error"):
            div = m30.get("volume_divergence")
            div_str = f"背离" if div else "-"
            lines.append(f"| 30M | {div_str} | 趋势: {m30.get('trend', '-')} |")

        # 15M
        sig_15m = symbol_data.get("signal_15m")
        if sig_15m and sig_15m.get("is_crash"):
            lines.append(
                f"| **15M** | **暴跌** | **{sig_15m.get('drop_pct', 0):.1%} / "
                f"{sig_15m.get('volume_ratio', 0):.1f}x** |"
            )
        else:
            m15 = mtf.get("15m", {})
            if m15 and not m15.get("error"):
                lines.append(f"| 15M | 正常 | 跌幅 {m15.get('drop_pct', 0):.1%} |")

        lines.append("")
        lines.append("")

        return lines

    def save_report(self, content: str, filename: str = None) -> str:
        """保存报告到文件"""
        now = datetime.now()
        date_dir = now.strftime("%Y-%m-%d")

        if not filename:
            filename = f"做空报告_{now.strftime('%H%M')}.md"

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
        """生成并保存报告"""
        content = self.generate_report(ranked_symbols, crash_signals, title)
        return self.save_report(content)
