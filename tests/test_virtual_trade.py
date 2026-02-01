"""
虚拟交易测试脚本
演示虚拟下单和PnL回放功能
"""
import sys
import os

# Add parent directory to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.virtual_trade import VirtualTradeManager
from core.pnl import PnLAnalyzer, PnLReplay


def test_basic_virtual_trade():
    """测试基本虚拟交易功能"""
    print("=" * 60)
    print("测试1: 基本虚拟交易功能")
    print("=" * 60)
    
    # 创建虚拟交易管理器，初始资金10000 USDT
    manager = VirtualTradeManager(initial_balance=10000.0)
    
    # 开多单 BTCUSDT
    print("\n[开仓] 买入 0.01 BTC")
    order1 = manager.create_order("BTCUSDT", "BUY", 0.01)
    print(f"订单ID: {order1.order_id}")
    print(f"成交价格: ${order1.filled_price:,.2f}")
    
    # 查看持仓
    position = manager.get_position("BTCUSDT")
    if position:
        current_price = position.avg_price  # 简化，使用开仓价
        print(f"\n持仓信息:")
        print(f"  数量: {position.quantity}")
        print(f"  平均价格: ${position.avg_price:,.2f}")
        print(f"  开仓时间: {position.entry_time}")
    
    # 查看账户摘要
    summary = manager.get_account_summary()
    print(f"\n账户摘要:")
    print(f"  初始资金: ${summary['initial_balance']:,.2f}")
    print(f"  当前余额: ${summary['balance']:,.2f}")
    print(f"  已实现盈亏: ${summary['realized_pnl']:,.2f}")
    print(f"  未实现盈亏: ${summary['total_unrealized_pnl']:,.2f}")
    print(f"  总资产: ${summary['total_balance']:,.2f}")
    print(f"  总收益: ${summary['total_return']:,.2f}")
    print(f"  收益率: {summary['return_rate']:.2f}%")
    
    # 平仓
    print("\n[平仓] 卖出 0.01 BTC")
    order2 = manager.create_order("BTCUSDT", "SELL", 0.01)
    print(f"订单ID: {order2.order_id}")
    print(f"成交价格: ${order2.filled_price:,.2f}")
    
    # 再次查看账户摘要
    summary2 = manager.get_account_summary()
    print(f"\n平仓后账户摘要:")
    print(f"  已实现盈亏: ${summary2['realized_pnl']:,.2f}")
    print(f"  总资产: ${summary2['total_balance']:,.2f}")
    print(f"  总收益: ${summary2['total_return']:,.2f}")
    print(f"  收益率: {summary2['return_rate']:.2f}%")


def test_multiple_positions():
    """测试多个持仓"""
    print("\n" + "=" * 60)
    print("测试2: 多个持仓管理")
    print("=" * 60)
    
    manager = VirtualTradeManager(initial_balance=10000.0)
    
    # 开多个仓位
    print("\n[开仓] 买入 0.01 BTC")
    manager.create_order("BTCUSDT", "BUY", 0.01)
    
    print("[开仓] 买入 1 ETH")
    # ETHUSDT 的精度可能不是 1.0，使用验证后的值
    from core.trade_prep import validate_order_params
    eth_validation = validate_order_params("ETHUSDT", 1.0, None)
    manager.create_order("ETHUSDT", "BUY", eth_validation["quantity"], validate_precision=False)
    
    print("[开仓] 做空 1000 BTR")
    manager.create_order("BTRUSDT", "SELL", 1000.0)
    
    # 查看所有持仓
    print("\n所有持仓:")
    positions = manager.get_all_positions()
    for pos in positions:
        print(f"\n  {pos['symbol']}:")
        print(f"    数量: {pos['quantity']}")
        print(f"    平均价格: ${pos['avg_price']:,.4f}")
        print(f"    当前价格: ${pos['current_price']:,.4f}")
        print(f"    未实现盈亏: ${pos['unrealized_pnl']:,.2f} USDT")
    
    # 账户摘要
    summary = manager.get_account_summary()
    print(f"\n账户总览:")
    print(f"  总资产: ${summary['total_balance']:,.2f}")
    print(f"  总收益: ${summary['total_return']:,.2f}")
    print(f"  收益率: {summary['return_rate']:.2f}%")
    print(f"  持仓数量: {len(summary['positions'])}")
    print(f"  总订单数: {summary['total_orders']}")


def test_pnl_analysis():
    """测试PnL分析"""
    print("\n" + "=" * 60)
    print("测试3: PnL分析")
    print("=" * 60)
    
    manager = VirtualTradeManager(initial_balance=10000.0)
    
    # 模拟一些交易
    print("\n执行模拟交易...")
    manager.create_order("BTCUSDT", "BUY", 0.01)
    # ETHUSDT 精度修正
    from core.trade_prep import validate_order_params
    eth_validation = validate_order_params("ETHUSDT", 1.0, None)
    manager.create_order("ETHUSDT", "BUY", eth_validation["quantity"], validate_precision=False)
    
    # 使用PnL分析器
    analyzer = PnLAnalyzer(manager)
    
    # 获取性能指标
    metrics = analyzer.get_performance_metrics()
    print("\n性能指标:")
    print(f"  初始资金: ${metrics['initial_balance']:,.2f}")
    print(f"  总资产: ${metrics['total_balance']:,.2f}")
    print(f"  总收益: ${metrics['total_return']:,.2f}")
    print(f"  收益率: {metrics['return_rate']:.2f}%")
    print(f"  已实现盈亏: ${metrics['realized_pnl']:,.2f}")
    print(f"  未实现盈亏: ${metrics['total_unrealized_pnl']:,.2f}")
    
    # 分析单个交易对
    print("\nBTCUSDT 分析:")
    btc_pnl = analyzer.calculate_symbol_pnl("BTCUSDT")
    print(f"  订单数: {btc_pnl['total_orders']}")
    print(f"  持仓数量: {btc_pnl['quantity']}")
    print(f"  平均价格: ${btc_pnl['avg_price']:,.2f}")
    print(f"  当前价格: ${btc_pnl['current_price']:,.2f}")
    print(f"  未实现盈亏: ${btc_pnl['unrealized_pnl']:,.2f} USDT")


def test_order_history():
    """测试订单历史"""
    print("\n" + "=" * 60)
    print("测试4: 订单历史")
    print("=" * 60)
    
    manager = VirtualTradeManager(initial_balance=10000.0)
    
    # 执行一些交易
    manager.create_order("BTCUSDT", "BUY", 0.01)
    manager.create_order("BTCUSDT", "BUY", 0.01)  # 加仓
    # ETHUSDT 精度修正
    from core.trade_prep import validate_order_params
    eth_validation = validate_order_params("ETHUSDT", 1.0, None)
    manager.create_order("ETHUSDT", "BUY", eth_validation["quantity"], validate_precision=False)
    manager.create_order("BTCUSDT", "SELL", 0.01)  # 部分平仓
    
    # 查看订单历史
    print("\n所有订单历史:")
    orders = manager.get_order_history()
    for i, order in enumerate(orders, 1):
        print(f"\n订单 {i}:")
        print(f"  ID: {order['order_id']}")
        print(f"  交易对: {order['symbol']}")
        print(f"  方向: {order['side']}")
        print(f"  数量: {order['quantity']}")
        print(f"  成交价: ${order['filled_price']:,.2f}")
        print(f"  时间: {order['timestamp']}")
    
    # 查看BTCUSDT的订单
    print("\nBTCUSDT 订单历史:")
    btc_orders = manager.get_order_history("BTCUSDT")
    for i, order in enumerate(btc_orders, 1):
        print(f"  {i}. {order['side']} {order['quantity']} @ ${order['filled_price']:,.2f}")


if __name__ == "__main__":
    try:
        # 运行所有测试
        test_basic_virtual_trade()
        test_multiple_positions()
        test_pnl_analysis()
        test_order_history()
        
        print("\n" + "=" * 60)
        print("[SUCCESS] 所有测试完成！")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n[ERROR] 错误: {e}")
        import traceback
        traceback.print_exc()
