# Binance Bot - 半自动做空信号系统

币安 USDT-M 合约半自动交易系统，程序打分 + 人工决策模式。

## 核心功能

- **霸榜天数追踪** — 监控涨幅榜前 10，追踪连续霸榜天数
- **多周期分析** — 日K/4H/1H/30M/15M 五周期联合分析
- **15分钟暴跌检测** — 跌幅 ≥ 5% 触发，钉钉实时推送
- **综合评分系统** — 霸榜天数 + 技术指标 + 短周期信号
- **Markdown 报告** — 定时生成打分报告，人工决策
- **仓位建议** — 根据评分自动给出仓位建议

## 项目结构

```
binance_bot/
├── config/config.yaml          # 系统配置
├── core/                       # 核心模块
│   ├── client.py               # 币安 API 客户端
│   ├── market.py               # 行情数据
│   └── dingtalk.py             # 钉钉推送
├── scanner/                    # 打分系统
│   ├── pump_tracker.py         # 霸榜天数追踪
│   ├── multi_timeframe.py      # 多周期分析
│   ├── signal_15m.py           # 15分钟暴跌检测
│   ├── scorer.py               # 综合评分器
│   └── reporter.py             # 报告生成器
├── scheduler/                  # 调度模块
│   ├── timer.py                # 定时任务（12:00/21:00）
│   └── monitor.py              # 实时监控
├── scripts/
│   └── run_scanner.py          # 入口脚本
├── utils/                      # 工具模块
│   ├── indicators.py           # 技术指标库
│   └── logger.py               # 日志
├── reports/                    # 报告输出目录
├── data/                       # 运行时数据
├── .env                        # API 密钥
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

3. 配置钉钉推送（`config/config.yaml`）：

```yaml
dingtalk:
  webhook_url: "https://oapi.dingtalk.com/robot/send?access_token=xxx"
  secret: "SECxxx"
  enabled: true
```

4. 运行系统：

```bash
# 立即生成报告
python scripts/run_scanner.py report

# 启动定时报告（12:00 / 21:00）
python scripts/run_scanner.py report --timer

# 启动实时监控（15分钟暴跌推送）
python scripts/run_scanner.py monitor

# 同时运行报告 + 监控
python scripts/run_scanner.py both
```

## 评分体系

### 多周期分析

| 周期 | 作用 | 关键指标 |
|------|------|----------|
| 日K | 标的筛选 | 霸榜天数、累计涨幅 |
| 4H | 趋势确认 | 高位滞涨、顶部形态 |
| 1H | 技术指标 | RSI 超买、布林带上轨 |
| 30M | 短期异动 | 量价背离 |
| **15M** | **入场触发** | **跌幅 ≥ 5%** |

### 综合评分权重

| 维度 | 权重 | 说明 |
|------|------|------|
| 霸榜天数 | 40% | 天数越多，做空信号越强 |
| 技术指标 | 35% | RSI 超买 + 布林带突破 |
| 15分钟信号 | 25% | 暴跌信号触发 |

### 仓位建议

| 评分 | 建议仓位 | 描述 |
|------|----------|------|
| ≥ 1.5 | 10% | 激进 |
| ≥ 1.2 | 8% | 标准 |
| ≥ 0.9 | 5% | 保守 |
| < 0.9 | 观望 | 不操作 |

## 报告示例

```markdown
# 山寨币做空信号报告 - 2026-03-08 21:00

## 📊 霸榜排名

| 排名 | 币种 | 霸榜天数 | 累计涨幅 | RSI | 综合评分 | 建议仓位 |
|:----:|:-----|:--------:|:--------:|:---:|:--------:|:--------:|
| 1 | XXXUSDT | 6 天 | +180% | 82 | **1.72** | 8% |
| 2 | YYYUSDT | 5 天 | +150% | 75 | **1.55** | 8% |

## ⚠️ 15分钟暴跌信号

### 🔴 XXXUSDT
- **跌幅**: -5.2%
- **放量**: 2.1x
- **建议仓位**: 8%
- **建议**: 可考虑建立头仓
```

## 配置说明

核心配置在 `config/config.yaml`：

```yaml
# 扫描器配置
scanner:
  pump_tracker:
    top_n: 10                    # 监控涨幅榜前 N 名
    min_pump_days: 3             # 最少霸榜天数

  signal_15m:
    crash_threshold: 0.05        # 暴跌阈值 5%
    volume_ratio_min: 1.5        # 最小放量倍数

  scoring:
    pump_days_weight: 0.40       # 霸榜天数权重
    technical_weight: 0.35       # 技术指标权重
    signal_15m_weight: 0.25      # 15分钟信号权重

# 报告配置
report:
  schedule_times:                # 定时报告时间
    - "12:00"
    - "21:00"

# 监控配置
monitor:
  enabled: true
  interval_sec: 60               # 监控间隔
```

## 技术指标

RSI（14）、布林带（20, 2σ）、EMA（20/50）、量价分析

## 免责声明

本项目仅供学习研究，为半自动辅助工具，不构成投资建议。加密货币交易存在高风险，使用者需自行承担所有风险。
