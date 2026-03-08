"""
霸榜追踪器 - 追踪涨幅榜前 N 名币种的连续霸榜天数
"""
import json
import os
from datetime import datetime, date
from typing import Dict, List, Optional
from core.client import get_client
from utils.logger import setup_logger

logger = setup_logger("pump_tracker")


class PumpTracker:
    """
    霸榜追踪器

    功能：
    1. 获取涨幅榜前 N 名
    2. 持久化记录每日霸榜数据
    3. 计算连续霸榜天数
    4. 输出霸榜排名
    """

    def __init__(self, data_file: str = "data/pump_history.json", top_n: int = 10):
        """
        初始化霸榜追踪器

        Args:
            data_file: 霸榜历史数据文件路径
            top_n: 监控涨幅榜前 N 名
        """
        self.data_file = data_file
        self.top_n = top_n
        self.client = get_client()
        self._history: Dict = self._load_history()

    def _load_history(self) -> Dict:
        """加载历史数据"""
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"加载霸榜历史失败: {e}")
        return {"records": {}, "last_update": None}

    def _save_history(self):
        """保存历史数据"""
        os.makedirs(os.path.dirname(self.data_file), exist_ok=True)
        with open(self.data_file, "w", encoding="utf-8") as f:
            json.dump(self._history, f, ensure_ascii=False, indent=2)

    def scan_top_gainers(self) -> List[Dict]:
        """
        获取涨幅榜前 N 名（仅U本位永续合约）

        Returns:
            [{"symbol": "XXXUSDT", "price": 0.123, "change_pct": 0.25}, ...]
        """
        try:
            # 获取可交易的永续合约列表
            exchange_info = self.client.futures_exchange_info()
            perpetual_symbols = set()
            for s in exchange_info.get("symbols", []):
                if (s.get("contractType") == "PERPETUAL" and
                    s.get("quoteAsset") == "USDT" and
                    s.get("status") == "TRADING"):
                    perpetual_symbols.add(s["symbol"])

            # 获取行情数据
            tickers = self.client.futures_ticker()

            # 过滤：仅U本位永续合约 + 成交额 > 1000万
            usdt_pairs = [
                t for t in tickers
                if t["symbol"] in perpetual_symbols
                and float(t.get("quoteVolume", 0)) > 10_000_000
            ]

            # 按涨幅排序
            sorted_pairs = sorted(
                usdt_pairs,
                key=lambda x: float(x.get("priceChangePercent", 0)),
                reverse=True
            )
            top_n = sorted_pairs[:self.top_n]

            result = []
            for t in top_n:
                result.append({
                    "symbol": t["symbol"],
                    "price": float(t.get("lastPrice", 0)),
                    "change_pct": float(t.get("priceChangePercent", 0)) / 100,
                    "volume": float(t.get("quoteVolume", 0)),
                })
            return result
        except Exception as e:
            logger.error(f"获取涨幅榜失败: {e}")
            return []

    def update_daily_record(self) -> Dict:
        """
        更新每日霸榜记录

        Returns:
            更新结果摘要
        """
        today = date.today().isoformat()
        top_gainers = self.scan_top_gainers()

        if not top_gainers:
            return {"success": False, "message": "获取涨幅榜失败"}

        symbols_today = {g["symbol"] for g in top_gainers}
        records = self._history.setdefault("records", {})

        # 更新每个币种的霸榜记录
        for gainer in top_gainers:
            symbol = gainer["symbol"]
            symbol_records = records.setdefault(symbol, {"dates": [], "total_gain": 0})

            # 如果今天还没记录，则添加
            if today not in symbol_records["dates"]:
                symbol_records["dates"].append(today)
                symbol_records["total_gain"] += gainer["change_pct"]

            # 更新最新价格和涨幅
            symbol_records["last_price"] = gainer["price"]
            symbol_records["last_change"] = gainer["change_pct"]

        # 对于之前霸榜但今天不在榜的币种，结束其连续霸榜
        for symbol in list(records.keys()):
            if symbol not in symbols_today:
                symbol_records = records[symbol]
                # 如果昨天还在榜，今天不在，记录中断
                dates = symbol_records.get("dates", [])
                if dates and dates[-1] != today:
                    # 可以选择保留历史或清空
                    pass

        self._history["last_update"] = datetime.now().isoformat()
        self._save_history()

        logger.info(f"霸榜记录更新完成，今日上榜: {len(top_gainers)} 个币种")
        return {
            "success": True,
            "date": today,
            "top_gainers": top_gainers,
            "total_tracked": len(records),
        }

    def get_pump_days(self, symbol: str) -> int:
        """
        获取指定币种的连续霸榜天数

        Args:
            symbol: 交易对

        Returns:
            连续霸榜天数
        """
        records = self._history.get("records", {})
        if symbol not in records:
            return 0

        dates = records[symbol].get("dates", [])
        if not dates:
            return 0

        # 计算连续天数（从最近一天往前数）
        dates_sorted = sorted(dates, reverse=True)
        today = date.today()

        consecutive_days = 0
        expected_date = today

        for d in dates_sorted:
            d_date = date.fromisoformat(d)
            if d_date == expected_date:
                consecutive_days += 1
                expected_date = date.fromisoformat(
                    (expected_date - __import__("datetime").timedelta(days=1)).isoformat()
                )
            elif d_date == expected_date - __import__("datetime").timedelta(days=1):
                # 允许一天的中断（可能是数据延迟）
                consecutive_days += 1
                expected_date = d_date - __import__("datetime").timedelta(days=1)
            else:
                break

        return consecutive_days

    def get_pump_ranking(self, min_days: int = 3) -> List[Dict]:
        """
        获取霸榜排名

        Args:
            min_days: 最少霸榜天数过滤

        Returns:
            排名列表，按霸榜天数降序
        """
        records = self._history.get("records", {})
        ranking = []

        for symbol, data in records.items():
            pump_days = self.get_pump_days(symbol)
            if pump_days >= min_days:
                ranking.append({
                    "symbol": symbol,
                    "pump_days": pump_days,
                    "total_gain": data.get("total_gain", 0),
                    "last_price": data.get("last_price", 0),
                    "last_change": data.get("last_change", 0),
                    "dates": data.get("dates", []),
                })

        # 按霸榜天数降序排序
        ranking.sort(key=lambda x: x["pump_days"], reverse=True)
        return ranking

    def get_watchlist(self, min_days: int = 3) -> List[str]:
        """
        获取关注列表（霸榜天数 >= min_days 的币种）

        Args:
            min_days: 最少霸榜天数

        Returns:
            币种列表
        """
        ranking = self.get_pump_ranking(min_days=min_days)
        return [r["symbol"] for r in ranking]

    def get_symbol_info(self, symbol: str) -> Optional[Dict]:
        """
        获取指定币种的详细信息

        Args:
            symbol: 交易对

        Returns:
            币种信息字典
        """
        records = self._history.get("records", {})
        if symbol not in records:
            return None

        data = records[symbol]
        return {
            "symbol": symbol,
            "pump_days": self.get_pump_days(symbol),
            "total_gain": data.get("total_gain", 0),
            "last_price": data.get("last_price", 0),
            "last_change": data.get("last_change", 0),
            "dates": data.get("dates", []),
        }
