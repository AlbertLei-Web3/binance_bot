"""
测试风控模块
Test Risk Management Module

Created: 2026-02-02
"""
import sys
sys.path.insert(0, '.')

from core.risk import (
    RiskManager, PositionStateMachine, PositionSide, 
    StateMachineStatus, generate_state_transition_table
)


def test_long_position_basic():
    """测试做多基本逻辑"""
    print("\n" + "=" * 60)
    print("测试1: 做多基本逻辑")
    print("=" * 60)
    
    # 创建做多状态机
    sm = PositionStateMachine(
        symbol="BTCUSDT",
        side=PositionSide.LONG,
        initial_capital=10000,
        leverage=5,
        reference_price=100
    )
    
    print(f"\n初始状态:")
    print(f"  止损价: ${sm.stop_loss_price:.2f} (应为 100 × 0.7 = 70)")
    
    # 头仓（通过构造函数时需要手动添加）
    sm.entry_prices.append(100)
    sm.entry_quantities.append(sm.get_position_size(0) * sm.leverage / 100)
    print(f"\n头仓 (state={sm.state}):")
    print(f"  价格: $100.00")
    print(f"  数量: {sm.entry_quantities[0]:.6f}")
    print(f"  仓位金额: ${sm.get_position_size(0):,.2f}")
    
    # 补仓3次
    for i, price in enumerate([90, 80, 70], 1):
        result = sm.add_position(price)
        print(f"\n补仓{i}:")
        print(f"  价格: ${price:.2f}")
        print(f"  数量: {result['quantity']:.6f}")
        print(f"  累计仓位: ${result['total_position_size']:,.2f}")
    
    print(f"\n平均成本: ${sm.get_avg_entry_price():.2f}")
    print(f"总数量: {sm.get_total_quantity():.6f}")
    
    # 测试止损（只在state=3时生效）
    print(f"\n测试止损:")
    print(f"  当前状态: {sm.state}")
    print(f"  价格70（止损价）: 止损{'触发' if sm.check_stop_loss(70) else '未触发'}")
    print(f"  价格69（低于止损价）: 止损{'触发' if sm.check_stop_loss(69) else '未触发'}")
    
    # 重置状态机
    sm.status = StateMachineStatus.ACTIVE
    
    # 测试止盈
    print(f"\n测试止盈:")
    take_profit, idx = sm.check_take_profit(300)  # 100 * 3 = 300
    print(f"  价格300 (头仓100涨200%): 止盈{'触发' if take_profit else '未触发'}" + 
          (f", 触发入场价索引{idx}" if take_profit else ""))
    
    sm.status = StateMachineStatus.ACTIVE
    take_profit, idx = sm.check_take_profit(270)  # 90 * 3 = 270
    print(f"  价格270 (补仓1的90涨200%): 止盈{'触发' if take_profit else '未触发'}" + 
          (f", 触发入场价索引{idx}" if take_profit else ""))
    
    # 计算盈亏
    print(f"\n盈亏计算:")
    for test_price in [70, 85, 100, 150, 300]:
        pnl = sm.calculate_pnl(test_price)
        print(f"  价格${test_price}: 盈亏${pnl['unrealized_pnl']:,.2f}, "
              f"回报率{pnl['return_rate']:.2f}%")


def test_short_position_basic():
    """测试做空基本逻辑"""
    print("\n" + "=" * 60)
    print("测试2: 做空基本逻辑")
    print("=" * 60)
    
    # 创建做空状态机
    sm = PositionStateMachine(
        symbol="ETHUSDT",
        side=PositionSide.SHORT,
        initial_capital=10000,
        leverage=5,
        reference_price=100
    )
    
    print(f"\n初始状态:")
    print(f"  止损价: ${sm.stop_loss_price:.2f} (应为 100 × 1.3 = 130)")
    
    # 头仓（通过构造函数时需要手动添加）
    sm.entry_prices.append(100)
    sm.entry_quantities.append(sm.get_position_size(0) * sm.leverage / 100)
    print(f"\n头仓 (state={sm.state}):")
    print(f"  价格: $100.00")
    print(f"  数量: {sm.entry_quantities[0]:.6f}")
    print(f"  仓位金额: ${sm.get_position_size(0):,.2f}")
    
    # 补仓3次（价格上涨时补仓）
    for i, price in enumerate([110, 120, 130], 1):
        result = sm.add_position(price)
        print(f"\n补仓{i}:")
        print(f"  价格: ${price:.2f}")
        print(f"  数量: {result['quantity']:.6f}")
        print(f"  累计仓位: ${result['total_position_size']:,.2f}")
    
    print(f"\n平均成本: ${sm.get_avg_entry_price():.2f}")
    print(f"总数量: {sm.get_total_quantity():.6f}")
    
    # 测试止损
    print(f"\n测试止损:")
    print(f"  当前状态: {sm.state}")
    print(f"  价格130（止损价）: 止损{'触发' if sm.check_stop_loss(130) else '未触发'}")
    print(f"  价格131（高于止损价）: 止损{'触发' if sm.check_stop_loss(131) else '未触发'}")
    
    # 重置状态机
    sm.status = StateMachineStatus.ACTIVE
    
    # 测试止盈（下跌40%）
    print(f"\n测试止盈:")
    take_profit, idx = sm.check_take_profit(60)  # 100 * 0.6 = 60 (下跌40%)
    print(f"  价格60 (头仓100跌40%): 止盈{'触发' if take_profit else '未触发'}" + 
          (f", 触发入场价索引{idx}" if take_profit else ""))
    
    sm.status = StateMachineStatus.ACTIVE
    take_profit, idx = sm.check_take_profit(66)  # 110 * 0.6 = 66 (下跌40%)
    print(f"  价格66 (补仓1的110跌40%): 止盈{'触发' if take_profit else '未触发'}" + 
          (f", 触发入场价索引{idx}" if take_profit else ""))
    
    # 计算盈亏
    print(f"\n盈亏计算:")
    for test_price in [60, 85, 100, 120, 150]:
        pnl = sm.calculate_pnl(test_price)
        print(f"  价格${test_price}: 盈亏${pnl['unrealized_pnl']:,.2f}, "
              f"回报率{pnl['return_rate']:.2f}%")


def test_risk_manager():
    """测试风控管理器"""
    print("\n" + "=" * 60)
    print("测试3: 风控管理器")
    print("=" * 60)
    
    rm = RiskManager()
    
    # 创建做多持仓
    print("\n创建做多持仓 BTCUSDT:")
    sm_long = rm.create_position(
        symbol="BTCUSDT",
        side=PositionSide.LONG,
        initial_capital=10000,
        leverage=5,
        reference_price=50000,
        entry_price=50000
    )
    print(f"  头仓: 价格${sm_long.entry_prices[0]:,.2f}, 数量{sm_long.entry_quantities[0]:.6f}")
    
    # 补仓
    for price in [48000, 46000, 44000]:
        result = sm_long.add_position(price)
        print(f"  补仓: 价格${price:,.2f}, 累计仓位${result['total_position_size']:,.2f}")
    
    # 创建做空持仓
    print("\n创建做空持仓 ETHUSDT:")
    sm_short = rm.create_position(
        symbol="ETHUSDT",
        side=PositionSide.SHORT,
        initial_capital=10000,
        leverage=5,
        reference_price=3000,
        entry_price=3000
    )
    print(f"  头仓: 价格${sm_short.entry_prices[0]:,.2f}, 数量{sm_short.entry_quantities[0]:.6f}")
    
    # 检查所有持仓
    print("\n检查风控事件:")
    
    # 场景1：止盈触发
    events = rm.check_all_positions({
        "BTCUSDT": 150000,  # 50000 * 3 = 150000 (上涨200%)
        "ETHUSDT": 3200
    })
    print(f"\n  场景1 - BTC涨到150000:")
    for event in events:
        print(f"    事件类型: {event['type']}")
        print(f"    标的: {event['symbol']}")
        print(f"    当前价格: ${event['current_price']:,.2f}")
        if event['type'] == 'TAKE_PROFIT':
            print(f"    触发入场价: ${event['triggered_entry_price']:,.2f}")
        print(f"    盈亏: ${event['pnl']['unrealized_pnl']:,.2f}")
        print(f"    回报率: {event['pnl']['return_rate']:.2f}%")
    
    # 重置
    sm_long.status = StateMachineStatus.ACTIVE
    
    # 场景2：止损触发
    events = rm.check_all_positions({
        "BTCUSDT": 34000,  # 50000 * 0.7 = 35000 (跌破止损)
        "ETHUSDT": 2000
    })
    print(f"\n  场景2 - BTC跌到34000 (跌破止损价35000):")
    for event in events:
        print(f"    事件类型: {event['type']}")
        print(f"    标的: {event['symbol']}")
        print(f"    当前价格: ${event['current_price']:,.2f}")
        if event['type'] == 'STOP_LOSS':
            print(f"    止损价: ${event['stop_loss_price']:,.2f}")
        print(f"    盈亏: ${event['pnl']['unrealized_pnl']:,.2f}")
        print(f"    回报率: {event['pnl']['return_rate']:.2f}%")


def test_state_transition_table():
    """测试状态转移表生成"""
    print("\n" + "=" * 60)
    print("测试4: 生成状态转移表")
    print("=" * 60)
    
    tables = generate_state_transition_table(
        initial_capital=10000,
        leverage=5,
        reference_price=100
    )
    
    return tables


if __name__ == "__main__":
    test_long_position_basic()
    test_short_position_basic()
    test_risk_manager()
    test_state_transition_table()
    
    print("\n" + "=" * 60)
    print("所有测试完成")
    print("=" * 60)
