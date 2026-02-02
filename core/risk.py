"""
Risk Management Module / 风控模块
实现止盈止损、状态机、补仓逻辑

Created: 2026-02-02
"""
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from enum import Enum


class PositionSide(Enum):
    """持仓方向"""
    LONG = "LONG"  # 做多
    SHORT = "SHORT"  # 做空


class StateMachineStatus(Enum):
    """状态机状态"""
    ACTIVE = "ACTIVE"  # 激活中
    STOPPED_LOSS = "STOPPED_LOSS"  # 止损终止
    TAKEN_PROFIT = "TAKEN_PROFIT"  # 止盈终止
    CLOSED = "CLOSED"  # 手动关闭


class PositionStateMachine:
    """
    持仓状态机
    管理补仓逻辑和状态转移
    """
    def __init__(self, symbol: str, side: PositionSide, initial_capital: float, 
                 leverage: float, reference_price: float):
        """
        初始化状态机
        
        Args:
            symbol: 交易对
            side: 持仓方向（LONG/SHORT）
            initial_capital: 初始资金 C
            leverage: 杠杆倍数 L
            reference_price: 初始参考价 P0
        """
        self.symbol = symbol
        self.side = side
        self.initial_capital = initial_capital
        self.leverage = leverage
        self.reference_price = reference_price
        
        # 状态变量
        self.state = 0  # 当前状态 n ∈ {0,1,2,3}
        self.status = StateMachineStatus.ACTIVE
        self.entry_prices: List[float] = []  # 记录每笔入场价
        self.entry_quantities: List[float] = []  # 记录每笔入场数量
        self.created_at = datetime.now()
        
        # 计算止损价（固定，基于P0）
        if side == PositionSide.LONG:
            self.stop_loss_price = reference_price * (1 - 1.5 / leverage)
        else:  # SHORT
            self.stop_loss_price = reference_price * (1 + 1.5 / leverage)
    
    def get_position_size(self, state: int) -> float:
        """
        获取指定状态的累计仓位
        A_total(n) = C/8 + n·C/16
        """
        return self.initial_capital / 8 + state * self.initial_capital / 16
    
    def get_add_position_size(self) -> float:
        """获取补仓金额（每次固定 C/16）"""
        return self.initial_capital / 16
    
    def can_add_position(self) -> bool:
        """是否可以补仓（最多4笔入场：头仓+3次补仓）"""
        return len(self.entry_prices) < 4 and self.status == StateMachineStatus.ACTIVE
    
    def add_position(self, price: float) -> Dict:
        """
        补仓
        
        Args:
            price: 补仓价格
            
        Returns:
            补仓结果字典
        """
        if not self.can_add_position():
            return {
                "success": False,
                "message": f"Cannot add position: state={self.state}, status={self.status.value}"
            }
        
        self.state += 1
        add_size = self.get_add_position_size()
        quantity = add_size * self.leverage / price  # 考虑杠杆的实际数量
        
        self.entry_prices.append(price)
        self.entry_quantities.append(quantity)
        
        return {
            "success": True,
            "state": self.state,
            "price": price,
            "quantity": quantity,
            "add_size": add_size,
            "total_position_size": self.get_position_size(self.state)
        }
    
    def check_stop_loss(self, current_price: float) -> bool:
        """
        检查止损
        止损只在补满3次仓（state=3）后激活
        
        Args:
            current_price: 当前价格
            
        Returns:
            是否触发止损
        """
        if self.state < 3 or self.status != StateMachineStatus.ACTIVE:
            return False
        
        triggered = False
        if self.side == PositionSide.LONG:
            # 做多：价格跌破止损价
            triggered = current_price <= self.stop_loss_price
        else:  # SHORT
            # 做空：价格突破止损价
            triggered = current_price >= self.stop_loss_price
        
        if triggered:
            self.status = StateMachineStatus.STOPPED_LOSS
        
        return triggered
    
    def check_take_profit(self, current_price: float) -> Tuple[bool, Optional[int]]:
        """
        检查止盈
        任意一笔入场价触发止盈即全平
        
        Args:
            current_price: 当前价格
            
        Returns:
            (是否触发止盈, 触发的入场价索引)
        """
        if self.status != StateMachineStatus.ACTIVE:
            return False, None
        
        for i, entry_price in enumerate(self.entry_prices):
            if self.side == PositionSide.LONG:
                # 做多：(current_price/entry_price - 1) >= 2.0
                profit_rate = (current_price / entry_price - 1)
                if profit_rate >= 2.0:
                    self.status = StateMachineStatus.TAKEN_PROFIT
                    return True, i
            else:  # SHORT
                # 做空：(1 - current_price/entry_price) >= 0.4
                profit_rate = (1 - current_price / entry_price)
                if profit_rate >= 0.4:
                    self.status = StateMachineStatus.TAKEN_PROFIT
                    return True, i
        
        return False, None
    
    def get_total_quantity(self) -> float:
        """获取总持仓数量"""
        return sum(self.entry_quantities)
    
    def get_avg_entry_price(self) -> float:
        """获取平均入场价"""
        if not self.entry_prices or not self.entry_quantities:
            return 0.0
        total_cost = sum(p * q for p, q in zip(self.entry_prices, self.entry_quantities))
        total_quantity = sum(self.entry_quantities)
        return total_cost / total_quantity if total_quantity > 0 else 0.0
    
    def calculate_pnl(self, current_price: float) -> Dict:
        """
        计算当前盈亏
        
        Args:
            current_price: 当前价格
            
        Returns:
            盈亏详情字典
        """
        if not self.entry_prices:
            return {
                "unrealized_pnl": 0.0,
                "return_rate": 0.0,
                "leverage_return_rate": 0.0
            }
        
        total_quantity = self.get_total_quantity()
        avg_price = self.get_avg_entry_price()
        
        if self.side == PositionSide.LONG:
            unrealized_pnl = (current_price - avg_price) * total_quantity
        else:  # SHORT
            unrealized_pnl = (avg_price - current_price) * total_quantity
        
        total_invested = self.get_position_size(self.state)
        return_rate = (unrealized_pnl / total_invested * 100) if total_invested > 0 else 0.0
        leverage_return_rate = return_rate  # 已包含杠杆效应
        
        return {
            "unrealized_pnl": unrealized_pnl,
            "return_rate": return_rate,
            "leverage_return_rate": leverage_return_rate,
            "total_quantity": total_quantity,
            "avg_price": avg_price,
            "total_invested": total_invested
        }
    
    def to_dict(self) -> Dict:
        """转换为字典格式"""
        return {
            "symbol": self.symbol,
            "side": self.side.value,
            "state": self.state,
            "status": self.status.value,
            "initial_capital": self.initial_capital,
            "leverage": self.leverage,
            "reference_price": self.reference_price,
            "stop_loss_price": self.stop_loss_price,
            "entry_prices": self.entry_prices,
            "entry_quantities": self.entry_quantities,
            "total_quantity": self.get_total_quantity(),
            "avg_entry_price": self.get_avg_entry_price(),
            "total_position_size": self.get_position_size(self.state),
            "created_at": self.created_at.isoformat()
        }


class RiskManager:
    """
    风控管理器
    管理多个持仓的风控逻辑
    """
    def __init__(self):
        self.state_machines: Dict[str, PositionStateMachine] = {}
    
    def create_position(self, symbol: str, side: PositionSide, initial_capital: float,
                       leverage: float, reference_price: float, 
                       entry_price: float) -> PositionStateMachine:
        """
        创建新持仓（头仓）
        
        Args:
            symbol: 交易对
            side: 持仓方向
            initial_capital: 初始资金
            leverage: 杠杆
            reference_price: 参考价格P0
            entry_price: 头仓入场价
            
        Returns:
            状态机对象
        """
        if symbol in self.state_machines:
            raise ValueError(f"Position for {symbol} already exists")
        
        sm = PositionStateMachine(symbol, side, initial_capital, leverage, reference_price)
        
        # 开头仓
        initial_size = sm.get_position_size(0)
        initial_quantity = initial_size * leverage / entry_price
        sm.entry_prices.append(entry_price)
        sm.entry_quantities.append(initial_quantity)
        
        self.state_machines[symbol] = sm
        return sm
    
    def get_position(self, symbol: str) -> Optional[PositionStateMachine]:
        """获取持仓状态机"""
        return self.state_machines.get(symbol)
    
    def check_all_positions(self, prices: Dict[str, float]) -> List[Dict]:
        """
        检查所有持仓的风控状态
        
        Args:
            prices: {symbol: current_price} 当前价格字典
            
        Returns:
            触发的风控事件列表
        """
        events = []
        
        for symbol, sm in self.state_machines.items():
            if sm.status != StateMachineStatus.ACTIVE:
                continue
            
            current_price = prices.get(symbol)
            if current_price is None:
                continue
            
            # 检查止损
            if sm.check_stop_loss(current_price):
                events.append({
                    "type": "STOP_LOSS",
                    "symbol": symbol,
                    "current_price": current_price,
                    "stop_loss_price": sm.stop_loss_price,
                    "state": sm.state,
                    "pnl": sm.calculate_pnl(current_price)
                })
            
            # 检查止盈
            take_profit, entry_idx = sm.check_take_profit(current_price)
            if take_profit:
                events.append({
                    "type": "TAKE_PROFIT",
                    "symbol": symbol,
                    "current_price": current_price,
                    "triggered_entry_price": sm.entry_prices[entry_idx],
                    "entry_index": entry_idx,
                    "pnl": sm.calculate_pnl(current_price)
                })
        
        return events
    
    def close_position(self, symbol: str):
        """关闭持仓"""
        if symbol in self.state_machines:
            self.state_machines[symbol].status = StateMachineStatus.CLOSED


def generate_state_transition_table(initial_capital: float = 10000, 
                                    leverage: float = 5,
                                    reference_price: float = 100) -> Dict:
    """
    生成数值状态转移表
    展示不同场景下的盈亏状态
    
    Args:
        initial_capital: 初始资金 C
        leverage: 杠杆 L
        reference_price: 参考价格 P0
        
    Returns:
        状态转移表字典
    """
    tables = {
        "parameters": {
            "initial_capital": initial_capital,
            "leverage": leverage,
            "reference_price": reference_price
        },
        "long_scenarios": [],
        "short_scenarios": []
    }
    
    # 做多场景
    print("=" * 80)
    print("做多场景 (LONG Position)")
    print("=" * 80)
    
    sm_long = PositionStateMachine("BTCUSDT", PositionSide.LONG, initial_capital, 
                                   leverage, reference_price)
    
    # 头仓
    sm_long.add_position(reference_price)
    
    print(f"\n初始参数:")
    print(f"  初始资金 C: ${initial_capital:,.2f}")
    print(f"  杠杆 L: {leverage}x")
    print(f"  参考价格 P0: ${reference_price:.2f}")
    print(f"  止损价: ${sm_long.stop_loss_price:.2f} (P0 × 0.7)")
    print(f"  止盈条件: 任意入场价上涨 200%")
    
    print(f"\n状态 0 (头仓):")
    print(f"  仓位金额: ${sm_long.get_position_size(0):,.2f} (C/8)")
    print(f"  入场价: ${reference_price:.2f}")
    print(f"  入场数量: {sm_long.entry_quantities[0]:.6f}")
    
    # 补仓场景
    add_prices = [90, 80, 70]  # 假设下跌补仓
    for i, add_price in enumerate(add_prices, 1):
        if sm_long.can_add_position():
            result = sm_long.add_position(add_price)
            print(f"\n状态 {i} (补仓{i}):")
            print(f"  补仓价格: ${add_price:.2f}")
            print(f"  补仓金额: ${result['add_size']:,.2f} (C/16)")
            print(f"  补仓数量: {result['quantity']:.6f}")
            print(f"  累计仓位: ${result['total_position_size']:,.2f} (C/8 + {i}·C/16)")
            print(f"  平均成本: ${sm_long.get_avg_entry_price():.2f}")
    
    print(f"\n止损激活: 补满3次仓后，止损价生效 = ${sm_long.stop_loss_price:.2f}")
    
    # 测试不同价格场景
    test_prices = [
        ("大幅止盈", 300, "entry_0上涨200%"),
        ("小幅盈利", 120, "盈利但未达止盈"),
        ("轻微亏损", 85, "state<3, 止损未激活"),
        ("触发止损", 69, "state=3, 触达止损价")
    ]
    
    print(f"\n价格场景测试:")
    for scenario_name, test_price, desc in test_prices:
        pnl = sm_long.calculate_pnl(test_price)
        stop_loss = sm_long.check_stop_loss(test_price)
        take_profit, tp_idx = sm_long.check_take_profit(test_price)
        
        scenario = {
            "name": scenario_name,
            "price": test_price,
            "description": desc,
            "pnl": pnl['unrealized_pnl'],
            "return_rate": pnl['return_rate'],
            "stop_loss": stop_loss,
            "take_profit": take_profit
        }
        tables["long_scenarios"].append(scenario)
        
        print(f"\n  {scenario_name}: 价格 ${test_price:.2f} ({desc})")
        print(f"    未实现盈亏: ${pnl['unrealized_pnl']:,.2f}")
        print(f"    回报率: {pnl['return_rate']:.2f}%")
        print(f"    止损触发: {'是' if stop_loss else '否'}")
        print(f"    止盈触发: {'是' if take_profit else '否'}" + 
              (f" (入场价{tp_idx})" if take_profit else ""))
        
        # 重置状态机状态以便下次测试
        if sm_long.status != StateMachineStatus.ACTIVE:
            sm_long.status = StateMachineStatus.ACTIVE
    
    # 做空场景
    print("\n" + "=" * 80)
    print("做空场景 (SHORT Position)")
    print("=" * 80)
    
    sm_short = PositionStateMachine("ETHUSDT", PositionSide.SHORT, initial_capital, 
                                    leverage, reference_price)
    
    # 头仓
    sm_short.add_position(reference_price)
    
    print(f"\n初始参数:")
    print(f"  初始资金 C: ${initial_capital:,.2f}")
    print(f"  杠杆 L: {leverage}x")
    print(f"  参考价格 P0: ${reference_price:.2f}")
    print(f"  止损价: ${sm_short.stop_loss_price:.2f} (P0 × 1.3)")
    print(f"  止盈条件: 任意入场价下跌 40%")
    
    print(f"\n状态 0 (头仓):")
    print(f"  仓位金额: ${sm_short.get_position_size(0):,.2f} (C/8)")
    print(f"  入场价: ${reference_price:.2f}")
    print(f"  入场数量: {sm_short.entry_quantities[0]:.6f}")
    
    # 补仓场景（上涨补仓）
    add_prices_short = [110, 120, 130]
    for i, add_price in enumerate(add_prices_short, 1):
        if sm_short.can_add_position():
            result = sm_short.add_position(add_price)
            print(f"\n状态 {i} (补仓{i}):")
            print(f"  补仓价格: ${add_price:.2f}")
            print(f"  补仓金额: ${result['add_size']:,.2f} (C/16)")
            print(f"  补仓数量: {result['quantity']:.6f}")
            print(f"  累计仓位: ${result['total_position_size']:,.2f} (C/8 + {i}·C/16)")
            print(f"  平均成本: ${sm_short.get_avg_entry_price():.2f}")
    
    print(f"\n止损激活: 补满3次仓后，止损价生效 = ${sm_short.stop_loss_price:.2f}")
    
    # 测试不同价格场景
    test_prices_short = [
        ("大幅止盈", 60, "entry_0下跌40%"),
        ("小幅盈利", 85, "盈利但未达止盈"),
        ("轻微亏损", 115, "state<3, 止损未激活"),
        ("触发止损", 131, "state=3, 触达止损价")
    ]
    
    print(f"\n价格场景测试:")
    for scenario_name, test_price, desc in test_prices_short:
        pnl = sm_short.calculate_pnl(test_price)
        stop_loss = sm_short.check_stop_loss(test_price)
        take_profit, tp_idx = sm_short.check_take_profit(test_price)
        
        scenario = {
            "name": scenario_name,
            "price": test_price,
            "description": desc,
            "pnl": pnl['unrealized_pnl'],
            "return_rate": pnl['return_rate'],
            "stop_loss": stop_loss,
            "take_profit": take_profit
        }
        tables["short_scenarios"].append(scenario)
        
        print(f"\n  {scenario_name}: 价格 ${test_price:.2f} ({desc})")
        print(f"    未实现盈亏: ${pnl['unrealized_pnl']:,.2f}")
        print(f"    回报率: {pnl['return_rate']:.2f}%")
        print(f"    止损触发: {'是' if stop_loss else '否'}")
        print(f"    止盈触发: {'是' if take_profit else '否'}" + 
              (f" (入场价{tp_idx})" if take_profit else ""))
        
        # 重置状态机状态
        if sm_short.status != StateMachineStatus.ACTIVE:
            sm_short.status = StateMachineStatus.ACTIVE
    
    print("\n" + "=" * 80)
    
    return tables
