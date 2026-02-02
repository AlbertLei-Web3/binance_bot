# Binance Bot - 币安合约交易机器人

一个用于币安 USDT-M 合约的 Python 交易机器人框架，支持虚拟交易、策略回测和实盘交易。

## ⚠️ 重要提示

**当前阶段为只读模式**，所有交易功能均为虚拟交易，不会向币安发送真实订单。

## ✨ 核心特性

- ✅ **只读 API 接入** - 安全获取行情和账户信息
- ✅ **虚拟交易系统** - 完整的模拟交易功能
- ✅ **策略框架** - 易于扩展的策略开发框架
- ✅ **PnL 分析** - 详细的盈亏分析和性能指标
- ✅ **交易安全准备** - 杠杆、保证金模式、精度验证
- ✅ **策略回测** - 基于历史数据的策略回测
- ✅ **自动化执行** - 支持策略自动运行

## 📁 项目结构

```
binance_bot/
├── config/              # 配置文件
│   └── config.yaml
├── core/                # 核心功能模块
│   ├── client.py        # API 客户端
│   ├── market.py        # 行情数据
│   ├── account.py       # 账户查询
│   ├── virtual_trade.py # 虚拟交易
│   ├── pnl.py          # PnL 分析
│   ├── trade_prep.py   # 交易准备
│   └── risk.py         # 风控模块
├── strategies/          # 交易策略
│   ├── base_strategy.py    # 策略基类
│   └── example_strategy.py # 示例策略
├── utils/               # 工具函数
│   ├── indicators.py   # 技术指标
│   └── logger.py       # 日志工具
├── scripts/             # 运行脚本
│   ├── run_strategy.py # 运行策略
│   └── backtest.py     # 回测脚本
├── tests/               # 测试脚本
│   ├── test_readonly.py
│   ├── test_virtual_trade.py
│   ├── test_trade_prep.py
│   └── test_risk.py
├── data/                # 数据存储
│   └── logs/            # 日志文件
├── .env                 # 环境变量（需自行创建）
├── requirements.txt     # 依赖包
└── README.md            # 本文件
```

## 🚀 快速开始

### 1. 安装依赖

```bash
cd binance_bot
pip install -r requirements.txt
```

### 2. 配置环境变量

创建 `.env` 文件：

```
BINANCE_API_KEY=YOUR_API_KEY
BINANCE_API_SECRET=YOUR_API_SECRET
```

### 3. 运行测试

```bash
# 测试只读功能
python tests/test_readonly.py

# 测试虚拟交易
python tests/test_virtual_trade.py

# 测试交易准备
python tests/test_trade_prep.py
```

### 4. 运行策略

```bash
# 运行示例策略（虚拟交易）
python scripts/run_strategy.py

# 回测策略
python scripts/backtest.py
```

## 📚 核心功能

### 只读 API 接入
- ✅ 获取合约行情（标记价格、K线）
- ✅ 获取账户余额
- ✅ 获取持仓信息

### 虚拟交易系统
- ✅ 虚拟下单和持仓管理
- ✅ 自动盈亏计算
- ✅ 订单历史记录

### PnL 分析
- ✅ 盈亏分析
- ✅ 性能指标计算
- ✅ 历史回放

### 风控模块
- ✅ 状态机管理（头仓+补仓逻辑）
- ✅ 止损规则（基于P0，补满3次仓后激活）
- ✅ 止盈规则（基于任意入场价触发）
- ✅ 数值状态转移表生成
- ✅ 多持仓风控监控

### 交易安全准备
- ✅ 杠杆检查（防止使用上次值）
- ✅ 保证金模式检查（建议逐仓）
- ✅ 精度验证（避免 LOT_SIZE 错误）

## 🛡️ 风控模块使用

### 风控规则说明

本系统实现了基于状态机的风控管理：

#### 仓位管理
- **初始资金**: C（运行时从交易所获取）
- **杠杆**: L（建议5x）
- **头仓**: A0 = C/8
- **补仓**: 每次 A = C/16，最多补仓3次
- **累计仓位**: A_total(n) = C/8 + n·C/16，n ∈ {0,1,2,3}

#### 止损规则
- **触发条件**: 补满3次仓（state=3）后激活
- **止损回报率**: -150% 杠杆回报率
- **做多止损**: P_stop = P0 × (1 - 1.5/L) = P0 × 0.7
- **做空止损**: P_stop = P0 × (1 + 1.5/L) = P0 × 1.3
- **触发动作**: 立即全平并终止状态机

#### 止盈规则
- **做多止盈**: (current_price / entry_price - 1) ≥ 2.0（标的上涨200%）
- **做空止盈**: (1 - current_price / entry_price) ≥ 0.4（标的下跌40%）
- **检查范围**: 任意一笔入场价触发即全平
- **触发动作**: 立即全平并终止状态机

### 风控模块使用示例

```python
from core.risk import RiskManager, PositionSide, generate_state_transition_table

# 1. 创建风控管理器
risk_manager = RiskManager()

# 2. 创建做多持仓
position = risk_manager.create_position(
    symbol="BTCUSDT",
    side=PositionSide.LONG,
    initial_capital=10000,  # 初始资金
    leverage=5,              # 杠杆
    reference_price=50000,   # 参考价格P0
    entry_price=50000        # 头仓入场价
)

# 3. 补仓（当价格达到补仓条件时）
result = position.add_position(48000)
print(f"补仓成功: 累计仓位 ${result['total_position_size']:.2f}")

# 4. 检查风控事件
events = risk_manager.check_all_positions({
    "BTCUSDT": 49000  # 当前价格
})

for event in events:
    if event['type'] == 'STOP_LOSS':
        print(f"触发止损: {event['symbol']} at ${event['current_price']}")
    elif event['type'] == 'TAKE_PROFIT':
        print(f"触发止盈: {event['symbol']} at ${event['current_price']}")

# 5. 生成状态转移表
tables = generate_state_transition_table(
    initial_capital=10000,
    leverage=5,
    reference_price=100
)
```

### 运行风控测试

```bash
# 运行完整的风控测试
python tests/test_risk.py
```

输出包括：
- 做多场景的完整状态转移
- 做空场景的完整状态转移
- 多持仓管理测试
- 详细的数值状态转移表

## 🔧 开发策略

### 创建新策略

1. 继承 `BaseStrategy` 类：

```python
from strategies.base_strategy import BaseStrategy

class MyStrategy(BaseStrategy):
    def on_tick(self, current_price: float, klines: list):
        # 实现你的策略逻辑
        # 返回订单信息或 None
        return {
            "side": "BUY",  # 或 "SELL"
            "quantity": 0.001,
            "price": None  # None 表示市价
        }
```

2. 在 `scripts/run_strategy.py` 中使用你的策略，或创建自定义运行脚本

## ⚠️ 安全注意事项

### 真实交易前必须：

1. **显式设置杠杆**（必须！否则使用上次值，极其危险）
```python
client.futures_change_leverage(symbol="BTCUSDT", leverage=3)
```

2. **设置保证金模式**（强烈建议逐仓）
```python
client.futures_change_margin_type(symbol="BTCUSDT", marginType="ISOLATED")
```

3. **验证精度**（避免 LOT_SIZE 错误）
```python
from core.trade_prep import validate_order_params
result = validate_order_params(symbol, quantity, price)
```

## 📊 技术指标

项目内置常用技术指标工具（`utils/indicators.py`）：

- **SMA** - 简单移动平均
- **EMA** - 指数移动平均
- **RSI** - 相对强弱指标
- **MACD** - 指数平滑异同移动平均线

使用示例：

```python
from utils.indicators import calculate_sma, calculate_rsi
from utils.indicators import get_closes_from_klines

klines = get_klines("BTCUSDT", interval="1h", limit=100)
closes = get_closes_from_klines(klines)

sma_20 = calculate_sma(closes, 20)
rsi = calculate_rsi(closes, 14)
```

## 📝 日志记录

策略执行器自动记录日志到 `data/logs/` 目录：

- 策略执行信息
- 订单执行记录
- 错误信息
- 账户状态
- 统计信息

日志文件命名格式：`{策略名称}_{日期}.log`

## 🔍 故障排除

### 常见问题

1. **精度验证错误**
   - 使用 `validate_order_params()` 验证订单参数
   - 或设置 `validate_precision=False`（仅虚拟交易）

2. **API 连接失败**
   - 检查网络连接
   - 验证 API Key 和 Secret
   - 查看日志文件

3. **策略执行器无法启动**
   - 检查策略代码
   - 查看日志文件
   - 验证交易对名称

## 📝 许可证

本项目仅供学习和研究使用。使用本代码进行真实交易的风险由使用者自行承担。

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📚 相关文档

- [Binance Futures API 文档](https://binance-docs.github.io/apidocs/futures/cn/)
- [python-binance 文档](https://python-binance.readthedocs.io/)
