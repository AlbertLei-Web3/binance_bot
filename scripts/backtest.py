"""
回测脚本 - 基于历史K线数据回测策略
"""
import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.virtual_trade import VirtualTradeManager
from core.pnl import PnLAnalyzer, PnLReplay
from strategies.example_strategy import ExampleStrategy
from core.market import get_klines


def backtest_strategy(symbol: str = "BTCUSDT", initial_balance: float = 10000.0,
                     interval: str = "1h", limit: int = 100):
    """
    回测策略
    
    Args:
        symbol: 交易对
        initial_balance: 初始资金
        interval: K线周期
        limit: K线数量
    """
    print("=" * 60)
    print("策略回测")
    print("=" * 60)
    print(f"交易对: {symbol}")
    print(f"初始资金: ${initial_balance:,.2f}")
    print(f"K线周期: {interval}")
    print(f"K线数量: {limit}")
    print()
    
    # 初始化
    manager = VirtualTradeManager(initial_balance=initial_balance)
    strategy = ExampleStrategy(symbol, manager)
    
    # 获取历史K线
    print("获取历史K线数据...")
    klines = get_klines(symbol, interval=interval, limit=limit)
    print(f"获取到 {len(klines)} 根K线")
    print()
    
    # 模拟回测
    print("开始回测...")
    order_count = 0
    
    for i, kline in enumerate(klines):
        # 使用K线的收盘价作为当前价格
        current_price = float(kline[4])  # 收盘价
        
        # 获取到当前K线的历史数据
        historical_klines = klines[:i+1]
        
        # 执行策略逻辑
        order_info = strategy.on_tick(current_price, historical_klines)
        
        if order_info:
            # 使用K线收盘价作为成交价（关闭精度验证，因为K线价格可能不符合精度要求）
            order = manager.create_order(
                symbol=symbol,
                side=order_info["side"],
                quantity=order_info["quantity"],
                price=current_price,
                validate_precision=False
            )
            order_count += 1
            timestamp = datetime.fromtimestamp(kline[0] / 1000)
            print(f"[{timestamp}] {order.side} {order.quantity} @ ${order.filled_price:,.2f}")
    
    print()
    print("=" * 60)
    print("回测结果")
    print("=" * 60)
    
    # 分析结果
    analyzer = PnLAnalyzer(manager)
    metrics = analyzer.get_performance_metrics()
    
    print(f"初始资金: ${metrics['initial_balance']:,.2f}")
    print(f"最终资产: ${metrics['total_balance']:,.2f}")
    print(f"总收益: ${metrics['total_return']:,.2f}")
    print(f"收益率: {metrics['return_rate']:.2f}%")
    print(f"已实现盈亏: ${metrics['realized_pnl']:,.2f}")
    print(f"未实现盈亏: ${metrics['total_unrealized_pnl']:,.2f}")
    print(f"总订单数: {order_count}")
    print(f"胜率: {metrics.get('win_rate', 0):.2f}%")
    
    # 显示持仓
    positions = manager.get_all_positions()
    if positions:
        print("\n当前持仓:")
        for pos in positions:
            print(f"  {pos['symbol']}: {pos['quantity']} @ ${pos['avg_price']:,.2f} "
                  f"(未实现盈亏: ${pos['unrealized_pnl']:,.2f})")
    
    return manager, analyzer


if __name__ == "__main__":
    try:
        backtest_strategy(symbol="BTCUSDT", initial_balance=10000.0, 
                         interval="1h", limit=100)
    except Exception as e:
        print(f"\n[ERROR] 错误: {e}")
        import traceback
        traceback.print_exc()
