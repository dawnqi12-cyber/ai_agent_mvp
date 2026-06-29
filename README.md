# Option Strategy Research Agent

一个用于作品集和面试展示的 **期权策略研究 AI Agent MVP**。项目使用 Python 构建，围绕“自然语言研究需求 -> 数据获取 -> 期权定价 -> 策略构建 -> 简化模拟 -> Markdown 研究报告”的流程，展示量化投研场景下 Agent 工具编排的完整闭环。

> 免责声明：本项目仅用于教育、研究和作品集展示，不构成投资、交易、税务或法律建议。期权具有高风险，真实交易前需要独立研究和专业意见。

## 项目背景

很多量化投研 demo 只停留在 notebook、单个公式或静态图表层面，难以体现工程化能力和 Agent 编排能力。本项目把期权研究流程拆成多个可复用工具，并用 rule-based planner 串联成一个本地可运行的投研 Agent。

项目刻意保留 mock data fallback：即使没有网络、`yfinance` 不可用，或者 ticker 暂时没有数据，系统也能完整演示。这一点对面试和作品集展示很重要。

## 核心功能

- **Streamlit 中文投研界面**：ticker 输入、市场观点、风险偏好、到期日选择、一键运行 Agent。
- **市场数据获取**：优先使用 `yfinance`，失败时自动切换到 mock data。
- **Mock 数据支持**：内置 `SPY`、`QQQ`、`AAPL`，也可为其他 ticker 生成可演示数据。
- **Black-Scholes 定价**：支持欧式 call / put 理论价格。
- **Greeks 计算**：Delta、Gamma、Theta、Vega、Rho。
- **隐含波动率反解**：使用 Brent 方法从市场价格反推 implied volatility。
- **期权策略构建**：Covered Call、Protective Put、Bull Call Spread、Bear Put Spread、Iron Condor。
- **简化策略模拟**：支持 Covered Call、Protective Put、Bull Call Spread，输出累计收益、最大回撤、胜率、平均收益和权益曲线。
- **Agent 编排**：将数据、定价、策略、模拟、报告封装为可调用工具。
- **Markdown 研究报告**：自动生成包含摘要、市场快照、波动率、期权链、策略、风险和免责声明的报告。
- **可选 LLM 增强**：如果环境存在 `OPENAI_API_KEY` 且安装 `openai` 包，可预留报告润色；没有 API key 时完整功能仍可运行。

## 技术架构

```text
app.py                         # Streamlit 中文投研 Demo
scripts/
  demo_agent.py                 # 命令行 Agent Demo
config/
  settings.example.yaml         # 配置样例
src/
  data/                         # yfinance + mock market data
  pricing/                      # Black-Scholes, Greeks, implied volatility
  strategies/                   # 期权策略定义与 payoff
  backtest/                     # 简化策略模拟
  agent/                        # planner, tools, report generator
  visualization/                # 后续可视化扩展预留
  utils/                        # 后续通用工具预留
tests/                          # pytest 测试
```

## 模块说明

| 模块 | 主要职责 |
| --- | --- |
| `src/data/` | 获取当前价格、历史价格、期权到期日、option chain；提供 mock fallback 和 historical volatility。 |
| `src/pricing/` | Black-Scholes call / put 定价、Greeks、implied volatility、参数校验。 |
| `src/strategies/` | 策略 legs、最大收益、最大亏损、盈亏平衡点、到期 payoff 曲线、风险说明。 |
| `src/backtest/` | 基于历史价格的 research prototype 策略模拟，输出核心绩效指标。 |
| `src/agent/` | Rule-based planner、Agent 工具封装、Markdown 报告生成。 |
| `app.py` | 面向面试演示的 Streamlit 中文界面。 |

## Agent 工作流

1. **解析用户意图**：`RuleBasedPlanner` 从自然语言中识别 ticker、市场观点、目标和风险偏好。
2. **获取市场数据**：`MarketDataClient` 优先调用 `yfinance`，失败时回退 mock provider。
3. **分析波动率**：基于历史收盘价计算 annualized historical volatility。
4. **获取期权链**：读取指定到期日的 calls / puts。
5. **计算 Greeks**：对参考期权合约计算 Delta、Gamma、Theta、Vega、Rho。
6. **构建策略**：根据 planner 结果生成 Covered Call、Protective Put、价差或 Iron Condor。
7. **运行简化模拟**：对已支持策略进行滚动持有窗口模拟。
8. **生成研究报告**：输出 Markdown 报告，包含结论、数据、策略、风险和免责声明。

## 金融计算模块说明

### Black-Scholes 与 Greeks

`src/pricing/black_scholes.py` 实现：

- 欧式 call / put 理论价格
- Delta、Gamma、Theta、Vega、Rho
- implied volatility 反解
- 输入参数校验：`spot`、`strike`、`time_to_expiry`、`volatility`、`risk_free_rate`、`option_type`

约定：

- Theta 按年表示。
- Vega 和 Rho 按 1.0 波动率 / 利率变动表示，UI 层可按需要缩放。
- 不依赖 LLM 做任何金融计算。

### 策略模块

`src/strategies/options.py` 实现：

- Covered Call
- Protective Put
- Bull Call Spread
- Bear Put Spread
- Iron Condor

每个策略返回统一的 `StrategyResult`：

- 策略名称
- 适用市场观点
- 组合腿信息 `legs`
- 最大收益
- 最大亏损
- 盈亏平衡点
- 到期 payoff 曲线 `pandas.DataFrame`
- 主要风险说明
- 适合 / 不适合的市场环境

### 简化模拟模块

`src/backtest/simulator.py` 是 research prototype，不追求机构级回测精度。它使用历史收盘价、固定持有窗口、Black-Scholes 入场权利金估算和到期 payoff 计算策略表现。

当前支持：

- Covered Call
- Protective Put
- Bull Call Spread

输出：

- 累计收益
- 最大回撤
- 胜率
- 平均收益
- 权益曲线
- 逐笔交易明细

## 如何运行

建议使用 Python 3.10+。

```bash
python -m venv .venv
pip install -r requirements.txt
```

运行测试：

```bash
python -m pytest
```

启动 Streamlit 中文 Demo：

```bash
streamlit run app.py
```

打开本地地址：

```text
http://127.0.0.1:8501
```

命令行 Agent Demo：

```bash
python scripts/demo_agent.py "Analyze AAPL options and suggest a conservative income strategy" --period 6mo
```

默认建议使用 mock data 模式，保证无网络环境也能稳定演示。如果希望优先尝试真实数据，可在命令行 demo 中加：

```bash
--live-data
```

## 示例输入输出

示例输入：

```text
Analyze AAPL options and suggest a conservative income strategy
```

Planner 解析结果示例：

```text
symbol: AAPL
market_bias: neutral
objective: income
risk_profile: conservative
recommended_strategy: Covered Call
```

报告输出包含：

```text
Executive Summary
Market Snapshot
Volatility Analysis
Option Chain Observations
Strategy Recommendation
Payoff / Risk Analysis
Simulation Result
Risk Disclosure
Not Financial Advice Disclaimer
```

Streamlit 页面展示：

- 当前价格
- 历史波动率
- 期权链摘要
- 推荐策略
- 策略 legs
- Greeks 表格
- payoff 图
- 简化模拟结果
- Markdown 研究报告

## 风险声明

本项目的所有输出仅用于教育、研究和作品集展示：

- 不构成真实投资建议。
- 不构成买入、卖出或持有任何证券或衍生品的建议。
- 简化模拟忽略滑点、手续费、bid/ask spread、保证金、提前行权、流动性、税务、真实成交约束等因素。
- Mock data 仅用于演示，不代表真实市场。
- 真实期权交易具有高风险，可能造成重大损失。

## 面试讲解话术

可以按下面的顺序讲：

1. **项目定位**：这是一个期权策略研究 Agent MVP，不是普通聊天机器人，而是投研工具链的自动编排。
2. **为什么做 fallback**：面试现场网络不稳定，真实数据源也可能返回空数据，所以我实现了 yfinance + mock fallback，保证演示可靠。
3. **金融计算可信度**：Black-Scholes、Greeks、IV 反解都由确定性 Python 代码完成，不依赖 LLM 计算。
4. **Agent 的价值**：Agent 不直接“猜答案”，而是把数据、定价、策略、模拟、报告这些工具按工作流组织起来。
5. **工程结构**：数据、定价、策略、回测、Agent、UI 分层清晰，方便测试和扩展。
6. **边界意识**：我明确标注这是 research prototype，不把简化回测包装成真实交易系统。
7. **可扩展性**：后续可以接真实 broker API、更完整期权回测、LLM 报告润色、多策略比较和组合优化。

## 简历 Bullet Points

- Built a Python-based Options Strategy Research Agent MVP with Streamlit UI, modular pricing, strategy, backtesting, and reporting layers.
- Implemented Black-Scholes call/put pricing, Greeks, and implied volatility solver with deterministic numerical methods and pytest coverage.
- Designed a resilient market data layer using `yfinance` with automatic mock data fallback for offline demos.
- Built explainable option strategy constructors for Covered Call, Protective Put, Bull/Bear Spreads, and Iron Condor with payoff curves and risk descriptions.
- Developed a rule-based Agent planner that maps natural-language investment intent to strategy workflows and generates Markdown research reports.
- Added simplified historical strategy simulation with cumulative return, max drawdown, win rate, average return, and equity curve outputs.

## 当前完成度

- 项目结构：完成
- 数据层：完成 MVP
- 定价层：完成 MVP
- 策略层：完成 MVP
- 简化模拟：完成 MVP
- Agent 编排：完成 MVP
- Streamlit 中文 Demo：完成 MVP
- 测试：覆盖核心计算、数据 fallback、策略、模拟和 Agent demo

## 后续扩展方向

- 增加真实期权链清洗与合约筛选逻辑。
- 使用真实 bid/ask、滑点、手续费和保证金规则增强回测。
- 增加多策略横向比较和策略打分。
- 接入 LLM 进行报告润色、策略解释和问答，但保留确定性金融计算。
- 支持导出 PDF / HTML 报告。
- 增加 Plotly 交互式 Greeks 曲面、IV smile、期限结构图。
- 增加 Dockerfile、CI、线上 demo 部署。
