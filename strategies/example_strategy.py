"""
示例策略 - 简单的移动平均策略
"""
from typing import Dict, Optional
from strategies.base_strategy import BaseStrategy


class ExampleStrategy(BaseStrategy):
    """示例策略：简单移动平均"""
    
    def __init__(self, symbol: str, trade_manager, short_period: int = 5, long_period: int = 20):
        super().__init__(symbol, trade_manager)
        self.short_period = short_period
        self.long_period = long_period
    
    def calculate_ma(self, klines: list, period: int) -> float:
        """计算移动平均"""
        closes = [float(k[4]) for k in klines[-period:]]  # 收盘价
        return sum(closes) / len(closes)
    
    def on_tick(self, current_price: float, klines: list) -> Optional[Dict]:
        """策略逻辑"""
        if len(klines) < self.long_period:
            return None
        
        ma_short = self.calculate_ma(klines, self.short_period)
        ma_long = self.calculate_ma(klines, self.long_period)
        
        position = self.get_position()
        has_position = position and position.quantity != 0
        
        # 金叉：买入信号
        if ma_short > ma_long and not has_position:
            return {
                "side": "BUY",
                "quantity": 0.001,  # 需要根据资金计算
                "price": None  # 市价
            }
        
        # 死叉：卖出信号
        if ma_short < ma_long and has_position:
            return {
                "side": "SELL",
                "quantity": abs(position.quantity),
                "price": None
            }
        
        return None
