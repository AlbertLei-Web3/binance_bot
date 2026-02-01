"""
PnL 计算和回放模块
用于分析虚拟交易的盈亏表现
"""
import json
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from core.virtual_trade import VirtualTradeManager, VirtualOrder
from core.market import get_mark_price, get_klines


class PnLAnalyzer:
    """PnL 分析器"""
    def __init__(self, trade_manager: VirtualTradeManager):
        self.trade_manager = trade_manager
    
    def calculate_daily_pnl(self) -> List[Dict]:
        """计算每日PnL"""
        daily_pnl = {}
        
        # 按日期分组订单
        for order in self.trade_manager.orders:
            date = order.timestamp.date()
            if date not in daily_pnl:
                daily_pnl[date] = {
                    "date": date.isoformat(),
                    "orders": [],
                    "realized_pnl": 0.0,
                    "order_count": 0
                }
            daily_pnl[date]["orders"].append(order.to_dict())
            daily_pnl[date]["order_count"] += 1
        
        # 计算每日已实现盈亏（简化版，实际需要更复杂的计算）
        result = []
        for date_str, data in sorted(daily_pnl.items()):
            result.append(data)
        
        return result
    
    def calculate_symbol_pnl(self, symbol: str) -> Dict:
        """计算某个交易对的PnL"""
        symbol_orders = [o for o in self.trade_manager.orders if o.symbol == symbol]
        position = self.trade_manager.get_position(symbol)
        
        if not position:
            return {
                "symbol": symbol,
                "total_orders": 0,
                "unrealized_pnl": 0.0,
                "has_position": False
            }
        
        current_price = get_mark_price(symbol)
        unrealized_pnl = position.get_unrealized_pnl(current_price)
        
        return {
            "symbol": symbol,
            "total_orders": len(symbol_orders),
            "quantity": position.quantity,
            "avg_price": position.avg_price,
            "current_price": current_price,
            "unrealized_pnl": unrealized_pnl,
            "has_position": True
        }
    
    def get_performance_metrics(self) -> Dict:
        """获取性能指标"""
        summary = self.trade_manager.get_account_summary()
        
        # 计算胜率（简化版）
        winning_trades = 0
        losing_trades = 0
        
        # 分析每个持仓的盈亏
        for symbol, position in self.trade_manager.positions.items():
            if position.quantity == 0:
                continue
            current_price = get_mark_price(symbol)
            pnl = position.get_unrealized_pnl(current_price)
            if pnl > 0:
                winning_trades += 1
            elif pnl < 0:
                losing_trades += 1
        
        total_trades = winning_trades + losing_trades
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
        
        return {
            **summary,
            "winning_trades": winning_trades,
            "losing_trades": losing_trades,
            "total_trades": total_trades,
            "win_rate": win_rate
        }


class PnLReplay:
    """PnL 回放器 - 基于历史K线数据回放交易"""
    def __init__(self, initial_balance: float = 10000.0):
        self.trade_manager = VirtualTradeManager(initial_balance)
        self.replay_data: List[Dict] = []
    
    def replay_from_klines(self, symbol: str, interval: str = "1h", limit: int = 100,
                          orders: List[Dict] = None) -> List[Dict]:
        """
        基于历史K线数据回放交易
        
        Args:
            symbol: 交易对
            interval: K线周期
            limit: K线数量
            orders: 订单列表，格式: [{"timestamp": "2024-01-01T10:00:00", "side": "BUY", "quantity": 0.1, "price": 50000}, ...]
        
        Returns:
            回放结果列表
        """
        # 获取历史K线
        klines = get_klines(symbol, interval=interval, limit=limit)
        
        # 如果没有提供订单，使用当前虚拟交易管理器的订单
        if orders is None:
            orders = [o.to_dict() for o in self.trade_manager.orders if o.symbol == symbol]
        
        # 按时间排序订单
        orders_sorted = sorted(orders, key=lambda x: x.get("timestamp", ""))
        
        replay_results = []
        current_kline_idx = 0
        
        for order_data in orders_sorted:
            order_time = datetime.fromisoformat(order_data["timestamp"].replace("Z", "+00:00"))
            
            # 找到对应的K线
            while current_kline_idx < len(klines):
                kline_time = datetime.fromtimestamp(klines[current_kline_idx][0] / 1000)
                if kline_time >= order_time:
                    break
                current_kline_idx += 1
            
            # 使用K线的收盘价作为成交价
            if current_kline_idx < len(klines):
                kline = klines[current_kline_idx]
                close_price = float(kline[4])  # 收盘价
                
                # 执行订单
                order = self.trade_manager.create_order(
                    symbol=symbol,
                    side=order_data["side"],
                    quantity=order_data["quantity"],
                    price=close_price
                )
                
                # 记录回放状态
                snapshot = self.trade_manager.get_account_summary()
                snapshot["replay_time"] = kline_time.isoformat()
                snapshot["replay_price"] = close_price
                replay_results.append(snapshot)
        
        return replay_results
    
    def export_replay_data(self, filepath: str):
        """导出回放数据到JSON文件"""
        data = {
            "initial_balance": self.trade_manager.initial_balance,
            "orders": [o.to_dict() for o in self.trade_manager.orders],
            "final_summary": self.trade_manager.get_account_summary()
        }
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    def load_replay_data(self, filepath: str):
        """从JSON文件加载回放数据"""
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        self.trade_manager = VirtualTradeManager(data["initial_balance"])
        for order_data in data["orders"]:
            # 重建订单和持仓
            order = VirtualOrder(
                order_id=order_data["order_id"],
                symbol=order_data["symbol"],
                side=order_data["side"],
                quantity=order_data["quantity"],
                price=order_data["price"],
                order_type=order_data.get("order_type", "MARKET")
            )
            order.timestamp = datetime.fromisoformat(order_data["timestamp"])
            order.filled_price = order_data["filled_price"]
            order.filled_quantity = order_data["filled_quantity"]
            
            if order.symbol not in self.trade_manager.positions:
                from core.virtual_trade import VirtualPosition
                self.trade_manager.positions[order.symbol] = VirtualPosition(order.symbol)
            
            self.trade_manager.positions[order.symbol].update_position(order)
            self.trade_manager.orders.append(order)
