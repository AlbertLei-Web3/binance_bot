# Binance Bot - 币安合约交易机器人

币安 USDT-M 合约 Python 交易机器人，核心策略为山寨币做空。当前为虚拟交易模式，不会发送真实订单。

## 核心功能

- **山寨币做空策略** — 两阶段模型：自动标的发现 → 多重信号择时入场
- **标的自动筛选** — 从币安合约涨幅榜扫描连续拉涨标的（AND 逻辑）
- **信号引擎** — 7 个做空信号检测器 + 加权评分系统
- **风控状态机** — 动态补仓、止盈止损、资金费率/极端行情/超时保护
- **虚拟交易系统** — 完整模拟交易，含 PnL 分析
- **技术指标库** — EMA、RSI、MACD、布林带、ATR、RSI 背离、量价分析

## 项目结构

```
binance_bot/
├── config/config.yaml              # 策略与筛选参数配置
├── core/                           # 核心模块
│   ├── client.py                   # 币安 API 客户端
│   ├── market.py                   # 行情数据
│   ├── account.py                  # 账户查询
│   ├── virtual_trade.py            # 虚拟交易引擎
│   ├── risk.py                     # 风控状态机
│   ├── pnl.py                      # PnL 分析
│   └── trade_prep.py               # 交易精度验证
├── strategies/                     # 策略模块
│   ├── base_strategy.py            # 策略基类
│   ├── altcoin_short_strategy.py   # 山寨币做空策略
│   ├── screener.py                 # 标的自动筛选
│   └── signal_engine.py            # 信号引擎（7 个检测器）
├── utils/                          # 工具模块
│   ├── indicators.py               # 技术指标库
│   └── logger.py                   # 日志
├── scripts/
│   └── run_altcoin_short.py        # 策略启动入口
├── tests/                          # 单元测试
├── docs/                           # 策略文档
│   ├── RISK_MANAGEMENT.md          # 风控设计文档
│   └── SHORT_STRATEGY_FOR_ALTCOINS.md  # 做空策略设计文档
├── data/                           # 运行时数据（watchlist 等）
├── .env                            # API 密钥（不入库）
└── requirements.txt
```

## 快速开始

1. 安装依赖：

```bash
pip install -r requirements.txt
```

2. 配置 API 密钥（`.env`）：

```
BINANCE_API_KEY=your_api_key
BINANCE_API_SECRET=your_api_secret
```

3. 运行策略：

```bash
python scripts/run_altcoin_short.py
```

> 当前为虚拟交易模式，不会发送真实订单。

## 策略工作流

```
涨幅榜扫描 → 连续拉涨检测(AND) → 基础过滤 → 信号评估 → 开仓 → 风控管理
```

### 阶段一：标的发现（Screener）

从币安合约涨幅榜自动筛选，三个条件同时满足（AND 逻辑）：

- 连续 ≥ 3 天日线收阳
- 每日涨幅均 ≥ 12%
- 累计涨幅 ≥ 100%

附加过滤：24h 成交额 ≥ 2000 万 USDT、买卖价差 ≤ 0.5%、资金费率 ≤ 0.15%

### 阶段二：信号引擎（7 个做空信号）

| 信号 | 权重 | 说明 |
|------|------|------|
| RSI 超买 + 顶背离 | 1.5 | RSI ≥ 70，有背离强度 0.9 |
| MACD 死叉 | 1.3 | 柱状图转负 |
| 量价背离 | 1.3 | 上涨缩量或下跌放量 |
| 价格回落 | 1.2 | 从高点回落 5%+ |
| 无法创新高 | 1.1 | 连续 4+ 根 K 线未破前高 |
| 跌破 EMA | 1.0 | 跌破 EMA20/EMA50 |
| 大阴线/长上影 | 1.0 | 实体或上影占比超阈值 |

入场条件：≥ 3 个信号触发 且 加权评分 ≥ 0.6

### 风控状态机

- 4 级仓位管理（头仓 → 最多 3 次补仓），补仓阈值根据 ATR 动态调整
- 止盈止损：每级仓位独立止盈线，统一止损线
- 保护机制：资金费率过高自动平仓、极端行情保护、持仓超时（48h）自动平仓

## 配置说明

核心参数在 `config/config.yaml`：

```yaml
altcoin_short:
  total_capital: 100000        # 总资金 (USDT)
  max_per_symbol: 0.10         # 单币种最大占比
  leverage: 5                  # 杠杆倍数
  max_positions: 5             # 最大同时持仓数
  min_signals: 3               # 最少信号数
  min_signal_score: 0.6        # 最低信号评分

screener:
  pump_detect_days: 3          # 连续拉涨最少天数
  daily_min_gain: 0.12         # 每日最低涨幅
  total_min_gain: 1.00         # 累计最低涨幅
```

## 技术指标

EMA（20/50）、RSI（14）、MACD（12/26/9）、布林带（20, 2σ）、ATR（14）、RSI 顶背离检测、量价分析

## 免责声明

本项目仅供学习研究，当前为虚拟交易模式。加密货币交易存在高风险，使用者需自行承担所有风险。
