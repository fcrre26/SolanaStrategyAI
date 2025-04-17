# Solana交易分析工具

这是一个用于分析Solana交易的工具，可以监控钱包交易、分析交易策略，并生成详细报告。

## 功能特点

- 实时监控Solana钱包交易活动
- 自动分析交易模式和策略
- 生成详细的交易分析报告
- 提供交互式数字菜单界面
- 支持多种数据存储格式（SQLite、JSON、CSV）
- 使用火山引擎API进行高级策略分析

## 安装

### 前置要求

- Python 3.9+
- Solana-py库
- Aiohttp库
- 火山引擎API密钥（用于分析功能）

### 步骤

1. 克隆仓库：

```bash
git clone https://github.com/fcrre26/SolanaStrategyAI.git
cd SolanaStrategyAI
```

2. 安装依赖：

```bash
pip install -r requirements.txt
```

## 使用方法

### 启动程序

使用以下命令启动程序：

```bash
python -m solana-analyzer.src.main WALLET_ADDRESS
```

其中`WALLET_ADDRESS`是您要监控的Solana钱包地址。

### 交互式菜单

启动后，程序会显示一个交互式数字菜单，提供以下选项：

1. 查看监控状态
2. 查看交易历史
3. 查看交易对分析
4. 查看池子状态
5. 查看市场数据
6. 生成分析报告
7. 实时监控交易

### 实时监控

选择菜单选项"7. 实时监控交易"可以启动实时监控功能：

- 使用GRPC流式连接实时监听钱包交易
- 交易发生即刻获取并存储数据
- 自动分析交易模式和策略
- 可检测交易对和交易模式

### 分析报告

选择菜单选项"6. 生成分析报告"可以生成详细的分析报告：

- 分析交易模式和策略
- 生成交易对分析
- 提供池子状态分析
- 生成市场数据分析

## 数据结构

### 存储结构

- `data/transactions/`: 存储交易数据
  - 按日期组织，每个交易存储为单独的记录
- `data/pools/`: 存储池子状态数据
  - 记录池子的价格、储备量等信息
- `data/market/`: 存储市场数据
  - 记录价格、交易量、TVL等信息
- `reports/`: 存储分析报告
  - 按日期组织，每个报告包含完整的分析结果

### 分析结果格式

分析结果遵循以下格式：

```json
{
  "target_selection": {
    "liquidity_criteria": {
      "min_liquidity": "最小流动性要求",
      "liquidity_stability": "流动性稳定性评估"
    },
    "volume_criteria": {
      "min_24h_volume": "24小时最小交易量",
      "volume_trend": "交易量趋势分析"
    },
    "price_criteria": {
      "price_stability": "价格稳定性评估",
      "price_trend": "价格趋势分析"
    }
  },
  "buy_strategy": {
    "trigger_conditions": {
      "price_drop": "价格下跌触发条件",
      "liquidity_increase": "流动性增加触发条件",
      "volume_spike": "交易量突增触发条件"
    },
    "buy_parameters": {
      "position_size": "仓位大小建议",
      "entry_price": "入场价格建议",
      "slippage_tolerance": "滑点容忍度"
    }
  },
  "sell_strategy": {
    "take_profit": {
      "target_price": "目标价格",
      "profit_percentage": "利润百分比"
    },
    "stop_loss": {
      "stop_price": "止损价格",
      "loss_percentage": "损失百分比"
    }
  },
  "position_management": {
    "scaling": "加减仓策略",
    "rebalancing": "再平衡策略"
  },
  "risk_control": {
    "max_position_size": "最大仓位建议",
    "max_daily_loss": "每日最大亏损限制",
    "correlation_management": "相关性管理策略"
  }
}
```

## 工作原理

1. **数据收集**：使用Solana RPC API收集指定钱包地址的交易数据
2. **数据解析**：解析交易数据，提取交易类型、DEX信息、代币转账等关键信息
3. **数据存储**：将解析后的数据存储到本地数据库中
4. **实时监控**：通过GRPC流式连接实时监控钱包交易，即时获取和存储交易数据
5. **API分析**：将存储的数据发送到火山引擎API进行分析，获取交易策略建议
6. **结果存储**：将分析结果存储到本地，方便后续查看和导出

## 架构设计

本项目采用模块化设计，主要组件如下：

- `src/monitor/`: 负责监控钱包交易
- `src/analysis/`: 负责分析交易数据和生成报告
- `src/storage/`: 负责数据存储和管理
- `src/main.py`: 主程序入口，提供用户界面

数据流程如下：

```
Solana区块链 -> 监控模块 -> 数据存储 -> API分析 -> 报告生成
```

## 许可证

MIT许可证 