"""
标的筛选模块 - 自动发现连续拉涨的山寨币
从币安合约涨幅榜扫描，检测连续拉涨标的，管理观察池
"""
import json
import os
from datetime import datetime
from typing import Dict, List, Optional

from core.client import get_client
from core.market import get_klines
from utils.indicators import get_opens_from_klines, get_closes_from_klines
from utils.logger import setup_logger

logger = setup_logger("screener")

# 排除的主流币（不做空）
EXCLUDED_SYMBOLS = {
    "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT",
    "ADAUSDT", "DOGEUSDT", "DOTUSDT", "LINKUSDT", "MATICUSDT",
}

# watchlist.json 默认路径
DEFAULT_WATCHLIST_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data", "watchlist.json"
)


class AltcoinScreener:
    """
    山寨币标的筛选器

    工作流：
    1. futures_ticker() 获取所有合约行情，按涨幅排序取前 N
    2. 对每个标的拉日线 K 线，检测连续拉涨（AND 逻辑）
    3. 基础过滤（成交额、价差、资金费率）
    4. 结果写入 watchlist.json 并返回观察池
    """

    def __init__(self, config: Dict = None):
        self.client = get_client()
        self.config = config or {}

        # 筛选参数
        self.top_n = self.config.get("top_n", 10)
        self.min_days = self.config.get("pump_detect_days", 3)
        self.daily_min_gain = self.config.get("daily_min_gain", 0.12)
        self.total_min_gain = self.config.get("total_min_gain", 1.00)
        self.min_volume_usdt = self.config.get("min_volume_usdt", 20_000_000)
        self.max_spread_pct = self.config.get("max_spread_pct", 0.005)
        self.max_funding_rate = self.config.get("max_funding_rate", 0.0015)

        self.watchlist_path = self.config.get("watchlist_path", DEFAULT_WATCHLIST_PATH)

    # ----------------------------------------------------------
    # 涨幅榜
    # ----------------------------------------------------------

    def get_top_gainers(self, limit: int = None) -> List[Dict]:
        """获取合约涨幅榜前 N"""
        limit = limit or self.top_n
        tickers = self.client.futures_ticker()

        # 过滤 USDT 合约，排除主流币
        usdt_tickers = [
            t for t in tickers
            if t["symbol"].endswith("USDT")
            and t["symbol"] not in EXCLUDED_SYMBOLS
        ]

        # 按 24h 涨幅降序
        usdt_tickers.sort(
            key=lambda t: float(t.get("priceChangePercent", 0)),
            reverse=True
        )

        result = []
        for t in usdt_tickers[:limit]:
            result.append({
                "symbol": t["symbol"],
                "price_change_pct": float(t.get("priceChangePercent", 0)),
                "volume_usdt": float(t.get("quoteVolume", 0)),
                "last_price": float(t.get("lastPrice", 0)),
            })

        logger.info(f"涨幅榜前{limit}: {[r['symbol'] for r in result]}")
        return result


    # ----------------------------------------------------------
    # 连续拉涨检测（AND 逻辑）
    # ----------------------------------------------------------

    def detect_consecutive_pump(self, symbol: str) -> Dict:
        """
        检测连续拉涨，三个条件同时满足：
        A. 连续 ≥ min_days 天日线收阳（收盘 > 开盘）
        B. 每日涨幅均 ≥ daily_min_gain (12%)
        C. 累计涨幅 ≥ total_min_gain (100%)

        Returns:
            {
                "is_pump": bool,
                "consecutive_days": int,
                "daily_gains": [float],
                "total_gain": float,
            }
        """
        try:
            klines = get_klines(symbol, interval="1d", limit=7)
        except Exception as e:
            logger.warning(f"{symbol} 获取日线失败: {e}")
            return {"is_pump": False, "consecutive_days": 0,
                    "daily_gains": [], "total_gain": 0.0}

        if len(klines) < self.min_days:
            return {"is_pump": False, "consecutive_days": 0,
                    "daily_gains": [], "total_gain": 0.0}

        opens = get_opens_from_klines(klines)
        closes = get_closes_from_klines(klines)

        # 从最近一天往前数连阳天数
        consecutive_days = 0
        daily_gains = []

        for i in range(len(klines) - 1, -1, -1):
            if closes[i] > opens[i]:
                gain = (closes[i] - opens[i]) / opens[i]
                consecutive_days += 1
                daily_gains.insert(0, gain)
            else:
                break

        # 累计涨幅：连阳期间第一天开盘到最后一天收盘
        if consecutive_days >= self.min_days:
            first_open = opens[len(klines) - consecutive_days]
            last_close = closes[-1]
            total_gain = (last_close - first_open) / first_open
        else:
            total_gain = 0.0

        # AND 逻辑：三条件同时满足
        condition_a = consecutive_days >= self.min_days
        condition_b = all(g >= self.daily_min_gain for g in daily_gains[-self.min_days:]) if condition_a else False
        condition_c = total_gain >= self.total_min_gain

        is_pump = condition_a and condition_b and condition_c

        return {
            "is_pump": is_pump,
            "consecutive_days": consecutive_days,
            "daily_gains": [round(g * 100, 2) for g in daily_gains],
            "total_gain": round(total_gain * 100, 2),
        }


    # ----------------------------------------------------------
    # 基础过滤
    # ----------------------------------------------------------

    def filter_candidates(self, candidates: List[Dict]) -> List[Dict]:
        """
        基础过滤：成交额、价差、资金费率
        """
        filtered = []
        for c in candidates:
            symbol = c["symbol"]

            # 成交额过滤
            if c.get("volume_usdt", 0) < self.min_volume_usdt:
                logger.debug(f"{symbol} 成交额不足，跳过")
                continue

            # 价差检查
            if not self._check_spread(symbol):
                continue

            # 资金费率检查
            if not self._check_funding_rate(symbol):
                continue

            filtered.append(c)

        logger.info(f"基础过滤后剩余 {len(filtered)} 个标的")
        return filtered

    def _check_spread(self, symbol: str) -> bool:
        """检查买卖价差"""
        try:
            book = self.client.futures_order_book(symbol=symbol, limit=5)
            best_bid = float(book["bids"][0][0])
            best_ask = float(book["asks"][0][0])
            if best_bid == 0:
                return False
            spread = (best_ask - best_bid) / best_bid
            if spread > self.max_spread_pct:
                logger.debug(f"{symbol} 价差 {spread:.4%} 超过阈值")
                return False
            return True
        except Exception as e:
            logger.warning(f"{symbol} 价差检查失败: {e}")
            return False

    def _check_funding_rate(self, symbol: str) -> bool:
        """检查资金费率"""
        try:
            info = self.client.futures_mark_price(symbol=symbol)
            funding_rate = float(info.get("lastFundingRate", 0))
            if abs(funding_rate) > self.max_funding_rate:
                logger.debug(f"{symbol} 资金费率 {funding_rate:.4%} 超过阈值")
                return False
            return True
        except Exception as e:
            logger.warning(f"{symbol} 资金费率检查失败: {e}")
            return False


    # ----------------------------------------------------------
    # 观察池管理
    # ----------------------------------------------------------

    def load_watchlist(self) -> Dict:
        """加载 watchlist.json"""
        if not os.path.exists(self.watchlist_path):
            return {"manual": [], "auto_discovered": []}
        try:
            with open(self.watchlist_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {"manual": [], "auto_discovered": []}

    def save_watchlist(self, auto_discovered: List[Dict]):
        """保存自动发现的标的到 watchlist.json"""
        os.makedirs(os.path.dirname(self.watchlist_path), exist_ok=True)
        watchlist = self.load_watchlist()
        watchlist["auto_discovered"] = auto_discovered
        with open(self.watchlist_path, "w", encoding="utf-8") as f:
            json.dump(watchlist, f, ensure_ascii=False, indent=2)

    def screen(self) -> List[Dict]:
        """
        完整筛选流程：
        1. 获取涨幅榜前 N
        2. 检测连续拉涨（AND 逻辑）
        3. 基础过滤
        4. 保存结果
        """
        top_gainers = self.get_top_gainers()

        # 检测连续拉涨
        pump_candidates = []
        for gainer in top_gainers:
            symbol = gainer["symbol"]
            pump_info = self.detect_consecutive_pump(symbol)

            if pump_info["is_pump"]:
                gainer.update(pump_info)
                pump_candidates.append(gainer)
                logger.info(
                    f"✓ {symbol} 连续拉涨确认: "
                    f"{pump_info['consecutive_days']}天连阳, "
                    f"每日涨幅{pump_info['daily_gains']}, "
                    f"累计{pump_info['total_gain']}%"
                )

        if not pump_candidates:
            logger.info("未发现符合连续拉涨条件的标的")
            return []

        # 基础过滤
        filtered = self.filter_candidates(pump_candidates)

        # 保存自动发现结果
        auto_discovered = []
        for c in filtered:
            auto_discovered.append({
                "symbol": c["symbol"],
                "discovered_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "consecutive_days": c["consecutive_days"],
                "daily_gains": c["daily_gains"],
                "total_gain": c["total_gain"],
                "reason": (
                    f"连续{c['consecutive_days']}天日线收阳，"
                    f"每日≥{self.daily_min_gain:.0%}，"
                    f"累计涨幅{c['total_gain']}%"
                ),
            })
        self.save_watchlist(auto_discovered)

        return filtered

    def get_observation_pool(self) -> List[Dict]:
        """
        获取观察池：自动筛选结果 + 手动自选
        返回去重后的标的列表
        """
        # 自动筛选
        auto_results = self.screen()
        auto_symbols = {r["symbol"] for r in auto_results}

        # 合并手动自选
        watchlist = self.load_watchlist()
        manual_symbols = [
            item["symbol"] for item in watchlist.get("manual", [])
            if item["symbol"] not in auto_symbols
        ]

        # 手动自选的标的也做基础过滤（只调一次全量接口）
        if manual_symbols:
            try:
                tickers = self.client.futures_ticker()
            except Exception as e:
                logger.warning(f"获取行情失败: {e}")
                tickers = []
            ticker_map = {t["symbol"]: t for t in tickers}

        for symbol in manual_symbols:
            ticker = ticker_map.get(symbol)
            try:
                if ticker:
                    candidate = {
                        "symbol": symbol,
                        "price_change_pct": float(ticker.get("priceChangePercent", 0)),
                        "volume_usdt": float(ticker.get("quoteVolume", 0)),
                        "last_price": float(ticker.get("lastPrice", 0)),
                        "source": "manual",
                    }
                    auto_results.append(candidate)
            except Exception as e:
                logger.warning(f"手动自选 {symbol} 获取行情失败: {e}")

        logger.info(f"观察池共 {len(auto_results)} 个标的")
        return auto_results
