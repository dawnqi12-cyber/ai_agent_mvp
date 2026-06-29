# Option Strategy Research Agent
量化投研 AI Agent MVP 骨架项目。项目目标是展示一个面向期权策略研究的 Agent 如何编排多个研究工具，包括行情数据获取、Black-Scholes 定价、Greeks 计算、策略构建、模拟回测、可视化和报告生成。

> 当前阶段只完成项目设计和基础骨架，不实现完整业务功能。

## 项目定位

- **项目类型**: Quant Research AI Agent MVP
- **展示重点**: Agent 工具编排、量化研究流程拆解、模块化工程结构
- **前端规划**: Streamlit
- **数据规划**: 优先使用 `yfinance`，同时必须支持 mock data fallback，保证无网络或数据源异常时仍可演示
- **核心研究对象**: 股票期权、Black-Scholes、Greeks、基础期权组合策略、模拟回测

## 架构概览

```text
app.py
config/
  settings.example.yaml
src/
  agent/
  backtest/
  data/
  pricing/
  strategies/
  utils/
  visualization/
tests/
```

## 模块职责

| 模块 | 职责 |
| --- | --- |
| `app.py` | 未来的 Streamlit 入口。当前仅保留占位入口，用于说明 MVP 的交互方向。 |
| `config/` | 基础配置文件，例如标的、日期范围、无风险利率、mock data 开关、回测参数等。 |
| `src/data/` | 数据获取层。未来优先从 `yfinance` 获取行情和期权链；当数据源不可用时，回退到 mock data。 |
| `src/pricing/` | 期权定价层。未来实现 Black-Scholes 定价、隐含波动率估计、Greeks 计算。 |
| `src/strategies/` | 策略定义层。未来封装 covered call、protective put、straddle、spread 等策略组合。 |
| `src/backtest/` | 模拟回测层。未来负责策略信号、持仓模拟、PnL、收益风险指标等。 |
| `src/agent/` | Agent 编排层。未来把数据、定价、策略、回测、报告生成封装为可调用工具，并组织研究工作流。 |
| `src/visualization/` | 可视化层。未来生成 payoff 图、Greeks 曲线、回测净值曲线和风险指标图。 |
| `src/utils/` | 通用工具层。未来放日志、配置加载、日期处理、校验函数等。 |
| `tests/` | 最小测试与后续单元测试。当前只校验项目结构。 |

## Agent 工具编排设计

未来 Agent 可以按照以下流程组织研究任务：

1. **Data Tool**: 获取标的价格、历史行情、期权链；失败时切换到 mock data。
2. **Pricing Tool**: 对期权合约进行 Black-Scholes 理论定价。
3. **Greeks Tool**: 计算 Delta、Gamma、Theta、Vega、Rho。
4. **Strategy Tool**: 根据用户目标构造策略，例如跨式、价差、备兑、保护性看跌。
5. **Backtest Tool**: 在历史或模拟价格路径上评估策略表现。
6. **Visualization Tool**: 输出 payoff、PnL、净值、风险指标图表。
7. **Report Tool**: 生成面试展示友好的研究摘要，包括假设、方法、结果和风险提示。

## MVP 分阶段计划

### Phase 0: 当前骨架

- 建立项目目录。
- 编写 README 初稿。
- 添加依赖清单。
- 添加基础配置样例。
- 添加最小结构测试。

### Phase 1: 数据与 mock fallback

- 实现 `yfinance` 数据获取适配器。
- 实现 mock data provider。
- 建立统一数据接口和异常回退机制。

### Phase 2: 定价与 Greeks

- 实现 Black-Scholes 欧式期权定价。
- 实现 Greeks 计算。
- 增加定价单元测试。

### Phase 3: 策略与回测

- 实现基础期权策略对象。
- 实现策略 payoff 和简单回测。
- 输出核心风险收益指标。

### Phase 4: Agent 与 Streamlit 展示

- 封装研究工具。
- 实现 Agent workflow。
- 使用 Streamlit 构建交互式展示页面。
- 生成可下载研究报告。

## 快速开始

```bash
python -m venv .venv
pip install -r requirements.txt
pytest
```

运行未来的 Streamlit 应用：

```bash
streamlit run app.py
```

当前 `app.py` 只是占位入口，完整交互界面将在后续阶段实现。
