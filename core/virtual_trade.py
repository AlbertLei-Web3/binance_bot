"""
虚拟交易模块 - 模拟下单和持仓管理
不调用真实API，仅用于策略回测和模拟交易
"""
import time
from typing import Dict, List, Optional
from datetime import datetime
from core.market import get_mark_price
from core.trade_prep import validate_order_params


class VirtualOrder:
    """虚拟订单类"""
    def __init__(self, order_id: str, symbol: str, side: str, quantity: float, 
                 price: float, order_type: str = "MARKET"):
        self.order_id = order_id
        self.symbol = symbol
        self.side = side.upper()  # BUY or SELL
        self.quantity = abs(quantity)
        self.price = price
        self.order_type = order_type
        self.status = "FILLED"  # 虚拟订单默认立即成交
        self.timestamp = datetime.now()
        self.filled_price = price
        self.filled_quantity = quantity
        
    def to_dict(self) -> Dict:
        """转换为字典格式"""
        return {
            "order_id": self.order_id,
            "symbol": self.symbol,
            "side": self.side,
            "quantity": self.quantity,
            "price": self.price,
            "filled_price": self.filled_price,
            "filled_quantity": self.filled_quantity,
            "order_type": self.order_type,
            "status": self.status,
            "timestamp": self.timestamp.isoformat()
        }


class VirtualPosition:
    """虚拟持仓类"""
    def __init__(self, symbol: str):
        self.symbol = symbol
        self.quantity = 0.0  # 正数=多单，负数=空单
        self.avg_price = 0.0  # 平均开仓价
        self.entry_time = None
        self.orders: List[VirtualOrder] = []  # 相关订单
        
    def update_position(self, order: VirtualOrder):
        """更新持仓"""
        if self.quantity == 0:
            # 新开仓
            self.quantity = order.filled_quantity if order.side == "BUY" else -order.filled_quantity
            self.avg_price = order.filled_price
            self.entry_time = order.timestamp
        else:
            # 加仓或减仓
            old_quantity = self.quantity
            old_avg_price = self.avg_price
            
            if order.side == "BUY":
                new_quantity = old_quantity + order.filled_quantity
            else:  # SELL
                new_quantity = old_quantity - order.filled_quantity
            
            # 计算新的平均价格
            if (old_quantity > 0 and new_quantity > 0) or (old_quantity < 0 and new_quantity < 0):
                # 同向加仓
                total_cost = abs(old_quantity) * old_avg_price + order.filled_quantity * order.filled_price
                self.avg_price = total_cost / abs(new_quantity)
            elif abs(new_quantity) < abs(old_quantity):
                # 减仓，平均价不变
                self.avg_price = old_avg_price
            else:
                # 反向开仓（平掉原仓位并反向）
                self.avg_price = order.filled_price
            
            self.quantity = new_quantity
            if self.quantity == 0:
                self.entry_time = None
        
        self.orders.append(order)
    
    def get_unrealized_pnl(self, current_price: float) -> float:
        """计算未实现盈亏"""
        if self.quantity == 0:
            return 0.0
        return (current_price - self.avg_price) * self.quantity
    
    def to_dict(self, current_price: float = None) -> Dict:
        """转换为字典格式"""
        result = {
            "symbol": self.symbol,
            "quantity": self.quantity,
            "avg_price": self.avg_price,
            "entry_time": self.entry_time.isoformat() if self.entry_time else None,
            "order_count": len(self.orders)
        }
        if current_price:
            result["current_price"] = current_price
            result["unrealized_pnl"] = self.get_unrealized_pnl(current_price)
        return result


class VirtualTradeManager:
    """虚拟交易管理器"""
    def __init__(self, initial_balance: float = 10000.0):
        self.initial_balance = initial_balance
        self.balance = initial_balance
        self.positions: Dict[str, VirtualPosition] = {}  # symbol -> VirtualPosition
        self.orders: List[VirtualOrder] = []  # 所有订单历史
        self.order_counter = 0
        self.realized_pnl = 0.0  # 已实现盈亏
        
    def _generate_order_id(self) -> str:
        """生成订单ID"""
        self.order_counter += 1
        return f"VIRTUAL_{int(time.time() * 1000)}_{self.order_counter}"
    
    def create_order(self, symbol: str, side: str, quantity: float, 
                    price: Optional[float] = None, validate_precision: bool = True) -> VirtualOrder:
        """
        创建虚拟订单
        
        Args:
            symbol: 交易对，如 "BTCUSDT"
            side: 方向，"BUY" 或 "SELL"
            quantity: 数量（正数）
            price: 价格，如果为None则使用当前标记价格
            validate_precision: 是否验证精度（默认True）
        
        Returns:
            VirtualOrder对象
        
        Raises:
            ValueError: 如果精度验证失败
        """
        # 验证精度
        if validate_precision:
            validation = validate_order_params(symbol, quantity, price)
            if not validation["valid"]:
                raise ValueError(f"订单参数精度错误: {', '.join(validation['messages'])}")
            quantity = validation["quantity"]
            if price is not None:
                price = validation["price"]
        
        if price is None:
            price = get_mark_price(symbol)
            # 如果使用市场价格，也需要验证精度
            if validate_precision:
                validation = validate_order_params(symbol, quantity, price)
                price = validation["price"]
        
        order_id = self._generate_order_id()
        order = VirtualOrder(order_id, symbol, side, quantity, price)
        
        # 更新持仓
        if symbol not in self.positions:
            self.positions[symbol] = VirtualPosition(symbol)
        
        old_quantity = self.positions[symbol].quantity
        old_avg_price = self.positions[symbol].avg_price if old_quantity != 0 else 0.0
        self.positions[symbol].update_position(order)
        new_quantity = self.positions[symbol].quantity
        
        # 计算已实现盈亏（平仓时）
        if old_quantity != 0 and (old_quantity > 0) != (new_quantity > 0):
            # 完全反向，计算平仓盈亏（使用旧的平均价格）
            realized_pnl = (price - old_avg_price) * old_quantity
            self.realized_pnl += realized_pnl
        elif old_quantity != 0 and abs(new_quantity) < abs(old_quantity):
            # 部分平仓（使用旧的平均价格）
            closed_quantity = abs(old_quantity) - abs(new_quantity)
            realized_pnl = (price - old_avg_price) * (
                closed_quantity if old_quantity > 0 else -closed_quantity
            )
            self.realized_pnl += realized_pnl
        
        # 记录订单
        self.orders.append(order)
        
        return order
    
    def get_position(self, symbol: str) -> Optional[VirtualPosition]:
        """获取持仓"""
        return self.positions.get(symbol)
    
    def get_all_positions(self) -> List[Dict]:
        """获取所有持仓信息（包含当前价格和未实现盈亏）"""
        result = []
        for symbol, position in self.positions.items():
            if position.quantity != 0:
                current_price = get_mark_price(symbol)
                result.append(position.to_dict(current_price))
        return result
    
    def get_account_summary(self) -> Dict:
        """获取账户摘要"""
        total_unrealized_pnl = 0.0
        positions_info = []
        
        for symbol, position in self.positions.items():
            if position.quantity != 0:
                current_price = get_mark_price(symbol)
                unrealized_pnl = position.get_unrealized_pnl(current_price)
                total_unrealized_pnl += unrealized_pnl
                positions_info.append(position.to_dict(current_price))
        
        total_balance = self.balance + self.realized_pnl + total_unrealized_pnl
        
        return {
            "initial_balance": self.initial_balance,
            "balance": self.balance,
            "realized_pnl": self.realized_pnl,
            "total_unrealized_pnl": total_unrealized_pnl,
            "total_balance": total_balance,
            "total_return": total_balance - self.initial_balance,
            "return_rate": (total_balance - self.initial_balance) / self.initial_balance * 100,
            "positions": positions_info,
            "total_orders": len(self.orders)
        }
    
    def get_order_history(self, symbol: Optional[str] = None) -> List[Dict]:
        """获取订单历史"""
        orders = self.orders
        if symbol:
            orders = [o for o in orders if o.symbol == symbol]
        return [o.to_dict() for o in orders]
