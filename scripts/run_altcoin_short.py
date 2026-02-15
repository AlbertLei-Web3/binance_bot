"""
山寨币做空策略 - 运行脚本
每 5 分钟执行一次完整周期：标的发现 → 信号评估 → 持仓管理
"""
import sys
import os
import time
import yaml
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.virtual_trade import VirtualTradeManager
from core.risk import RiskManager
from strategies.screener import AltcoinScreener
from strategies.signal_engine import SignalEngine
from strategies.altcoin_short_strategy import AltcoinShortStrategy
from utils.logger import setup_logger

logger = setup_logger("run_altcoin_short")

# 默认配置路径
CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "config", "config.yaml"
)


def load_config() -> dict:
    """加载配置文件"""
    if not os.path.exists(CONFIG_PATH):
        logger.warning(f"配置文件不存在: {CONFIG_PATH}，使用默认配置")
        return {}
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def build_strategy(config: dict) -> AltcoinShortStrategy:
    """根据配置构建策略实例"""
    strategy_cfg = config.get("altcoin_short", {})
    screener_cfg = config.get("screener", {})
    initial_balance = strategy_cfg.get("total_capital", 100000)

    trade_manager = VirtualTradeManager(initial_balance=float(initial_balance))
    risk_manager = RiskManager()
    screener = AltcoinScreener(config=screener_cfg)
    signal_engine = SignalEngine()

    return AltcoinShortStrategy(
        trade_manager=trade_manager,
        risk_manager=risk_manager,
        screener=screener,
        signal_engine=signal_engine,
        config=strategy_cfg,
    )


def print_cycle_result(result: dict):
    """格式化输出周期结果"""
    pool = result.get("observation_pool", [])
    new_pos = result.get("new_positions", [])
    events = result.get("position_events", [])

    logger.info(f"观察池 ({len(pool)}): {pool}")

    for p in new_pos:
        logger.info(
            f"★ 新开仓 {p['symbol']} @ {p['price']:.4f}, "
            f"头仓={p['head_size']:.2f} USDT, "
            f"信号={p['signals']}, 得分={p['score']:.2f}"
        )

    for e in events:
        etype = e.get("type", "")
        symbol = e.get("symbol", "")
        if etype == "STOP_LOSS":
            pnl = e.get("pnl", {})
            logger.info(f"✗ {symbol} 止损 PnL={pnl.get('unrealized_pnl', 0):.2f}")
        elif etype == "TAKE_PROFIT":
            pnl = e.get("pnl", {})
            logger.info(f"✓ {symbol} 止盈 PnL={pnl.get('unrealized_pnl', 0):.2f}")
        elif etype == "ADD_POSITION":
            logger.info(f"↑ {symbol} 补仓第{e.get('state')}次 @ {e.get('price', 0):.4f}")
        elif etype == "CLOSE":
            logger.info(f"✗ {symbol} 平仓（{e.get('reason')}）")


def print_status(strategy: AltcoinShortStrategy):
    """输出策略状态摘要"""
    status = strategy.get_status()
    account = status.get("account", {})

    logger.info("=" * 50)
    logger.info(
        f"持仓: {status['active_positions']}/{status['max_positions']} | "
        f"总资产: {account.get('total_balance', 0):,.2f} | "
        f"收益率: {account.get('return_rate', 0):.2f}%"
    )

    for pos in status.get("positions", []):
        logger.info(
            f"  {pos['symbol']} state={pos['state']} "
            f"均价={pos['avg_price']:.4f} "
            f"现价={pos['current_price']:.4f} "
            f"PnL={pos['pnl']:.2f} ({pos['return_rate']:.2f}%)"
        )
    logger.info("=" * 50)


def main():
    """主函数"""
    config = load_config()
    strategy = build_strategy(config)
    cycle_interval = config.get("altcoin_short", {}).get("cycle_interval_sec", 300)

    logger.info("=" * 50)
    logger.info("山寨币做空策略启动")
    logger.info(f"周期间隔: {cycle_interval}s")
    logger.info("=" * 50)

    cycle_count = 0
    try:
        while True:
            cycle_count += 1
            start = datetime.now()
            logger.info(f"\n--- 周期 #{cycle_count} [{start.strftime('%H:%M:%S')}] ---")

            try:
                result = strategy.run_cycle()
                print_cycle_result(result)
            except Exception as e:
                logger.error(f"周期执行异常: {e}", exc_info=True)

            # 每 3 个周期输出完整状态
            if cycle_count % 3 == 0:
                print_status(strategy)

            elapsed = (datetime.now() - start).total_seconds()
            sleep_time = max(0, cycle_interval - elapsed)
            if sleep_time > 0:
                logger.info(f"等待 {sleep_time:.0f}s 后进入下一周期...")
                time.sleep(sleep_time)

    except KeyboardInterrupt:
        logger.info("\n策略停止，输出最终状态：")
        print_status(strategy)


if __name__ == "__main__":
    main()
