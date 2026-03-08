"""
实时监控模块 - 持续监控15分钟异动，触发时推送钉钉通知
"""
import time
import threading
from datetime import datetime
from typing import Dict, List, Optional, Set
from utils.logger import setup_logger

logger = setup_logger("monitor")


class RealtimeMonitor:
    """
    实时监控器

    功能：
    - 持续监控关注列表中的币种
    - 检测15分钟暴跌信号（跌幅 ≥ 5%）
    - 触发时推送钉钉通知
    """

    def __init__(self, pump_tracker, analyzer, signal_15m, scorer,
                 notifier, config: Dict = None):
        """
        初始化实时监控器

        Args:
            pump_tracker: 霸榜追踪器实例
            analyzer: 多周期分析器实例
            signal_15m: 15分钟信号检测器实例
            scorer: 评分器实例
            notifier: 钉钉通知器实例
            config: 配置字典
        """
        self.pump_tracker = pump_tracker
        self.analyzer = analyzer
        self.signal_15m = signal_15m
        self.scorer = scorer
        self.notifier = notifier
        self.config = config or {}

        monitor_cfg = self.config.get("monitor", {})
        self.interval_sec = monitor_cfg.get("interval_sec", 60)
        self.enabled = monitor_cfg.get("enabled", True)
        self.manual_symbols = monitor_cfg.get("symbols", [])

        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._triggered_signals: Set[str] = set()  # 已触发的信号，避免重复推送

    def start(self, blocking: bool = False):
        """
        启动监控

        Args:
            blocking: 是否阻塞主线程
        """
        if not self.enabled:
            logger.info("实时监控已禁用")
            return

        self._running = True

        if blocking:
            self._run_loop()
        else:
            self._thread = threading.Thread(target=self._run_loop, daemon=True)
            self._thread.start()
            logger.info(f"实时监控已启动，间隔: {self.interval_sec}秒")

    def stop(self):
        """停止监控"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("实时监控已停止")

    def _run_loop(self):
        """主监控循环"""
        while self._running:
            try:
                self._check_symbols()
            except Exception as e:
                logger.error(f"监控检查失败: {e}")

            time.sleep(self.interval_sec)

    def _check_symbols(self):
        """检查关注列表中的币种"""
        # 获取监控列表
        symbols = self._get_watch_symbols()
        if not symbols:
            logger.debug("关注列表为空，跳过检查")
            return

        logger.debug(f"检查 {len(symbols)} 个币种: {symbols}")

        for symbol in symbols:
            try:
                self._check_symbol(symbol)
            except Exception as e:
                logger.debug(f"{symbol} 检查失败: {e}")

    def _get_watch_symbols(self) -> List[str]:
        """获取监控列表"""
        # 优先使用手动指定的列表
        if self.manual_symbols:
            return self.manual_symbols

        # 否则从霸榜追踪器获取
        min_days = self.config.get("scanner", {}).get("pump_tracker", {}).get("min_pump_days", 3)
        return self.pump_tracker.get_watchlist(min_days=min_days)

    def _check_symbol(self, symbol: str):
        """检查单个币种"""
        # 检测15分钟暴跌信号
        crash_signal = self.signal_15m.detect_crash(symbol)

        if crash_signal and crash_signal.get("is_crash"):
            # 生成唯一标识，避免短时间内重复推送
            signal_key = f"{symbol}_{datetime.now().strftime('%Y%m%d_%H%M')}"

            if signal_key not in self._triggered_signals:
                self._handle_crash_signal(symbol, crash_signal)
                self._triggered_signals.add(signal_key)

                # 清理过期的触发记录（保留最近1小时）
                self._cleanup_triggered_signals()

    def _handle_crash_signal(self, symbol: str, crash_signal: Dict):
        """
        处理暴跌信号

        Args:
            symbol: 交易对
            crash_signal: 暴跌信号数据
        """
        logger.info(f"⚠️ 检测到暴跌信号: {symbol}")

        # 获取霸榜信息
        pump_info = self.pump_tracker.get_symbol_info(symbol) or {}
        pump_days = pump_info.get("pump_days", 0)

        # 多周期分析
        mtf_analysis = self.analyzer.analyze(
            symbol,
            pump_days=pump_days,
            total_gain=pump_info.get("total_gain", 0)
        )

        # 计算评分
        score_result = self.scorer.calculate_score(
            pump_days=pump_days,
            mtf_analysis=mtf_analysis,
            signal_15m=crash_signal
        )

        # 推送钉钉通知
        if self.notifier:
            success = self.notifier.send_signal_alert(
                symbol=symbol,
                price=crash_signal.get("close_price", 0),
                drop_pct=crash_signal.get("drop_pct", 0),
                volume_ratio=crash_signal.get("volume_ratio", 0),
                pump_days=pump_days,
                position_advice=score_result.get("position_advice", "-"),
            )
            if success:
                logger.info(f"钉钉推送成功: {symbol}")
            else:
                logger.warning(f"钉钉推送失败: {symbol}")

    def _cleanup_triggered_signals(self):
        """清理过期的触发记录"""
        current_time = datetime.now()
        current_prefix = current_time.strftime("%Y%m%d_%H")

        # 只保留当前小时的记录
        self._triggered_signals = {
            key for key in self._triggered_signals
            if key.split("_")[0] + "_" + key.split("_")[1] == current_prefix
        }

    def get_status(self) -> Dict:
        """获取监控器状态"""
        return {
            "running": self._running,
            "enabled": self.enabled,
            "interval_sec": self.interval_sec,
            "watch_symbols": self._get_watch_symbols(),
            "triggered_count": len(self._triggered_signals),
        }

    def add_symbol(self, symbol: str):
        """添加监控币种"""
        if symbol not in self.manual_symbols:
            self.manual_symbols.append(symbol)
            logger.info(f"添加监控币种: {symbol}")

    def remove_symbol(self, symbol: str):
        """移除监控币种"""
        if symbol in self.manual_symbols:
            self.manual_symbols.remove(symbol)
            logger.info(f"移除监控币种: {symbol}")

    def force_check(self, symbol: str = None):
        """
        强制检查（用于手动触发）

        Args:
            symbol: 指定币种，为空则检查所有
        """
        if symbol:
            self._check_symbol(symbol)
        else:
            self._check_symbols()
