"""Markdown research report generation for the options Agent."""

from __future__ import annotations

import os
from dataclasses import dataclass

import pandas as pd

from src.agent.planner import AgentPlan
from src.backtest import BacktestResult, RESEARCH_DISCLAIMER
from src.data import MarketSnapshot, OptionChain
from src.pricing import Greeks
from src.strategies import StrategyResult

NOT_FINANCIAL_ADVICE = (
    "本报告仅用于教育、研究和作品集展示，不构成投资、交易、税务或法律建议。"
    "期权具有较高风险，可能不适合所有投资者。"
)


@dataclass(frozen=True)
class ReportInputs:
    plan: AgentPlan
    snapshot: MarketSnapshot
    historical_volatility: float
    option_chain: OptionChain
    greeks: Greeks
    strategy: StrategyResult
    simulation: BacktestResult | None
    provider: str


def generate_markdown_report(
    inputs: ReportInputs,
    enable_llm_enhancement: bool = False,
) -> str:
    """Generate a complete Markdown research report without requiring an LLM."""

    strategy = inputs.strategy
    simulation = inputs.simulation
    report = "\n\n".join(
        [
            "# 期权策略研究报告",
            _executive_summary(inputs),
            _market_snapshot(inputs.snapshot, inputs.provider),
            _volatility_analysis(inputs.historical_volatility),
            _option_chain_observations(inputs.option_chain),
            _strategy_recommendation(inputs.plan, strategy),
            _payoff_risk_analysis(strategy, inputs.greeks),
            _simulation_result(simulation),
            _risk_disclosure(strategy),
            _not_financial_advice(),
        ]
    )
    if enable_llm_enhancement:
        return enhance_report_with_llm(report)
    return report


def enhance_report_with_llm(report: str) -> str:
    """Optional hook for future LLM polishing when OpenAI credentials exist.

    The project deliberately does not depend on this path. If the API key or
    package is unavailable, the deterministic report is returned unchanged.
    """

    if not os.getenv("OPENAI_API_KEY"):
        return report
    try:
        from openai import OpenAI  # type: ignore
    except Exception:
        return report + "\n\n<!-- LLM enhancement skipped: OpenAI package is not installed. -->"

    try:
        client = OpenAI()
        response = client.responses.create(
            model=os.getenv("OPENAI_REPORT_MODEL", "gpt-4.1-mini"),
            input=(
                "请润色下面这份中文期权研究报告，保留所有数字、风险提示和免责声明：\n\n"
                f"{report}"
            ),
        )
        enhanced = getattr(response, "output_text", None)
        return enhanced if enhanced else report
    except Exception:
        return report + "\n\n<!-- LLM enhancement skipped: request failed. -->"


def _executive_summary(inputs: ReportInputs) -> str:
    return (
        "## 执行摘要\n"
        f"- 用户需求：{inputs.plan.user_input}\n"
        f"- 意图识别：{_bias_label(inputs.plan.market_bias)} / "
        f"{_objective_label(inputs.plan.objective)} / {_risk_profile_label(inputs.plan.risk_profile)}\n"
        f"- 推荐策略：{_strategy_label(inputs.strategy.name)}\n"
        f"- Planner 逻辑：{_planner_rationale_label(inputs.plan)}"
    )


def _market_snapshot(snapshot: MarketSnapshot, provider: str) -> str:
    return (
        "## 市场快照\n"
        f"- 标的代码：{snapshot.symbol}\n"
        f"- 当前价格：{snapshot.price:.2f} {snapshot.currency}\n"
        f"- 数据来源：{_provider_label(provider)}"
    )


def _volatility_analysis(historical_volatility: float) -> str:
    return (
        "## 波动率分析\n"
        f"- 年化历史波动率：{historical_volatility:.2%}\n"
        "- 计算方法：基于收盘价对数收益率，并按 252 个交易日年化。"
    )


def _option_chain_observations(option_chain: OptionChain) -> str:
    calls = _summarize_option_side(option_chain.calls)
    puts = _summarize_option_side(option_chain.puts)
    return (
        "## 期权链观察\n"
        f"- 分析到期日：{option_chain.expiration}\n"
        f"- 看涨期权数量：{len(option_chain.calls)}；行权价范围：{calls}\n"
        f"- 看跌期权数量：{len(option_chain.puts)}；行权价范围：{puts}\n"
        f"- 期权链来源：{_provider_label(option_chain.provider)}"
    )


def _strategy_recommendation(plan: AgentPlan, strategy: StrategyResult) -> str:
    legs = "\n".join(
        f"- {_position_label(leg.position)} {leg.quantity:g} 份 {_instrument_label(leg.instrument)}"
        + (f"，行权价 {leg.strike:.2f}" if leg.strike is not None else "")
        + (f"，权利金/价格 {leg.premium:.2f}" if leg.premium else "")
        + (f"（{_leg_description_label(leg.description)}）" if leg.description else "")
        for leg in strategy.legs
    )
    breakevens = ", ".join(f"{point:.2f}" for point in strategy.breakeven_points)
    return (
        "## 策略建议\n"
        f"- 策略：{_strategy_label(strategy.name)}\n"
        f"- 市场观点：{_market_view_text(strategy.name, strategy.market_view)}\n"
        f"- Planner 分类：{_bias_label(plan.market_bias)}、{_objective_label(plan.objective)}、"
        f"{_risk_profile_label(plan.risk_profile)}\n"
        f"- 最大收益：{_format_number(strategy.max_profit)}\n"
        f"- 最大亏损：{_format_number(strategy.max_loss)}\n"
        f"- 盈亏平衡点：{breakevens}\n"
        "\n组合腿：\n"
        f"{legs}"
    )


def _payoff_risk_analysis(strategy: StrategyResult, greeks: Greeks) -> str:
    payoff = strategy.payoff_curve
    best = payoff.loc[payoff["payoff"].idxmax()]
    worst = payoff.loc[payoff["payoff"].idxmin()]
    return (
        "## Payoff / 风险分析\n"
        f"- 样本价格区间内最佳收益：{best['payoff']:.2f}，对应标的价格 {best['underlying_price']:.2f}\n"
        f"- 样本价格区间内最差收益：{worst['payoff']:.2f}，对应标的价格 {worst['underlying_price']:.2f}\n"
        f"- 参考期权 Delta：{greeks.delta:.4f}\n"
        f"- 参考期权 Gamma：{greeks.gamma:.4f}\n"
        f"- 参考期权 Theta：{greeks.theta:.4f}\n"
        f"- 参考期权 Vega：{greeks.vega:.4f}\n"
        f"- 参考期权 Rho：{greeks.rho:.4f}\n"
        f"- 适合市场：{_environment_label(strategy.suitable_market)}\n"
        f"- 不适合市场：{_environment_label(strategy.unsuitable_market)}"
    )


def _simulation_result(simulation: BacktestResult | None) -> str:
    if simulation is None:
        return (
            "## 简化模拟结果\n"
            "- 当前策略暂未接入简化模拟模块。"
        )
    return (
        "## 简化模拟结果\n"
        f"- 模拟策略：{_strategy_label(simulation.strategy_name)}\n"
        f"- 累计收益：{simulation.cumulative_return:.2%}\n"
        f"- 最大回撤：{simulation.max_drawdown:.2%}\n"
        f"- 胜率：{simulation.win_rate:.2%}\n"
        f"- 平均单笔收益：{simulation.average_return:.2%}\n"
        f"- 模拟交易笔数：{len(simulation.trades)}\n"
        "- 原型说明：该简化模拟仅用于教育和研究，忽略许多真实交易细节，不构成投资建议。"
    )


def _risk_disclosure(strategy: StrategyResult) -> str:
    risks = "\n".join(f"- {_risk_label(risk)}" for risk in strategy.risks)
    return (
        "## 风险披露\n"
        f"{risks}\n"
        f"- 回测限制：{_research_disclaimer_label(RESEARCH_DISCLAIMER)}"
    )


def _not_financial_advice() -> str:
    return "## 非投资建议免责声明\n" + NOT_FINANCIAL_ADVICE


def _summarize_option_side(frame: pd.DataFrame) -> str:
    if frame.empty or "strike" not in frame.columns:
        return "无数据"
    return f"{float(frame['strike'].min()):.2f} 至 {float(frame['strike'].max()):.2f}"


def _format_number(value: float) -> str:
    if value == float("inf"):
        return "无限"
    return f"{value:.2f}"


def _provider_label(provider: str) -> str:
    if provider == "mock":
        return "Mock 数据"
    return provider


def _strategy_label(name: str) -> str:
    labels = {
        "Covered Call": "备兑看涨 Covered Call",
        "Protective Put": "保护性看跌 Protective Put",
        "Bull Call Spread": "牛市看涨价差 Bull Call Spread",
        "Bear Put Spread": "熊市看跌价差 Bear Put Spread",
        "Iron Condor": "铁鹰 Iron Condor",
    }
    return labels.get(name, name)


def _bias_label(value: str) -> str:
    return {"bullish": "看涨", "bearish": "看跌", "neutral": "中性"}.get(value, value)


def _objective_label(value: str) -> str:
    return {
        "income": "收益型",
        "hedge": "对冲保护",
        "directional": "方向性",
        "range": "区间震荡",
    }.get(value, value)


def _risk_profile_label(value: str) -> str:
    return {"conservative": "保守", "balanced": "平衡", "aggressive": "激进"}.get(value, value)


def _position_label(position: str) -> str:
    return {"long": "买入", "short": "卖出"}.get(position, position)


def _instrument_label(instrument: str) -> str:
    return {"stock": "股票", "call": "看涨期权", "put": "看跌期权"}.get(instrument, instrument)


def _leg_description_label(description: str) -> str:
    labels = {
        "Buy underlying stock": "买入标的股票",
        "Sell call option": "卖出看涨期权",
        "Buy protective put": "买入保护性看跌期权",
        "Buy lower-strike call": "买入低行权价看涨期权",
        "Sell higher-strike call": "卖出高行权价看涨期权",
        "Buy higher-strike put": "买入高行权价看跌期权",
        "Sell lower-strike put": "卖出低行权价看跌期权",
        "Buy lower-strike protective put": "买入低行权价保护性看跌期权",
        "Sell higher-strike put": "卖出高行权价看跌期权",
        "Sell lower-strike call": "卖出低行权价看涨期权",
        "Buy higher-strike protective call": "买入高行权价保护性看涨期权",
    }
    return labels.get(description, description)


def _market_view_text(strategy_name: str, fallback: str) -> str:
    labels = {
        "Covered Call": "中性到温和看涨：通过卖出看涨期权获取权利金，同时接受上涨空间被封顶。",
        "Protective Put": "看好标的长期表现，但希望通过买入看跌期权限定下行风险。",
        "Bull Call Spread": "温和看涨：用有限成本表达上涨观点，同时收益上限明确。",
        "Bear Put Spread": "温和看跌：用有限成本表达下跌观点，同时收益上限明确。",
        "Iron Condor": "中性区间观点：预期标的价格维持在一定范围内震荡。",
    }
    return labels.get(strategy_name, fallback)


def _planner_rationale_label(plan: AgentPlan) -> str:
    return (
        f"识别到{_bias_label(plan.market_bias)}观点、{_objective_label(plan.objective)}目标、"
        f"{_risk_profile_label(plan.risk_profile)}风险偏好，因此选择"
        f"{_strategy_label(plan.strategy_key.replace('_', ' ').title())}作为第一版研究策略。"
    )


def _risk_label(risk: str) -> str:
    labels = {
        "Upside is capped above the short call strike.": "标的价格高于卖出看涨期权行权价后，上涨收益被封顶。",
        "Downside stock risk remains significant if the underlying falls sharply.": "如果标的大幅下跌，股票多头仍会承受显著下行风险。",
        "Assignment risk exists when the short call is in the money.": "卖出的看涨期权进入实值后，存在被行权或指派风险。",
        "Protection has a cost and raises the breakeven price.": "保护性期权需要支付成本，会抬高盈亏平衡点。",
        "Upside remains exposed to the premium drag.": "上涨收益会受到权利金成本拖累。",
        "Put protection only applies through the selected expiration.": "看跌保护仅在所选到期日前有效。",
        "Maximum profit is capped above the higher strike.": "价格高于高行权价后，最大收益被封顶。",
        "The strategy can lose the full net debit if the underlying finishes below the lower strike.": "若到期价格低于低行权价，可能损失全部净权利金支出。",
        "Time decay can hurt if the expected move does not happen.": "若预期行情迟迟未出现，时间价值衰减可能不利。",
        "Maximum profit is capped below the lower strike.": "价格低于低行权价后，最大收益被封顶。",
        "The strategy can lose the full net debit if the underlying finishes above the higher strike.": "若到期价格高于高行权价，可能损失全部净权利金支出。",
        "A slow or shallow decline may not overcome premium paid.": "若下跌幅度或速度不足，收益可能无法覆盖权利金成本。",
        "Large moves beyond either short strike can quickly turn the trade unprofitable.": "标的大幅突破任一卖出行权价后，策略可能快速转亏。",
        "Maximum loss occurs if price moves beyond either long wing at expiration.": "若到期价格突破任一买入保护腿，可能触及最大亏损。",
        "Short options carry assignment and liquidity risk.": "卖出期权存在指派风险和流动性风险。",
    }
    return labels.get(risk, risk)


def _environment_label(text: str) -> str:
    labels = {
        "Sideways to moderately rising markets with elevated call premiums.": "震荡到温和上涨、且看涨期权权利金较高的市场。",
        "Strong bull markets or sharp selloffs.": "强劲单边上涨或急跌市场。",
        "Bullish markets where the investor still wants crash protection.": "看涨但仍希望防范尾部下跌风险的市场。",
        "Low-volatility sideways markets where insurance premium may decay.": "低波动震荡市场，保护性权利金可能持续衰减。",
        "Moderately bullish markets with a clear upside target.": "温和看涨且有明确上方目标位的市场。",
        "Strongly bullish markets where capped upside is unattractive, or bearish markets.": "强烈看涨时收益封顶可能不划算，或处于看跌市场。",
        "Moderately bearish markets with a defined downside target.": "温和看跌且有明确下方目标位的市场。",
        "Strongly bearish markets where capped profit is limiting, or bullish markets.": "强烈看跌时收益封顶可能限制表现，或处于看涨市场。",
        "Range-bound markets with elevated option premiums and no expected breakout.": "区间震荡、期权权利金较高且暂不预期突破的市场。",
        "Trending, event-driven, or high-breakout-risk markets.": "趋势性行情、事件驱动行情或突破风险较高的市场。",
    }
    return labels.get(text, text)


def _research_disclaimer_label(disclaimer: str) -> str:
    if disclaimer == RESEARCH_DISCLAIMER:
        return "该简化回测仅用于教育和研究，忽略许多真实交易细节，不构成投资建议。"
    return disclaimer
