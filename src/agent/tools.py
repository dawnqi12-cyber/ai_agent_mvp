"""Callable tools for the options research Agent workflow."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from src.agent.planner import AgentPlan, RuleBasedPlanner, StrategyKey
from src.agent.report_generator import ReportInputs, generate_markdown_report
from src.backtest import BacktestResult, run_strategy_backtest
from src.data import MarketDataClient, MarketSnapshot, OptionChain, historical_volatility
from src.pricing import Greeks, black_scholes_greeks
from src.strategies import (
    StrategyResult,
    bear_put_spread,
    bull_call_spread,
    covered_call,
    iron_condor,
    protective_put,
)


@dataclass(frozen=True)
class MarketDataBundle:
    snapshot: MarketSnapshot
    history: pd.DataFrame
    historical_volatility: float
    provider: str
    fallback_reason: str | None = None


@dataclass(frozen=True)
class AgentRunResult:
    plan: AgentPlan
    market_data: MarketDataBundle
    option_chain: OptionChain
    greeks: Greeks
    strategy: StrategyResult
    simulation: BacktestResult | None
    report_markdown: str


class AgentToolkit:
    """Tool wrapper around data, pricing, strategy, backtest, and reporting modules."""

    _simulatable_strategies = {"covered_call", "protective_put", "bull_call_spread"}

    def __init__(
        self,
        data_client: MarketDataClient | None = None,
        prefer_mock: bool = False,
        risk_free_rate: float = 0.04,
    ) -> None:
        self.data_client = data_client or MarketDataClient(prefer_mock=prefer_mock)
        self.risk_free_rate = risk_free_rate

    def get_market_data(self, symbol: str, period: str = "1y") -> MarketDataBundle:
        history = self.data_client.get_history(symbol, period=period)
        snapshot = self.data_client.get_snapshot(symbol)
        hv = historical_volatility(history)
        return MarketDataBundle(
            snapshot=snapshot,
            history=history,
            historical_volatility=hv,
            provider=self.data_client.last_provider or snapshot.provider,
            fallback_reason=self.data_client.last_fallback_reason,
        )

    def get_option_chain(self, symbol: str, expiration: str | None = None) -> OptionChain:
        return self.data_client.get_option_chain(symbol, expiration=expiration)

    def calculate_greeks(
        self,
        spot: float,
        strike: float,
        time_to_expiry: float,
        volatility: float,
        option_type: str = "call",
    ) -> Greeks:
        if option_type not in {"call", "put"}:
            raise ValueError("option_type must be 'call' or 'put'")
        return black_scholes_greeks(
            spot=spot,
            strike=strike,
            time_to_expiry=time_to_expiry,
            risk_free_rate=self.risk_free_rate,
            volatility=volatility,
            option_type=option_type,
        )

    def build_strategy(
        self,
        plan: AgentPlan,
        market_data: MarketDataBundle,
        option_chain: OptionChain,
    ) -> StrategyResult:
        spot = market_data.snapshot.price
        if plan.strategy_key == "covered_call":
            call = _select_option(option_chain.calls, target_strike=spot * 1.05, direction="above")
            return covered_call(spot=spot, call_strike=call["strike"], call_premium=call["premium"])

        if plan.strategy_key == "protective_put":
            put = _select_option(option_chain.puts, target_strike=spot * 0.95, direction="below")
            return protective_put(spot=spot, put_strike=put["strike"], put_premium=put["premium"])

        if plan.strategy_key == "bull_call_spread":
            lower = _select_option(option_chain.calls, target_strike=spot, direction="above")
            higher = _select_option(
                option_chain.calls, target_strike=lower["strike"] * 1.08, direction="above"
            )
            return bull_call_spread(
                lower_strike=lower["strike"],
                higher_strike=higher["strike"],
                long_call_premium=lower["premium"],
                short_call_premium=higher["premium"],
                spot=spot,
            )

        if plan.strategy_key == "bear_put_spread":
            higher = _select_option(option_chain.puts, target_strike=spot, direction="below")
            lower = _select_option(option_chain.puts, target_strike=higher["strike"] * 0.92, direction="below")
            return bear_put_spread(
                lower_strike=lower["strike"],
                higher_strike=higher["strike"],
                long_put_premium=higher["premium"],
                short_put_premium=lower["premium"],
                spot=spot,
            )

        return _build_iron_condor(spot, option_chain)

    def run_simulation(
        self,
        strategy_key: StrategyKey,
        history: pd.DataFrame,
    ) -> BacktestResult | None:
        if strategy_key not in self._simulatable_strategies:
            return None
        return run_strategy_backtest(
            history=history,
            strategy_type=strategy_key,  # type: ignore[arg-type]
            risk_free_rate=self.risk_free_rate,
        )

    def generate_report(
        self,
        plan: AgentPlan,
        market_data: MarketDataBundle,
        option_chain: OptionChain,
        greeks: Greeks,
        strategy: StrategyResult,
        simulation: BacktestResult | None,
        enable_llm_enhancement: bool = False,
    ) -> str:
        return generate_markdown_report(
            ReportInputs(
                plan=plan,
                snapshot=market_data.snapshot,
                historical_volatility=market_data.historical_volatility,
                option_chain=option_chain,
                greeks=greeks,
                strategy=strategy,
                simulation=simulation,
                provider=market_data.provider,
            ),
            enable_llm_enhancement=enable_llm_enhancement,
        )


def run_agent_research(
    user_input: str,
    prefer_mock: bool = True,
    period: str = "1y",
    enable_llm_enhancement: bool = False,
) -> AgentRunResult:
    """Run the rule-based Agent workflow and return a full Markdown report."""

    planner = RuleBasedPlanner()
    plan = planner.plan(user_input)
    toolkit = AgentToolkit(prefer_mock=prefer_mock)
    market_data = toolkit.get_market_data(plan.symbol, period=period)
    option_chain = toolkit.get_option_chain(plan.symbol)
    greeks = toolkit.calculate_greeks(
        spot=market_data.snapshot.price,
        strike=_reference_strike(plan.strategy_key, market_data.snapshot.price, option_chain),
        time_to_expiry=30 / 365,
        volatility=max(market_data.historical_volatility, 0.05),
        option_type="put" if plan.strategy_key in {"protective_put", "bear_put_spread"} else "call",
    )
    strategy = toolkit.build_strategy(plan, market_data, option_chain)
    simulation = toolkit.run_simulation(plan.strategy_key, market_data.history)
    report = toolkit.generate_report(
        plan=plan,
        market_data=market_data,
        option_chain=option_chain,
        greeks=greeks,
        strategy=strategy,
        simulation=simulation,
        enable_llm_enhancement=enable_llm_enhancement,
    )
    return AgentRunResult(
        plan=plan,
        market_data=market_data,
        option_chain=option_chain,
        greeks=greeks,
        strategy=strategy,
        simulation=simulation,
        report_markdown=report,
    )


def _select_option(frame: pd.DataFrame, target_strike: float, direction: str) -> dict[str, float]:
    if frame.empty:
        raise ValueError("option chain side must not be empty")
    options = frame.copy()
    if direction == "above":
        filtered = options[options["strike"] >= target_strike]
    elif direction == "below":
        filtered = options[options["strike"] <= target_strike]
    else:
        raise ValueError("direction must be above or below")
    if filtered.empty:
        filtered = options
    selected = filtered.iloc[(filtered["strike"] - target_strike).abs().argsort()].iloc[0]
    return {"strike": float(selected["strike"]), "premium": _option_premium(selected)}


def _option_premium(row: pd.Series) -> float:
    bid = _positive_float(row.get("bid"))
    ask = _positive_float(row.get("ask"))
    if bid is not None and ask is not None and ask >= bid:
        return max((bid + ask) / 2, 0.01)
    last_price = _positive_float(row.get("lastPrice"))
    if last_price is not None:
        return last_price
    return 0.01


def _positive_float(value: Any) -> float | None:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    return numeric if numeric > 0 else None


def _build_iron_condor(spot: float, option_chain: OptionChain) -> StrategyResult:
    long_put = _select_option(option_chain.puts, target_strike=spot * 0.85, direction="below")
    short_put = _select_option(option_chain.puts, target_strike=spot * 0.92, direction="below")
    short_call = _select_option(option_chain.calls, target_strike=spot * 1.08, direction="above")
    long_call = _select_option(option_chain.calls, target_strike=spot * 1.15, direction="above")
    return iron_condor(
        long_put_strike=long_put["strike"],
        short_put_strike=short_put["strike"],
        short_call_strike=short_call["strike"],
        long_call_strike=long_call["strike"],
        long_put_premium=long_put["premium"],
        short_put_premium=short_put["premium"],
        short_call_premium=short_call["premium"],
        long_call_premium=long_call["premium"],
        spot=spot,
    )


def _reference_strike(strategy_key: StrategyKey, spot: float, option_chain: OptionChain) -> float:
    if strategy_key in {"protective_put", "bear_put_spread"}:
        return _select_option(option_chain.puts, spot * 0.95, "below")["strike"]
    return _select_option(option_chain.calls, spot * 1.05, "above")["strike"]
