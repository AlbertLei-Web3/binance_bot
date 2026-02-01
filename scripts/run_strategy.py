"""
运行策略的主脚本
"""
import sys
import os
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.virtual_trade import VirtualTradeManager
from strategies.example_strategy import ExampleStrategy
from utils.logger import get_strategy_logger


def main():
    """主函数"""
    # 初始化
    manager = VirtualTradeManager(initial_balance=10000.0)
    strategy = ExampleStrategy("BTCUSDT", manager)
    logger = get_strategy_logger("example_strategy")
    
    logger.info("=" * 60)
    logger.info("策略开始运行")
    logger.info("=" * 60)
    
    try:
        tick_count = 0
        while True:
            tick_count += 1
            logger.info(f"\n--- Tick #{tick_count} ---")
            
            # 执行策略
            order = strategy.run_once()
            
            if order:
                logger.info(f"执行订单: {order.side} {order.quantity} @ ${order.filled_price:,.2f}")
            
            # 显示账户状态（每10个tick显示一次）
            if tick_count % 10 == 0:
                summary = strategy.get_account_summary()
                logger.info(f"账户状态 - 总资产: ${summary['total_balance']:,.2f} | "
                          f"收益: ${summary['total_return']:,.2f} ({summary['return_rate']:.2f}%)")
            
            # 等待
            time.sleep(60)  # 每分钟执行一次
            
    except KeyboardInterrupt:
        logger.info("\n策略停止")
        # 显示最终结果
        summary = strategy.get_account_summary()
        logger.info("\n最终账户状态:")
        logger.info(f"  总资产: ${summary['total_balance']:,.2f}")
        logger.info(f"  总收益: ${summary['total_return']:,.2f}")
        logger.info(f"  收益率: {summary['return_rate']:.2f}%")
        logger.info(f"  总订单数: {summary['total_orders']}")


if __name__ == "__main__":
    main()
