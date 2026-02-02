"""
Risk Management Demo / 风控模块演示
展示如何使用风控模块进行交易管理

Created: 2026-02-02
"""
import sys
sys.path.insert(0, '.')

from core.risk import RiskManager, PositionSide, generate_state_transition_table


def demo_long_position():
    """演示做多持仓的风控管理"""
    print("\n" + "=" * 70)
    print("做多持仓风控演示 / LONG Position Risk Management Demo")
    print("=" * 70)
    
    # 创建风控管理器
    rm = RiskManager()
    
    # 参数设置
    symbol = "BTCUSDT"
    initial_capital = 10000  # $10,000 初始资金
    leverage = 5             # 5x 杠杆
    reference_price = 50000  # $50,000 参考价格
    
    print(f"\n初始参数:")
    print(f"  交易对: {symbol}")
    print(f"  初始资金: ${initial_capital:,.2f}")
    print(f"  杠杆: {leverage}x")
    print(f"  参考价格: ${reference_price:,.2f}")
    
    # 创建做多持仓（开头仓）
    position = rm.create_position(
        symbol=symbol,
        side=PositionSide.LONG,
        initial_capital=initial_capital,
        leverage=leverage,
        reference_price=reference_price,
        entry_price=reference_price
    )
    
    print(f"\n头仓信息:")
    print(f"  入场价: ${position.entry_prices[0]:,.2f}")
    print(f"  仓位金额: ${position.get_position_size(0):,.2f} (C/8)")
    print(f"  入场数量: {position.entry_quantities[0]:.6f} BTC")
    print(f"  止损价: ${position.stop_loss_price:,.2f} (P0 × 0.7)")
    print(f"  止盈条件: 任意入场价上涨 200%")
    
    # 模拟价格下跌，触发补仓
    add_prices = [48000, 46000, 44000]
    print(f"\n价格下跌，开始补仓:")
    
    for i, add_price in enumerate(add_prices, 1):
        result = position.add_position(add_price)
        print(f"\n  补仓 {i}: 价格 ${add_price:,.2f}")
        print(f"    补仓金额: ${result['add_size']:,.2f} (C/16)")
        print(f"    补仓数量: {result['quantity']:.6f} BTC")
        print(f"    累计仓位: ${result['total_position_size']:,.2f}")
        print(f"    平均成本: ${position.get_avg_entry_price():,.2f}")
        print(f"    当前状态: state={position.state}")
    
    print(f"\n补满3次仓后，止损激活！")
    print(f"  止损价: ${position.stop_loss_price:,.2f}")
    
    # 测试不同价格场景
    print(f"\n场景测试:")
    
    test_scenarios = [
        (35000, "跌破止损价，触发止损"),
        (47000, "小幅反弹，未触发任何事件"),
        (150000, "大幅上涨，头仓触发止盈（50000×3）"),
    ]
    
    for test_price, desc in test_scenarios:
        # 重置状态机以便测试
        if position.status.value != "ACTIVE":
            from core.risk import StateMachineStatus
            position.status = StateMachineStatus.ACTIVE
        
        # 计算盈亏
        pnl = position.calculate_pnl(test_price)
        
        # 检查风控事件
        events = rm.check_all_positions({symbol: test_price})
        
        print(f"\n  价格 ${test_price:,.2f} - {desc}")
        print(f"    未实现盈亏: ${pnl['unrealized_pnl']:,.2f}")
        print(f"    回报率: {pnl['return_rate']:.2f}%")
        
        if events:
            event = events[0]
            if event['type'] == 'STOP_LOSS':
                print(f"    [STOP LOSS] 触发止损！全平仓位，状态机终止")
            elif event['type'] == 'TAKE_PROFIT':
                print(f"    [TAKE PROFIT] 触发止盈！入场价 ${event['triggered_entry_price']:,.2f} 达标")
                print(f"    全平仓位，状态机终止")
        else:
            print(f"    [NO EVENT] 无风控事件触发")


def demo_short_position():
    """演示做空持仓的风控管理"""
    print("\n" + "=" * 70)
    print("做空持仓风控演示 / SHORT Position Risk Management Demo")
    print("=" * 70)
    
    rm = RiskManager()
    
    symbol = "ETHUSDT"
    initial_capital = 10000
    leverage = 5
    reference_price = 3000
    
    print(f"\n初始参数:")
    print(f"  交易对: {symbol}")
    print(f"  初始资金: ${initial_capital:,.2f}")
    print(f"  杠杆: {leverage}x")
    print(f"  参考价格: ${reference_price:,.2f}")
    
    # 创建做空持仓
    position = rm.create_position(
        symbol=symbol,
        side=PositionSide.SHORT,
        initial_capital=initial_capital,
        leverage=leverage,
        reference_price=reference_price,
        entry_price=reference_price
    )
    
    print(f"\n头仓信息:")
    print(f"  入场价: ${position.entry_prices[0]:,.2f}")
    print(f"  仓位金额: ${position.get_position_size(0):,.2f} (C/8)")
    print(f"  入场数量: {position.entry_quantities[0]:.6f} ETH")
    print(f"  止损价: ${position.stop_loss_price:,.2f} (P0 × 1.3)")
    print(f"  止盈条件: 任意入场价下跌 40%")
    
    # 模拟价格上涨，触发补仓
    add_prices = [3200, 3400, 3600]
    print(f"\n价格上涨，开始补仓:")
    
    for i, add_price in enumerate(add_prices, 1):
        result = position.add_position(add_price)
        print(f"\n  补仓 {i}: 价格 ${add_price:,.2f}")
        print(f"    补仓金额: ${result['add_size']:,.2f} (C/16)")
        print(f"    补仓数量: {result['quantity']:.6f} ETH")
        print(f"    累计仓位: ${result['total_position_size']:,.2f}")
        print(f"    平均成本: ${position.get_avg_entry_price():,.2f}")
        print(f"    当前状态: state={position.state}")
    
    print(f"\n补满3次仓后，止损激活！")
    print(f"  止损价: ${position.stop_loss_price:,.2f}")
    
    # 测试场景
    print(f"\n场景测试:")
    
    test_scenarios = [
        (3900, "突破止损价，触发止损"),
        (3100, "小幅回落，未触发任何事件"),
        (1800, "大幅下跌，头仓触发止盈（3000×0.6）"),
    ]
    
    for test_price, desc in test_scenarios:
        if position.status.value != "ACTIVE":
            from core.risk import StateMachineStatus
            position.status = StateMachineStatus.ACTIVE
        
        pnl = position.calculate_pnl(test_price)
        events = rm.check_all_positions({symbol: test_price})
        
        print(f"\n  价格 ${test_price:,.2f} - {desc}")
        print(f"    未实现盈亏: ${pnl['unrealized_pnl']:,.2f}")
        print(f"    回报率: {pnl['return_rate']:.2f}%")
        
        if events:
            event = events[0]
            if event['type'] == 'STOP_LOSS':
                print(f"    [STOP LOSS] 触发止损！全平仓位，状态机终止")
            elif event['type'] == 'TAKE_PROFIT':
                print(f"    [TAKE PROFIT] 触发止盈！入场价 ${event['triggered_entry_price']:,.2f} 达标")
                print(f"    全平仓位，状态机终止")
        else:
            print(f"    [NO EVENT] 无风控事件触发")


def demo_state_transition_table():
    """演示状态转移表生成"""
    print("\n" + "=" * 70)
    print("状态转移表生成 / State Transition Table Generation")
    print("=" * 70)
    print("\n生成详细的数值状态转移表...\n")
    
    tables = generate_state_transition_table(
        initial_capital=10000,
        leverage=5,
        reference_price=100
    )
    
    print("\n状态转移表生成完成！")
    print(f"  做多场景数量: {len(tables['long_scenarios'])}")
    print(f"  做空场景数量: {len(tables['short_scenarios'])}")


if __name__ == "__main__":
    print("=" * 70)
    print("风控模块演示程序")
    print("Risk Management Module Demo")
    print("=" * 70)
    
    demo_long_position()
    demo_short_position()
    demo_state_transition_table()
    
    print("\n" + "=" * 70)
    print("演示完成！")
    print("Demo completed!")
    print("=" * 70)
