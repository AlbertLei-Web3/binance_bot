"""
交易准备测试脚本
验证杠杆、保证金模式、精度检查功能
"""
import sys
import os

# Add parent directory to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.trade_prep import TradePreparator, validate_order_params


def test_precision_check():
    """测试精度检查"""
    print("=" * 60)
    print("测试1: 精度检查")
    print("=" * 60)
    
    prep = TradePreparator()
    symbol = "BTCUSDT"
    
    try:
        # 获取精度信息
        step_size = prep.get_step_size(symbol)
        tick_size = prep.get_tick_size(symbol)
        min_qty = prep.get_min_quantity(symbol)
        max_qty = prep.get_max_quantity(symbol)
        
        print(f"\n{symbol} 精度信息:")
        print(f"  数量精度 (stepSize): {step_size}")
        print(f"  价格精度 (tickSize): {tick_size}")
        print(f"  最小数量: {min_qty}")
        print(f"  最大数量: {max_qty}")
        
        # 测试数量验证
        print("\n测试数量验证:")
        test_quantities = [0.001, 0.0015, 0.001234, 0.01]
        for qty in test_quantities:
            is_valid, msg, corrected = prep.validate_quantity(symbol, qty)
            status = "[OK]" if is_valid else "[WARN]"
            print(f"  {status} {qty} -> {msg}")
            if not is_valid:
                print(f"     修正后: {corrected}")
        
        # 测试价格验证
        print("\n测试价格验证:")
        test_prices = [50000.0, 50000.123, 50000.5, 50001.234]
        for price in test_prices:
            is_valid, msg, corrected = prep.validate_price(symbol, price)
            status = "[OK]" if is_valid else "[WARN]"
            print(f"  {status} ${price:,.2f} -> {msg}")
            if not is_valid:
                print(f"     修正后: ${corrected:,.2f}")
        
    except Exception as e:
        print(f"❌ 错误: {e}")
        import traceback
        traceback.print_exc()


def test_leverage_check():
    """测试杠杆检查"""
    print("\n" + "=" * 60)
    print("测试2: 杠杆检查")
    print("=" * 60)
    
    prep = TradePreparator()
    symbol = "BTCUSDT"
    
    try:
        leverage_info = prep.check_leverage(symbol)
        print(f"\n{symbol} 杠杆信息:")
        print(f"  当前杠杆: {leverage_info.get('current_leverage', 'N/A')}")
        print(f"  状态: {leverage_info.get('status', 'N/A')}")
        if leverage_info.get('warning'):
            print(f"  [WARN] {leverage_info['warning']}")
    except Exception as e:
        print(f"[ERROR] 错误: {e}")


def test_margin_type_check():
    """测试保证金模式检查"""
    print("\n" + "=" * 60)
    print("测试3: 保证金模式检查")
    print("=" * 60)
    
    prep = TradePreparator()
    symbol = "BTCUSDT"
    
    try:
        margin_info = prep.check_margin_type(symbol)
        print(f"\n{symbol} 保证金模式:")
        print(f"  当前模式: {margin_info.get('current_margin_type', 'N/A')}")
        print(f"  状态: {margin_info.get('status', 'N/A')}")
        if margin_info.get('recommendation'):
            print(f"  建议: {margin_info['recommendation']}")
    except Exception as e:
        print(f"[ERROR] 错误: {e}")


def test_prepare_for_trading():
    """测试交易前准备"""
    print("\n" + "=" * 60)
    print("测试4: 交易前准备检查")
    print("=" * 60)
    
    prep = TradePreparator()
    symbol = "BTCUSDT"
    
    try:
        result = prep.prepare_for_trading(symbol, leverage=3, margin_type="ISOLATED")
        
        print(f"\n{symbol} 交易准备检查:")
        print(f"  准备状态: {'[READY] 就绪' if result['ready_for_trading'] else '[WARN] 需要设置'}")
        
        # 杠杆检查
        leverage_check = result["checks"]["leverage"]
        print(f"\n  杠杆:")
        print(f"    当前: {leverage_check.get('current_leverage', 'N/A')}")
        print(f"    建议: {leverage_check.get('recommended', 'N/A')}")
        print(f"    需要操作: {'是' if leverage_check.get('action_required') else '否'}")
        if leverage_check.get('warning'):
            print(f"    [WARN] {leverage_check['warning']}")
        
        # 保证金模式检查
        margin_check = result["checks"]["margin_type"]
        print(f"\n  保证金模式:")
        print(f"    当前: {margin_check.get('current_margin_type', 'N/A')}")
        print(f"    建议: {margin_check.get('recommended', 'N/A')}")
        print(f"    需要操作: {'是' if margin_check.get('action_required') else '否'}")
        if margin_check.get('recommendation'):
            print(f"    [TIP] {margin_check['recommendation']}")
        
        # 精度信息
        precision_check = result["checks"]["precision"]
        print(f"\n  精度信息:")
        if "error" not in precision_check:
            print(f"    数量精度: {precision_check.get('step_size', 'N/A')}")
            print(f"    价格精度: {precision_check.get('tick_size', 'N/A')}")
            print(f"    最小数量: {precision_check.get('min_quantity', 'N/A')}")
            print(f"    最大数量: {precision_check.get('max_quantity', 'N/A')}")
        else:
            print(f"    [ERROR] {precision_check.get('error', 'N/A')}")
        
        if result.get('warning'):
            print(f"\n  [WARN] {result['warning']}")
        
    except Exception as e:
        print(f"[ERROR] 错误: {e}")
        import traceback
        traceback.print_exc()


def test_validate_order_params():
    """测试订单参数验证便捷函数"""
    print("\n" + "=" * 60)
    print("测试5: 订单参数验证便捷函数")
    print("=" * 60)
    
    symbol = "BTCUSDT"
    
    # 测试用例
    test_cases = [
        {"quantity": 0.001, "price": 50000.0},
        {"quantity": 0.0015, "price": 50000.123},  # 两个都有精度问题
        {"quantity": 0.01, "price": None},  # 使用市价
    ]
    
    for i, params in enumerate(test_cases, 1):
        print(f"\n测试用例 {i}:")
        print(f"  数量: {params['quantity']}")
        print(f"  价格: {params.get('price', '市价')}")
        
        try:
            result = validate_order_params(symbol, params["quantity"], params.get("price"))
            if result["valid"]:
                print(f"  [OK] 验证通过")
            else:
                print(f"  [WARN] 验证失败:")
                for msg in result["messages"]:
                    print(f"    - {msg}")
            print(f"  修正后数量: {result['quantity']}")
            if result["price"] is not None:
                print(f"  修正后价格: ${result['price']:,.2f}")
        except Exception as e:
            print(f"  [ERROR] 错误: {e}")


if __name__ == "__main__":
    try:
        test_precision_check()
        test_leverage_check()
        test_margin_type_check()
        test_prepare_for_trading()
        test_validate_order_params()
        
        print("\n" + "=" * 60)
        print("[SUCCESS] 所有测试完成！")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n[ERROR] 错误: {e}")
        import traceback
        traceback.print_exc()
