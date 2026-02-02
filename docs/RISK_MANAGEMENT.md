# Risk Management Module / 风控模块

**Created: 2026-02-02**

## 概述 / Overview

本风控模块实现了基于状态机的交易风险管理系统，包括仓位管理、止损、止盈等功能。

## 核心规则 / Core Rules

### 1. 仓位管理 / Position Management

#### 参数定义
- **C**: 初始资金（Initial Capital）
- **L**: 杠杆倍数（Leverage）
- **P0**: 初始参考价格（Reference Price）

#### 仓位规则
- **头仓**: A0 = C/8 (12.5% 初始资金)
- **每次补仓**: A = C/16 (6.25% 初始资金)
- **最多补仓次数**: 3次
- **累计仓位公式**: A_total(n) = C/8 + n·C/16，其中 n ∈ {0,1,2,3}

| 状态 | 补仓次数 | 累计仓位金额 | 占初始资金比例 |
|------|---------|-------------|--------------|
| n=0  | 头仓    | C/8         | 12.5%        |
| n=1  | 1次补仓 | 3C/16       | 18.75%       |
| n=2  | 2次补仓 | C/4         | 25%          |
| n=3  | 3次补仓 | 5C/16       | 31.25%       |

### 2. 止损规则 / Stop Loss Rule

#### 激活条件
- **必须补满3次仓**（state=3）才激活止损
- 在 state < 3 时，止损不生效

#### 止损价格计算
- **止损回报率**: -150% 杠杆回报率
- **做多止损价**: P_stop = P0 × (1 - 1.5/L)
  - 例: L=5时，P_stop = P0 × 0.7
- **做空止损价**: P_stop = P0 × (1 + 1.5/L)
  - 例: L=5时，P_stop = P0 × 1.3

#### 触发机制
- 当前价格达到止损价时立即触发
- **做多**: current_price ≤ P_stop
- **做空**: current_price ≥ P_stop

#### 触发动作
- 立即全平仓位
- 终止状态机

### 3. 止盈规则 / Take Profit Rule

#### 止盈条件
- **做多**: (current_price / entry_price - 1) ≥ 2.0
  - 标的上涨 200%
  - L=5 时杠杆回报率 = 1000%
  
- **做空**: (1 - current_price / entry_price) ≥ 0.4
  - 标的下跌 40%
  - L=5 时杠杆回报率 = 200%

#### 检查范围
- 检查**所有入场价**（包括头仓和每次补仓）
- **任意一笔入场价**触发条件即全平

#### 触发动作
- 立即全平仓位
- 终止状态机

### 4. 状态转移 / State Transition

```
[开头仓] → state=0
    ↓ (价格触发补仓阈值)
[补仓1] → state=1
    ↓ (价格触发补仓阈值)
[补仓2] → state=2
    ↓ (价格触发补仓阈值)
[补仓3] → state=3 (止损激活)
    ↓ (价格触发止盈/止损)
[全平仓] → 状态机终止
```

## API 使用 / API Usage

### 1. 创建风控管理器

```python
from core.risk import RiskManager, PositionSide

# 创建管理器
rm = RiskManager()
```

### 2. 创建持仓

```python
# 做多持仓
long_position = rm.create_position(
    symbol="BTCUSDT",
    side=PositionSide.LONG,
    initial_capital=10000,    # $10,000
    leverage=5,                # 5x 杠杆
    reference_price=50000,     # 参考价格 P0
    entry_price=50000          # 头仓入场价
)

# 做空持仓
short_position = rm.create_position(
    symbol="ETHUSDT",
    side=PositionSide.SHORT,
    initial_capital=10000,
    leverage=5,
    reference_price=3000,
    entry_price=3000
)
```

### 3. 补仓

```python
# 当价格触发补仓条件时
result = position.add_position(48000)

if result['success']:
    print(f"补仓成功！")
    print(f"  状态: state={result['state']}")
    print(f"  补仓金额: ${result['add_size']}")
    print(f"  累计仓位: ${result['total_position_size']}")
```

### 4. 检查风控事件

```python
# 检查所有持仓的风控状态
events = rm.check_all_positions({
    "BTCUSDT": 49000,  # 当前价格
    "ETHUSDT": 3100
})

for event in events:
    if event['type'] == 'STOP_LOSS':
        print(f"止损触发: {event['symbol']}")
        # 执行全平操作
        
    elif event['type'] == 'TAKE_PROFIT':
        print(f"止盈触发: {event['symbol']}")
        print(f"触发入场价: ${event['triggered_entry_price']}")
        # 执行全平操作
```

### 5. 计算盈亏

```python
# 计算当前盈亏
pnl = position.calculate_pnl(current_price)

print(f"未实现盈亏: ${pnl['unrealized_pnl']:,.2f}")
print(f"回报率: {pnl['return_rate']:.2f}%")
print(f"平均成本: ${pnl['avg_price']:,.2f}")
```

### 6. 获取持仓信息

```python
# 转换为字典格式
info = position.to_dict()

print(f"交易对: {info['symbol']}")
print(f"方向: {info['side']}")
print(f"状态: state={info['state']}, status={info['status']}")
print(f"止损价: ${info['stop_loss_price']}")
print(f"入场价列表: {info['entry_prices']}")
print(f"平均入场价: ${info['avg_entry_price']}")
```

## 数值示例 / Numerical Examples

### 做多场景 (LONG)

**初始参数**:
- 初始资金: $10,000
- 杠杆: 5x
- 参考价格: $50,000
- 止损价: $35,000 (50000 × 0.7)

**状态转移**:

| 状态 | 价格 | 仓位金额 | 数量(BTC) | 平均成本 |
|------|------|----------|-----------|---------|
| 0    | $50,000 | $1,250  | 0.125    | $50,000 |
| 1    | $48,000 | $1,875  | 0.190    | $49,315 |
| 2    | $46,000 | $2,500  | 0.258    | $48,442 |
| 3    | $44,000 | $3,125  | 0.329    | $47,483 |

**场景测试**:
- 价格 $35,000: 触发止损（state=3）→ 亏损 $-4,108 (-131%)
- 价格 $47,000: 无事件触发 → 亏损 $-159 (-5%)
- 价格 $150,000: 触发止盈（头仓 $50k×3）→ 盈利 $+33,734 (+1,079%)

### 做空场景 (SHORT)

**初始参数**:
- 初始资金: $10,000
- 杠杆: 5x
- 参考价格: $3,000
- 止损价: $3,900 (3000 × 1.3)

**状态转移**:

| 状态 | 价格 | 仓位金额 | 数量(ETH) | 平均成本 |
|------|------|----------|-----------|---------|
| 0    | $3,000 | $1,250  | 2.083    | $3,000 |
| 1    | $3,200 | $1,875  | 3.060    | $3,063 |
| 2    | $3,400 | $2,500  | 3.979    | $3,141 |
| 3    | $3,600 | $3,125  | 4.847    | $3,223 |

**场景测试**:
- 价格 $3,900: 触发止损（state=3）→ 亏损 $-3,278 (-105%)
- 价格 $3,100: 无事件触发 → 盈利 $+599 (+19%)
- 价格 $1,800: 触发止盈（头仓 $3k×0.6）→ 盈利 $+6,900 (+221%)

## 测试与演示 / Testing & Demo

### 运行完整测试

```bash
# 运行风控模块测试
python tests/test_risk.py
```

测试内容包括：
- 做多基本逻辑测试
- 做空基本逻辑测试
- 风控管理器测试
- 状态转移表生成

### 运行演示脚本

```bash
# 运行交互式演示
python scripts/risk_demo.py
```

演示内容包括：
- 做多持仓完整流程
- 做空持仓完整流程
- 详细的数值状态转移表

## 注意事项 / Important Notes

### ⚠️ 安全警告

1. **止损仅在 state=3 时生效**
   - 补仓前两次时止损未激活
   - 需要额外的风控措施保护早期仓位

2. **止盈基于任意入场价**
   - 早期入场价更容易触发止盈
   - 补仓会提高平均成本，但不影响早期入场价的止盈判断

3. **止损价基于 P0**
   - 止损价是固定的，不随补仓变化
   - 补仓会降低平均成本，但止损价不变

4. **状态机终止后不可恢复**
   - 触发止盈/止损后状态机终止
   - 需要重新创建持仓才能继续交易

### 💡 最佳实践

1. **设置合理的补仓阈值**
   - 补仓间隔不宜过小（避免频繁补仓）
   - 补仓间隔不宜过大（避免错过机会）

2. **监控所有风控事件**
   - 定期调用 `check_all_positions()`
   - 及时响应止盈/止损信号

3. **记录所有状态转移**
   - 保存每次补仓的详细信息
   - 便于事后分析和优化策略

4. **测试不同杠杆倍数**
   - 杠杆越高，风险越大
   - 建议从低杠杆（3-5x）开始

## 代码结构 / Code Structure

```
core/risk.py
├── PositionSide (Enum)        # 持仓方向
├── StateMachineStatus (Enum)  # 状态机状态
├── PositionStateMachine       # 持仓状态机
│   ├── __init__()            # 初始化
│   ├── add_position()        # 补仓
│   ├── check_stop_loss()     # 检查止损
│   ├── check_take_profit()   # 检查止盈
│   └── calculate_pnl()       # 计算盈亏
├── RiskManager                # 风控管理器
│   ├── create_position()     # 创建持仓
│   ├── check_all_positions() # 检查所有持仓
│   └── close_position()      # 关闭持仓
└── generate_state_transition_table()  # 生成状态转移表
```

## 未来扩展 / Future Extensions

- [ ] 动态调整止损价（基于波动率）
- [ ] 部分止盈功能
- [ ] 移动止损（Trailing Stop）
- [ ] 多级止盈目标
- [ ] 风险敞口监控
- [ ] 回撤控制
- [ ] 仓位热力图可视化

## 许可证 / License

本模块是 Binance Bot 项目的一部分，遵循项目主许可证。
