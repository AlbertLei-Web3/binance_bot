"""
半自动做空信号系统 - 入口脚本

运行模式：
1. report: 生成报告（可指定时间或立即执行）
2. monitor: 启动实时监控
3. both: 同时运行报告和监控

Usage:
    python scripts/run_scanner.py report           # 立即生成报告
    python scripts/run_scanner.py report --timer   # 启动定时报告
    python scripts/run_scanner.py monitor          # 启动实时监控
    python scripts/run_scanner.py both             # 同时运行
"""
import argparse
import sys
import os
import yaml
from datetime import datetime

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scanner.pump_tracker import PumpTracker
from scanner.multi_timeframe import MultiTimeframeAnalyzer
from scanner.signal_15m import Signal15M
from scanner.scorer import Scorer
from scanner.reporter import Reporter
from scheduler.timer import TimerScheduler, run_once
from scheduler.monitor import RealtimeMonitor
from core.dingtalk import init_notifier, get_notifier
from utils.logger import setup_logger

logger = setup_logger("scanner")


def load_config(config_path: str = "config/config.yaml") -> dict:
    """加载配置文件"""
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def init_components(config: dict):
    """初始化各组件"""
    scanner_cfg = config.get("scanner", {})
    dingtalk_cfg = config.get("dingtalk", {})

    # 初始化钉钉通知器
    if dingtalk_cfg.get("enabled") and dingtalk_cfg.get("webhook_url"):
        init_notifier(
            webhook_url=dingtalk_cfg["webhook_url"],
            secret=dingtalk_cfg.get("secret", "")
        )
        logger.info("钉钉通知器已初始化")

    # 初始化各组件
    pump_tracker = PumpTracker(
        data_file=scanner_cfg.get("pump_tracker", {}).get("data_file", "data/pump_history.json"),
        top_n=scanner_cfg.get("pump_tracker", {}).get("top_n", 10)
    )

    analyzer = MultiTimeframeAnalyzer(config=scanner_cfg)

    signal_15m = Signal15M(config=scanner_cfg)

    scorer = Scorer(config=scanner_cfg)

    reporter = Reporter(
        output_dir=scanner_cfg.get("report", {}).get("output_dir", "reports")
    )

    return {
        "pump_tracker": pump_tracker,
        "analyzer": analyzer,
        "signal_15m": signal_15m,
        "scorer": scorer,
        "reporter": reporter,
    }


def generate_report(components: dict, send_notification: bool = True) -> str:
    """
    生成报告

    Args:
        components: 组件字典
        send_notification: 是否发送钉钉通知

    Returns:
        报告文件路径
    """
    logger.info("=" * 50)
    logger.info("开始生成报告")
    logger.info("=" * 50)

    pump_tracker = components["pump_tracker"]
    analyzer = components["analyzer"]
    signal_15m = components["signal_15m"]
    scorer = components["scorer"]
    reporter = components["reporter"]

    # 1. 更新霸榜记录
    pump_tracker.update_daily_record()

    # 2. 获取霸榜排名
    min_days = 3  # 最少霸榜天数
    ranking = pump_tracker.get_pump_ranking(min_days=min_days)

    if not ranking:
        logger.warning("没有符合条件的币种")
        return None

    logger.info(f"霸榜排名: {len(ranking)} 个币种")

    # 3. 对每个币种进行多周期分析和评分
    scored_symbols = []
    crash_signals = []

    for item in ranking:
        symbol = item["symbol"]

        # 多周期分析
        mtf_analysis = analyzer.analyze(
            symbol,
            pump_days=item["pump_days"],
            total_gain=item["total_gain"]
        )

        # 15分钟暴跌检测
        sig_15m = signal_15m.detect_crash(symbol)
        if sig_15m and sig_15m.get("is_crash"):
            crash_signals.append(sig_15m)

        # 综合评分
        score_result = scorer.score_symbol(
            symbol=symbol,
            pump_info=item,
            mtf_analysis=mtf_analysis,
            signal_15m=sig_15m
        )
        scored_symbols.append(score_result)

        logger.info(
            f"{symbol}: 评分={score_result['total_score']:.2f}, "
            f"仓位={score_result['position_advice']}, "
            f"信号={len(score_result['signals'])}"
        )

    # 4. 排名
    ranked_symbols = scorer.rank_symbols(scored_symbols)

    # 5. 生成报告
    filepath = reporter.generate_and_save(ranked_symbols, crash_signals)

    logger.info(f"报告已生成: {filepath}")

    # 6. 发送钉钉通知
    if send_notification:
        notifier = get_notifier()
        if notifier:
            top_symbols = [
                {
                    "symbol": s["symbol"],
                    "pump_days": s["pump_days"],
                    "score": s["total_score"],
                    "position_advice": s["position_advice"],
                }
                for s in ranked_symbols[:5]
            ]

            crash_summary = ""
            if crash_signals:
                crash_summary = f"⚠️ 暴跌信号: {len(crash_signals)} 个\n"

            summary = f"{crash_summary}共 {len(ranked_symbols)} 个关注币种"
            success = notifier.send_daily_report(summary, top_symbols)

            if success:
                logger.info("钉钉通知已发送")
            else:
                logger.warning("钉钉通知发送失败")

    return filepath


def run_monitor(components: dict, config: dict):
    """
    启动实时监控

    Args:
        components: 组件字典
        config: 配置字典
    """
    notifier = get_notifier()
    if not notifier:
        logger.warning("钉钉通知器未初始化，将无法推送警报")

    monitor = RealtimeMonitor(
        pump_tracker=components["pump_tracker"],
        analyzer=components["analyzer"],
        signal_15m=components["signal_15m"],
        scorer=components["scorer"],
        notifier=notifier,
        config=config
    )

    monitor.start(blocking=True)


def run_timer_scheduler(components: dict, config: dict):
    """
    启动定时调度器

    Args:
        components: 组件字典
        config: 配置字典
    """
    schedule_times = config.get("scanner", {}).get("report", {}).get(
        "schedule_times", ["12:00", "21:00"]
    )

    scheduler = TimerScheduler(schedule_times=schedule_times)
    scheduler.add_callback(lambda: generate_report(components))

    logger.info(f"定时调度器已配置，触发时间: {schedule_times}")

    # 显示下次触发时间
    next_trigger = scheduler.get_next_trigger_time()
    if next_trigger:
        logger.info(f"下次触发时间: {next_trigger.strftime('%Y-%m-%d %H:%M:%S')}")

    scheduler.start(blocking=True)


def main():
    parser = argparse.ArgumentParser(description="半自动做空信号系统")
    parser.add_argument(
        "mode",
        choices=["report", "monitor", "both"],
        help="运行模式: report(报告), monitor(监控), both(两者)"
    )
    parser.add_argument(
        "--timer", "-t",
        action="store_true",
        help="启用定时模式（仅 report 模式）"
    )
    parser.add_argument(
        "--config", "-c",
        default="config/config.yaml",
        help="配置文件路径"
    )
    parser.add_argument(
        "--no-notify",
        action="store_true",
        help="不发送钉钉通知"
    )

    args = parser.parse_args()

    # 加载配置
    config = load_config(args.config)
    logger.info(f"配置已加载: {args.config}")

    # 初始化组件
    components = init_components(config)

    if args.mode == "report":
        if args.timer:
            # 定时报告模式
            run_timer_scheduler(components, config)
        else:
            # 立即生成报告
            generate_report(components, send_notification=not args.no_notify)

    elif args.mode == "monitor":
        # 实时监控模式
        run_monitor(components, config)

    elif args.mode == "both":
        # 同时运行（监控后台运行，报告前台定时）
        import threading

        # 启动监控（后台）
        notifier = get_notifier()
        monitor = RealtimeMonitor(
            pump_tracker=components["pump_tracker"],
            analyzer=components["analyzer"],
            signal_15m=components["signal_15m"],
            scorer=components["scorer"],
            notifier=notifier,
            config=config
        )
        monitor.start(blocking=False)

        # 启动定时报告（前台）
        run_timer_scheduler(components, config)


if __name__ == "__main__":
    main()
