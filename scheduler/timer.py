"""
定时调度模块 - 定时生成报告（12:00 / 21:00）
"""
import time
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Callable, Optional
from utils.logger import setup_logger

logger = setup_logger("timer")


class TimerScheduler:
    """
    定时调度器

    功能：
    - 在指定时间点触发任务
    - 支持多个触发时间
    - 支持任务回调函数
    """

    def __init__(self, schedule_times: List[str] = None):
        """
        初始化定时调度器

        Args:
            schedule_times: 触发时间列表，格式 ["HH:MM", ...]
                           默认 ["12:00", "21:00"]
        """
        self.schedule_times = schedule_times or ["12:00", "21:00"]
        self.callbacks: List[Callable] = []
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._last_triggered: Dict[str, str] = {}  # {time: date} 记录每个时间点最后触发日期

    def add_callback(self, callback: Callable):
        """添加任务回调函数"""
        self.callbacks.append(callback)

    def start(self, blocking: bool = True):
        """
        启动调度器

        Args:
            blocking: 是否阻塞主线程
        """
        self._running = True

        if blocking:
            self._run_loop()
        else:
            self._thread = threading.Thread(target=self._run_loop, daemon=True)
            self._thread.start()
            logger.info("定时调度器已启动（后台模式）")

    def stop(self):
        """停止调度器"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("定时调度器已停止")

    def _run_loop(self):
        """主循环"""
        logger.info(f"定时调度器已启动，触发时间: {self.schedule_times}")

        while self._running:
            now = datetime.now()
            today = now.strftime("%Y-%m-%d")
            current_time = now.strftime("%H:%M")

            # 检查是否需要触发
            for schedule_time in self.schedule_times:
                last_date = self._last_triggered.get(schedule_time, "")

                # 当前时间匹配且今天还没触发过
                if current_time == schedule_time and last_date != today:
                    logger.info(f"⏰ 触发定时任务: {schedule_time}")
                    self._trigger_callbacks()
                    self._last_triggered[schedule_time] = today

            # 每秒检查一次
            time.sleep(1)

    def _trigger_callbacks(self):
        """触发所有回调函数"""
        for callback in self.callbacks:
            try:
                callback()
            except Exception as e:
                logger.error(f"回调执行失败: {e}")

    def get_next_trigger_time(self) -> Optional[datetime]:
        """
        获取下一次触发时间

        Returns:
            下一次触发的 datetime 对象
        """
        now = datetime.now()
        today = now.strftime("%Y-%m-%d")

        for schedule_time in sorted(self.schedule_times):
            hour, minute = map(int, schedule_time.split(":"))
            trigger_dt = datetime.now().replace(hour=hour, minute=minute, second=0, microsecond=0)

            if trigger_dt > now:
                return trigger_dt

        # 今天没有了，返回明天的第一个
        if self.schedule_times:
            hour, minute = map(int, sorted(self.schedule_times)[0].split(":"))
            tomorrow = now + timedelta(days=1)
            return tomorrow.replace(hour=hour, minute=minute, second=0, microsecond=0)

        return None

    def get_status(self) -> Dict:
        """获取调度器状态"""
        next_trigger = self.get_next_trigger_time()
        return {
            "running": self._running,
            "schedule_times": self.schedule_times,
            "last_triggered": self._last_triggered,
            "next_trigger": next_trigger.strftime("%Y-%m-%d %H:%M:%S") if next_trigger else None,
        }


def run_once(callback: Callable, schedule_times: List[str] = None) -> bool:
    """
    检查当前时间是否需要执行一次性任务

    Args:
        callback: 回调函数
        schedule_times: 触发时间列表

    Returns:
        是否执行了任务
    """
    schedule_times = schedule_times or ["12:00", "21:00"]
    now = datetime.now()
    current_time = now.strftime("%H:%M")

    # 允许 1 分钟的误差
    for schedule_time in schedule_times:
        h1, m1 = map(int, current_time.split(":"))
        h2, m2 = map(int, schedule_time.split(":"))

        diff = abs((h1 * 60 + m1) - (h2 * 60 + m2))
        if diff <= 1:  # 1 分钟内
            logger.info(f"⏰ 执行定时任务: {schedule_time}")
            try:
                callback()
                return True
            except Exception as e:
                logger.error(f"任务执行失败: {e}")
                return False

    return False
