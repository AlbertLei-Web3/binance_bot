# Risk Management Quick Reference / 风控模块快速参考

**Created: 2026-02-02**

## 一分钟上手 / Quick Start

```python
from core.risk import RiskManager, PositionSide

# 1. 创建管理器
rm = RiskManager()

# 2. 开仓
pos = rm.create_position(
    symbol="BTCUSDT",
    side=PositionSide.LONG,  # 或 SHORT
    initial_capital=10000,
    leverage=5,
    reference_price=50000,
    entry_price=50000
)

# 3. 补仓
pos.add_position(48000)

# 4. 检查风控
events = rm.check_all_positions({"BTCUSDT": 49000})
```

## 核心公式 / Core Formulas

### 仓位
```
头仓: C/8
补仓: C/16 × n (n=1,2,3)
累计: C/8 + n·C/16
```

### 止损 (state=3时激活)
```
做多: P_stop = P0 × (1 - 1.5/L)
做空: P_stop = P0 × (1 + 1.5/L)
L=5 时: 0.7×P0 和 1.3×P0
```

### 止盈
```
做多: price/entry ≥ 3.0 (涨200%)
做空: 1-price/entry ≥ 0.4 (跌40%)
任意入场价触发即全平
```

## 状态速查 / State Table

| State | 描述 | 仓位 | 止损 |
|-------|------|------|------|
| 0 | 头仓 | C/8 | ❌ 未激活 |
| 1 | 补仓1 | 3C/16 | ❌ 未激活 |
| 2 | 补仓2 | C/4 | ❌ 未激活 |
| 3 | 补仓3 | 5C/16 | ✅ 已激活 |

## 数值示例 (C=$10k, L=5x)

### 做多 @ $50k
| 价格 | 动作 | 盈亏 |
|------|------|------|
| $150k | 止盈 | +1079% |
| $47k | - | -5% |
| $35k | 止损 | -131% |

### 做空 @ $3k
| 价格 | 动作 | 盈亏 |
|------|------|------|
| $1.8k | 止盈 | +221% |
| $3.1k | - | +19% |
| $3.9k | 止损 | -105% |

## 运行测试 / Run Tests

```bash
# 完整测试
python tests/test_risk.py

# 交互演示
python scripts/risk_demo.py
```

## 关键点 / Key Points

⚠️ **止损仅在补满3次仓后激活**  
✅ **止盈检查所有入场价**  
📊 **止损价固定（基于P0）**  
🔄 **状态机终止后不可恢复**

## 详细文档 / Full Docs

参见: `docs/RISK_MANAGEMENT.md`
