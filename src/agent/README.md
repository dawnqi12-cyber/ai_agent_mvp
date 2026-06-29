# Agent

Rule-based research Agent and callable tools.

Implemented tools:

- Data fetch tool
- Black-Scholes pricing tool
- Greeks calculation tool
- Strategy construction tool
- Backtest simulation tool
- Report generation tool

`RuleBasedPlanner` interprets natural-language prompts into market bias,
objective, risk profile, ticker symbol, and a first-pass strategy. The report
generator is deterministic and works without an LLM. An optional OpenAI report
enhancement hook is available when `OPENAI_API_KEY` and the `openai` package are
present, but it is not required.
