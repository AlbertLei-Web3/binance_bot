"""
交易准备模块 - 处理杠杆、保证金模式、精度检查
⚠️ 注意：当前为只读阶段，这些函数仅用于准备和验证，不实际调用API
"""
from typing import Dict, Optional, Tuple
from core.client import get_client


class TradePreparator:
    """交易准备器 - 确保交易前的安全设置"""
    
    def __init__(self):
        self.client = get_client()
        self._exchange_info_cache: Optional[Dict] = None
        self._symbol_info_cache: Dict[str, Dict] = {}
    
    def get_exchange_info(self, use_cache: bool = True) -> Dict:
        """获取交易所信息（包含精度规则）"""
        if not use_cache or self._exchange_info_cache is None:
            self._exchange_info_cache = self.client.futures_exchange_info()
        return self._exchange_info_cache
    
    def get_symbol_info(self, symbol: str, use_cache: bool = True) -> Dict:
        """获取单个交易对的详细信息"""
        if not use_cache or symbol not in self._symbol_info_cache:
            exchange_info = self.get_exchange_info(use_cache)
            for s in exchange_info.get("symbols", []):
                if s["symbol"] == symbol:
                    self._symbol_info_cache[symbol] = s
                    return s
            raise ValueError(f"交易对 {symbol} 不存在")
        return self._symbol_info_cache[symbol]
    
    def get_step_size(self, symbol: str) -> float:
        """
        获取数量精度（最小变动单位）
        
        Returns:
            stepSize: 例如 0.001 表示数量最小为 0.001
        """
        symbol_info = self.get_symbol_info(symbol)
        for filter_item in symbol_info.get("filters", []):
            if filter_item["filterType"] == "LOT_SIZE":
                step_size = float(filter_item["stepSize"])
                return step_size
        raise ValueError(f"无法获取 {symbol} 的 stepSize")
    
    def get_tick_size(self, symbol: str) -> float:
        """
        获取价格精度（最小变动单位）
        
        Returns:
            tickSize: 例如 0.01 表示价格最小为 0.01
        """
        symbol_info = self.get_symbol_info(symbol)
        for filter_item in symbol_info.get("filters", []):
            if filter_item["filterType"] == "PRICE_FILTER":
                tick_size = float(filter_item["tickSize"])
                return tick_size
        raise ValueError(f"无法获取 {symbol} 的 tickSize")
    
    def validate_quantity(self, symbol: str, quantity: float) -> Tuple[bool, str, float]:
        """
        验证并修正数量精度
        
        Returns:
            (is_valid, message, corrected_quantity)
        """
        step_size = self.get_step_size(symbol)
        
        # 计算应该的数量（向下取整到stepSize的倍数）
        corrected_quantity = (quantity // step_size) * step_size
        
        if abs(quantity - corrected_quantity) > 1e-10:
            return False, f"数量精度错误，已修正: {quantity} -> {corrected_quantity}", corrected_quantity
        
        return True, "数量精度正确", quantity
    
    def validate_price(self, symbol: str, price: float) -> Tuple[bool, str, float]:
        """
        验证并修正价格精度
        
        Returns:
            (is_valid, message, corrected_price)
        """
        tick_size = self.get_tick_size(symbol)
        
        # 计算应该的价格（向下取整到tickSize的倍数）
        corrected_price = (price // tick_size) * tick_size
        
        if abs(price - corrected_price) > 1e-10:
            return False, f"价格精度错误，已修正: {price} -> {corrected_price}", corrected_price
        
        return True, "价格精度正确", price
    
    def get_min_quantity(self, symbol: str) -> float:
        """获取最小交易数量"""
        symbol_info = self.get_symbol_info(symbol)
        for filter_item in symbol_info.get("filters", []):
            if filter_item["filterType"] == "LOT_SIZE":
                min_qty = float(filter_item["minQty"])
                return min_qty
        raise ValueError(f"无法获取 {symbol} 的 minQty")
    
    def get_max_quantity(self, symbol: str) -> float:
        """获取最大交易数量"""
        symbol_info = self.get_symbol_info(symbol)
        for filter_item in symbol_info.get("filters", []):
            if filter_item["filterType"] == "LOT_SIZE":
                max_qty = float(filter_item["maxQty"])
                return max_qty
        raise ValueError(f"无法获取 {symbol} 的 maxQty")
    
    def check_leverage(self, symbol: str) -> Dict:
        """
        检查当前杠杆设置（只读）
        
        ⚠️ 注意：当前为只读阶段，不实际设置杠杆
        """
        try:
            # 获取当前持仓信息（包含杠杆）
            positions = self.client.futures_position_information()
            for pos in positions:
                if pos["symbol"] == symbol:
                    leverage = int(pos.get("leverage", 0))
                    return {
                        "symbol": symbol,
                        "current_leverage": leverage,
                        "status": "已设置" if leverage > 0 else "未设置",
                        "warning": "[WARN] 杠杆未显式设置，可能使用上次值，极其危险！" if leverage == 0 else None
                    }
            return {
                "symbol": symbol,
                "current_leverage": 0,
                "status": "未设置",
                "warning": "⚠️ 杠杆未显式设置，可能使用上次值，极其危险！"
            }
        except Exception as e:
            return {
                "symbol": symbol,
                "error": str(e),
                "warning": "无法获取杠杆信息"
            }
    
    def check_margin_type(self, symbol: str) -> Dict:
        """
        检查当前保证金模式（只读）
        
        ⚠️ 注意：当前为只读阶段，不实际设置保证金模式
        """
        try:
            positions = self.client.futures_position_information()
            for pos in positions:
                if pos["symbol"] == symbol:
                    margin_type = pos.get("marginType", "UNKNOWN")
                    return {
                        "symbol": symbol,
                        "current_margin_type": margin_type,
                        "status": "已设置" if margin_type != "UNKNOWN" else "未设置",
                        "recommendation": "强烈建议使用 ISOLATED（逐仓）模式" if margin_type != "ISOLATED" else "当前为逐仓模式，安全"
                    }
            return {
                "symbol": symbol,
                "current_margin_type": "UNKNOWN",
                "status": "未设置",
                "recommendation": "强烈建议使用 ISOLATED（逐仓）模式"
            }
        except Exception as e:
            return {
                "symbol": symbol,
                "error": str(e),
                "warning": "无法获取保证金模式信息"
            }
    
    def prepare_for_trading(self, symbol: str, leverage: int = 3, 
                          margin_type: str = "ISOLATED") -> Dict:
        """
        交易前准备检查（只读验证，不实际执行）
        
        ⚠️ 注意：当前为只读阶段，这些设置不会实际执行
        真实交易时需要显式调用：
        - client.futures_change_leverage(symbol=symbol, leverage=leverage)
        - client.futures_change_margin_type(symbol=symbol, marginType=margin_type)
        
        Args:
            symbol: 交易对
            leverage: 建议杠杆倍数（默认3倍）
            margin_type: 建议保证金模式（默认ISOLATED逐仓）
        
        Returns:
            准备检查结果
        """
        result = {
            "symbol": symbol,
            "checks": {}
        }
        
        # 检查杠杆
        leverage_info = self.check_leverage(symbol)
        result["checks"]["leverage"] = leverage_info
        result["checks"]["leverage"]["recommended"] = leverage
        result["checks"]["leverage"]["action_required"] = (
            leverage_info.get("current_leverage", 0) != leverage
        )
        
        # 检查保证金模式
        margin_info = self.check_margin_type(symbol)
        result["checks"]["margin_type"] = margin_info
        result["checks"]["margin_type"]["recommended"] = margin_type
        result["checks"]["margin_type"]["action_required"] = (
            margin_info.get("current_margin_type", "") != margin_type
        )
        
        # 获取精度信息
        try:
            step_size = self.get_step_size(symbol)
            tick_size = self.get_tick_size(symbol)
            min_qty = self.get_min_quantity(symbol)
            max_qty = self.get_max_quantity(symbol)
            
            result["checks"]["precision"] = {
                "step_size": step_size,
                "tick_size": tick_size,
                "min_quantity": min_qty,
                "max_quantity": max_qty,
                "status": "已获取精度信息"
            }
        except Exception as e:
            result["checks"]["precision"] = {
                "error": str(e),
                "status": "获取精度信息失败"
            }
        
        # 总结
        all_ready = (
            not result["checks"]["leverage"].get("action_required", True) and
            not result["checks"]["margin_type"].get("action_required", True) and
            "error" not in result["checks"].get("precision", {})
        )
        
        result["ready_for_trading"] = all_ready
        result["warning"] = "⚠️ 当前为只读阶段，设置不会实际执行" if all_ready else "需要完成准备步骤"
        
        return result


# 便捷函数
def get_preparator() -> TradePreparator:
    """获取交易准备器实例"""
    return TradePreparator()


def validate_order_params(symbol: str, quantity: float, price: Optional[float] = None) -> Dict:
    """
    验证订单参数的便捷函数
    
    Returns:
        {
            "valid": bool,
            "quantity": float,  # 修正后的数量
            "price": float,     # 修正后的价格（如果提供）
            "messages": List[str]
        }
    """
    prep = get_preparator()
    messages = []
    valid = True
    
    # 验证数量
    qty_valid, qty_msg, corrected_qty = prep.validate_quantity(symbol, quantity)
    if not qty_valid:
        valid = False
        messages.append(qty_msg)
    quantity = corrected_qty
    
    # 验证价格（如果提供）
    corrected_price = price
    if price is not None:
        price_valid, price_msg, corrected_price = prep.validate_price(symbol, price)
        if not price_valid:
            valid = False
            messages.append(price_msg)
    
    return {
        "valid": valid,
        "quantity": quantity,
        "price": corrected_price,
        "messages": messages
    }
