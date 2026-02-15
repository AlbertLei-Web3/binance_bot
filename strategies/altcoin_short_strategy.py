"""
山寨币做空策略
两阶段模型：标的发现（screener）→ 择时入场（signal_engine）
集成风控模块管理持仓
"""
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from core.client import get_client
from core.market import get_mark_price, get_klines
from core.risk import RiskManager, PositionSide, PositionStateMachine, StateMachineStatus
from core.virtual_trade import VirtualTradeManager
from strategies.screener import AltcoinScreener
from strategies.signal_engine import SignalEngine
from utils.indicators import calculate_atr, get_closes_from_klines
from utils.logger import setup_logger

logger = setup_logger("altcoin_short")


# 默认策略配置
DEFAULT_CONFIG = {
    "total_capital": 100000,
    "max_per_symbol": 0.10,           # 单币种最大占比 10%
    "leverage": 5,
    "min_signals": 3,
    "min_signal_score": 0.6,
    "max_positions": 5,
    "funding_rate_threshold": 0.0015,
    "max_hold_hours": 48,
    "pump_detect_days": 3,
    "daily_min_gain": 0.12,
    "total_min_gain": 1.00,
    # 补仓阈值（基础值，会根据 ATR 动态调整）
    "add_position_thresholds": [0.08, 0.15, 0.25],
    # 补仓最小间隔（分钟）
    "add_position_interval_min": 30,
    # 极端行情阈值
    "extreme_candle_pct": 0.20,
    "extreme_hour_pct": 0.30,
    # 引爆信号配置
    "ignition_klines_5m_limit": 30,
    "ignition_klines_15m_limit": 30,
    "require_ignition_for_entry": False,
}


class AltcoinShortStrategy:
    """
    山寨币做空策略

    工作流：
    1. screener 获取观察池（连续拉涨标的）
    2. signal_engine 对每个标的评估入场信号
    3. 满足条件则开空仓，创建风控状态机
    4. 持续监控持仓：补仓、止盈止损、异常保护
    """

    def __init__(self,
                 trade_manager: VirtualTradeManager,
                 risk_manager: RiskManager,
                 screener: AltcoinScreener,
                 signal_engine: SignalEngine,
                 config: Dict = None):
        self.trade_manager = trade_manager
        self.risk_manager = risk_manager
        self.screener = screener
        self.signal_engine = signal_engine
        self.config = {**DEFAULT_CONFIG, **(config or {})}
        self.client = get_client()

        # 持仓元数据：{symbol: {opened_at, last_add_at, ...}}
        self._position_meta: Dict[str, Dict] = {}


    # ==============================================================
    # 主循环
    # ==============================================================

    def run_cycle(self) -> Dict:
        """
        执行一个完整周期

        Returns:
            {
                "observation_pool": [...],
                "new_positions": [...],
                "position_events": [...],
            }
        """
        result = {
            "observation_pool": [],
            "new_positions": [],
            "position_events": [],
        }

        # 阶段一：标的发现
        pool = self.screener.get_observation_pool()
        result["observation_pool"] = [p["symbol"] for p in pool]
        logger.info(f"观察池: {result['observation_pool']}")

        # 阶段二：对观察池中的标的评估入场
        active_count = self._get_active_position_count()
        max_pos = self.config["max_positions"]

        for candidate in pool:
            if active_count >= max_pos:
                logger.info(f"已达最大持仓数 {max_pos}，停止评估新标的")
                break

            symbol = candidate["symbol"]

            # 已有持仓则跳过
            if self.risk_manager.get_position(symbol):
                continue

            entry_result = self._evaluate_and_enter(symbol)
            if entry_result:
                result["new_positions"].append(entry_result)
                active_count += 1

        # 阶段三：管理现有持仓
        events = self._check_all_positions()
        result["position_events"] = events

        return result


    # ==============================================================
    # 入场逻辑
    # ==============================================================

    def _evaluate_and_enter(self, symbol: str) -> Optional[Dict]:
        """评估信号并决定是否入场"""
        try:
            klines = get_klines(symbol, interval="1h", limit=100)
            current_price = get_mark_price(symbol)
        except Exception as e:
            logger.warning(f"{symbol} 获取数据失败: {e}")
            return None

        # 极端行情检查
        if self._check_extreme_market(klines):
            logger.info(f"{symbol} 检测到极端行情，跳过")
            return None

        # 第一轮：仅用 1h 数据做初步信号分析
        signals = self.signal_engine.analyze(klines, current_price)

        # 优化 API 调用：1h 信号 >= 2 个时才拉取短周期数据
        klines_5m = None
        klines_15m = None
        if len(signals) >= 2:
            try:
                limit_5m = self.config["ignition_klines_5m_limit"]
                limit_15m = self.config["ignition_klines_15m_limit"]
                klines_5m = get_klines(symbol, interval="5m", limit=limit_5m)
                klines_15m = get_klines(symbol, interval="15m", limit=limit_15m)
            except Exception as e:
                logger.debug(f"{symbol} 获取短周期数据失败: {e}")

            # 第二轮：带短周期数据重新分析（引爆信号会追加到列表）
            if klines_5m and klines_15m:
                signals = self.signal_engine.analyze(
                    klines, current_price,
                    klines_5m=klines_5m, klines_15m=klines_15m,
                )

        score = self.signal_engine.get_signal_score(signals)
        require_ignition = self.config["require_ignition_for_entry"]
        should_enter = self.signal_engine.should_enter(
            signals,
            min_score=self.config["min_signal_score"],
            min_signals=self.config["min_signals"],
            require_ignition=require_ignition,
        )

        signal_names = [s.name for s in signals]
        logger.info(
            f"{symbol} 信号评估: 得分={score:.2f}, "
            f"信号数={len(signals)}, 信号={signal_names}, "
            f"入场={'是' if should_enter else '否'}"
        )

        if not should_enter:
            return None

        return self._open_short(symbol, current_price, signals, score)

    def _open_short(self, symbol: str, price: float,
                    signals: list, score: float) -> Dict:
        """开空仓"""
        cfg = self.config
        # 单币种分配资金 = 总资金 × max_per_symbol
        allocated = cfg["total_capital"] * cfg["max_per_symbol"]
        # initial_capital = allocated × 16/5（补满仓后 5C/16 = allocated）
        initial_capital = allocated * 16 / 5
        leverage = cfg["leverage"]

        # 创建风控状态机
        sm = self.risk_manager.create_position(
            symbol=symbol,
            side=PositionSide.SHORT,
            initial_capital=initial_capital,
            leverage=leverage,
            reference_price=price,
            entry_price=price,
        )

        # 虚拟下单（头仓）— 直接从状态机获取已计算的数量
        head_size = initial_capital / 8  # C/8
        quantity = sm.entry_quantities[0]
        self.trade_manager.create_order(
            symbol=symbol, side="SELL", quantity=quantity, price=price
        )

        # 记录元数据
        self._position_meta[symbol] = {
            "opened_at": datetime.now(),
            "last_add_at": datetime.now(),
            "signals": [s.name for s in signals],
            "entry_score": score,
        }

        logger.info(
            f"★ 开空 {symbol} @ {price:.4f}, "
            f"头仓={head_size:.2f} USDT, 杠杆={leverage}x, "
            f"止损={sm.stop_loss_price:.4f}"
        )

        return {
            "symbol": symbol,
            "side": "SHORT",
            "price": price,
            "head_size": head_size,
            "signals": [s.name for s in signals],
            "score": score,
        }


    # ==============================================================
    # 持仓管理
    # ==============================================================

    def _check_all_positions(self) -> List[Dict]:
        """检查所有持仓：止盈止损、补仓、异常保护"""
        events = []
        symbols_to_check = list(self.risk_manager.state_machines.keys())

        for symbol in symbols_to_check:
            sm = self.risk_manager.get_position(symbol)
            if not sm or sm.status != StateMachineStatus.ACTIVE:
                continue

            try:
                current_price = get_mark_price(symbol)
            except Exception as e:
                logger.warning(f"{symbol} 获取价格失败: {e}")
                continue

            # 1. 风控检查（止盈止损）
            risk_event = self._check_risk_events(symbol, sm, current_price)
            if risk_event:
                events.append(risk_event)
                continue  # 已平仓，跳过后续检查

            # 2. 资金费率检查
            if self._should_close_funding_rate(symbol):
                event = self._close_position(symbol, current_price, "资金费率过高")
                events.append(event)
                continue

            # 3. 持仓超时检查
            if self._should_close_timeout(symbol):
                event = self._close_position(symbol, current_price, "持仓超时")
                events.append(event)
                continue

            # 4. 极端行情检查
            try:
                klines = get_klines(symbol, interval="1h", limit=5)
                if self._check_extreme_market(klines):
                    event = self._close_position(symbol, current_price, "极端行情保护")
                    events.append(event)
                    continue
            except Exception:
                pass

            # 5. 补仓检查
            add_event = self._check_add_position(symbol, sm, current_price)
            if add_event:
                events.append(add_event)

            # 6. 输出持仓状态
            pnl = sm.calculate_pnl(current_price)
            logger.debug(
                f"{symbol} 状态: state={sm.state}, "
                f"均价={sm.get_avg_entry_price():.4f}, "
                f"PnL={pnl['unrealized_pnl']:.2f}, "
                f"回报率={pnl['return_rate']:.2f}%"
            )

        return events

    def _check_risk_events(self, symbol: str,
                           sm: PositionStateMachine,
                           current_price: float) -> Optional[Dict]:
        """检查止盈止损"""
        # 止损
        if sm.check_stop_loss(current_price):
            pnl = sm.calculate_pnl(current_price)
            self._execute_close(symbol, current_price)
            logger.info(f"✗ {symbol} 止损触发 @ {current_price:.4f}, PnL={pnl['unrealized_pnl']:.2f}")
            return {"type": "STOP_LOSS", "symbol": symbol, "price": current_price, "pnl": pnl}

        # 止盈
        take_profit, entry_idx = sm.check_take_profit(current_price)
        if take_profit:
            pnl = sm.calculate_pnl(current_price)
            self._execute_close(symbol, current_price)
            logger.info(f"✓ {symbol} 止盈触发 @ {current_price:.4f}, PnL={pnl['unrealized_pnl']:.2f}")
            return {"type": "TAKE_PROFIT", "symbol": symbol, "price": current_price, "pnl": pnl}

        return None


    # ==============================================================
    # 补仓逻辑
    # ==============================================================

    def _check_add_position(self, symbol: str,
                            sm: PositionStateMachine,
                            current_price: float) -> Optional[Dict]:
        """检查是否需要补仓（做空方向：价格上涨触发补仓）"""
        if not sm.can_add_position():
            return None

        # 补仓间隔检查
        meta = self._position_meta.get(symbol, {})
        last_add = meta.get("last_add_at")
        interval_min = self.config["add_position_interval_min"]
        if last_add and (datetime.now() - last_add).total_seconds() < interval_min * 60:
            return None

        # 动态补仓阈值（基于 ATR 调整）
        thresholds = self._get_dynamic_thresholds(symbol)
        ref_price = sm.reference_price
        current_state = sm.state  # 0=头仓, 1=补仓1次, ...

        if current_state >= len(thresholds):
            return None

        threshold = thresholds[current_state]
        # 做空：价格上涨超过阈值才补仓
        trigger_price = ref_price * (1 + threshold)

        if current_price < trigger_price:
            return None

        # 执行补仓
        result = sm.add_position(current_price)
        if not result.get("success"):
            return None

        # 虚拟下单
        quantity = result["quantity"]
        self.trade_manager.create_order(
            symbol=symbol, side="SELL", quantity=quantity, price=current_price
        )

        # 更新元数据
        if symbol in self._position_meta:
            self._position_meta[symbol]["last_add_at"] = datetime.now()

        logger.info(
            f"↑ {symbol} 补仓{sm.state}次 @ {current_price:.4f}, "
            f"补仓金额={result['add_size']:.2f}, "
            f"累计仓位={result['total_position_size']:.2f}"
        )

        return {
            "type": "ADD_POSITION",
            "symbol": symbol,
            "state": sm.state,
            "price": current_price,
            "add_size": result["add_size"],
        }

    def _get_dynamic_thresholds(self, symbol: str) -> List[float]:
        """根据 ATR 动态调整补仓阈值"""
        base = self.config["add_position_thresholds"]
        try:
            klines = get_klines(symbol, interval="1h", limit=30)
            atr = calculate_atr(klines, 14)
            closes = get_closes_from_klines(klines)
            if not closes or closes[-1] == 0:
                return base
            atr_pct = atr / closes[-1]
            # ATR 占比越大，阈值越宽
            factor = max(1.0, atr_pct / 0.02)  # 基准 ATR 2%
            return [t * factor for t in base]
        except Exception:
            return base


    # ==============================================================
    # 保护机制
    # ==============================================================

    def _should_close_funding_rate(self, symbol: str) -> bool:
        """资金费率过高则平仓"""
        try:
            info = self.client.futures_mark_price(symbol=symbol)
            rate = float(info.get("lastFundingRate", 0))
            threshold = self.config["funding_rate_threshold"]
            if rate > threshold:
                logger.info(f"{symbol} 资金费率 {rate:.4%} 超过阈值 {threshold:.4%}")
                return True
        except Exception:
            pass
        return False

    def _should_close_timeout(self, symbol: str) -> bool:
        """持仓超时检查"""
        meta = self._position_meta.get(symbol, {})
        opened_at = meta.get("opened_at")
        if not opened_at:
            return False
        max_hours = self.config["max_hold_hours"]
        return (datetime.now() - opened_at).total_seconds() > max_hours * 3600

    def _check_extreme_market(self, klines: list) -> bool:
        """极端行情检测"""
        if not klines:
            return False

        extreme_candle = self.config["extreme_candle_pct"]
        extreme_hour = self.config["extreme_hour_pct"]

        # 单根 K 线涨跌幅检查
        for k in klines[-3:]:
            o, c = float(k[1]), float(k[4])
            if o == 0:
                continue
            change = abs(c - o) / o
            if change > extreme_candle:
                return True

        # 最近几根 K 线累计涨跌幅
        if len(klines) >= 3:
            first_open = float(klines[-3][1])
            last_close = float(klines[-1][4])
            if first_open > 0:
                total_change = abs(last_close - first_open) / first_open
                if total_change > extreme_hour:
                    return True

        return False

    # ==============================================================
    # 平仓执行
    # ==============================================================

    def _close_position(self, symbol: str, current_price: float,
                        reason: str) -> Dict:
        """策略级平仓"""
        sm = self.risk_manager.get_position(symbol)
        pnl = sm.calculate_pnl(current_price) if sm else {}
        self._execute_close(symbol, current_price)
        logger.info(f"✗ {symbol} 平仓（{reason}）@ {current_price:.4f}")
        return {"type": "CLOSE", "symbol": symbol, "reason": reason,
                "price": current_price, "pnl": pnl}

    def _execute_close(self, symbol: str, current_price: float):
        """执行平仓：虚拟买入 + 关闭风控状态机"""
        sm = self.risk_manager.get_position(symbol)
        if sm:
            total_qty = sm.get_total_quantity()
            if total_qty > 0:
                self.trade_manager.create_order(
                    symbol=symbol, side="BUY",
                    quantity=total_qty, price=current_price
                )
            self.risk_manager.close_position(symbol)

        # 清理元数据
        self._position_meta.pop(symbol, None)

    # ==============================================================
    # 工具方法
    # ==============================================================

    def _get_active_position_count(self) -> int:
        """获取活跃持仓数"""
        return sum(
            1 for sm in self.risk_manager.state_machines.values()
            if sm.status == StateMachineStatus.ACTIVE
        )

    def get_status(self) -> Dict:
        """获取策略状态摘要"""
        positions = []
        for symbol, sm in self.risk_manager.state_machines.items():
            if sm.status != StateMachineStatus.ACTIVE:
                continue
            try:
                price = get_mark_price(symbol)
                pnl = sm.calculate_pnl(price)
            except Exception:
                pnl = {}
                price = 0

            meta = self._position_meta.get(symbol, {})
            positions.append({
                "symbol": symbol,
                "state": sm.state,
                "avg_price": sm.get_avg_entry_price(),
                "current_price": price,
                "pnl": pnl.get("unrealized_pnl", 0),
                "return_rate": pnl.get("return_rate", 0),
                "opened_at": str(meta.get("opened_at", "")),
                "signals": meta.get("signals", []),
            })

        return {
            "active_positions": len(positions),
            "max_positions": self.config["max_positions"],
            "positions": positions,
            "account": self.trade_manager.get_account_summary(),
        }
