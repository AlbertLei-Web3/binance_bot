"""
策略基类 - 所有交易策略的基础类
"""
from abc import ABC, abstractmethod
from typing import Dict, Optional
from core.virtual_trade import VirtualTradeManager
from core.market import get_mark_price, get_klines
from core.trade_prep import TradePreparator


class BaseStrategy(ABC):
    """策略基类"""
    
    def __init__(self, symbol: str, trade_manager: VirtualTradeManager):
        self.symbol = symbol
        self.trade_manager = trade_manager
        self.preparator = TradePreparator()
        self.is_running = False
    
    @abstractmethod
    def on_tick(self, current_price: float, klines: list) -> Optional[Dict]:
        """
        每个tick的处理逻辑（必须实现）
        
        Args:
            current_price: 当前价格
            klines: K线数据
        
        Returns:
            订单信息字典或None
            {
                "side": "BUY" or "SELL",
                "quantity": float,
                "price": float (可选)
            }
        """
        pass
    
    def should_open_position(self) -> bool:
        """判断是否应该开仓（可重写）"""
        return True
    
    def should_close_position(self) -> bool:
        """判断是否应该平仓（可重写）"""
        return False
    
    def run_once(self):
        """执行一次策略逻辑"""
        current_price = get_mark_price(self.symbol)
        klines = get_klines(self.symbol, interval="1m", limit=100)
        
        order_info = self.on_tick(current_price, klines)
        
        if order_info:
            order = self.trade_manager.create_order(
                symbol=self.symbol,
                side=order_info["side"],
                quantity=order_info["quantity"],
                price=order_info.get("price")
            )
            return order
        return None
    
    def get_position(self):
        """获取当前持仓"""
        return self.trade_manager.get_position(self.symbol)
    
    def get_account_summary(self):
        """获取账户摘要"""
        return self.trade_manager.get_account_summary()
