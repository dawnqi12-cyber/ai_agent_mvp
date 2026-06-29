"""Rule-based planning for the options research Agent."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

MarketBias = Literal["bullish", "bearish", "neutral"]
Objective = Literal["income", "hedge", "directional", "range"]
RiskProfile = Literal["conservative", "balanced", "aggressive"]
StrategyKey = Literal[
    "covered_call",
    "protective_put",
    "bull_call_spread",
    "bear_put_spread",
    "iron_condor",
]


@dataclass(frozen=True)
class AgentPlan:
    """Interpreted user intent and selected research workflow."""

    user_input: str
    symbol: str
    market_bias: MarketBias
    objective: Objective
    risk_profile: RiskProfile
    strategy_key: StrategyKey
    rationale: str


class RuleBasedPlanner:
    """Small deterministic planner used before an LLM is introduced."""

    _known_symbols = {"SPY", "QQQ", "AAPL", "MSFT", "TSLA", "NVDA", "AMZN", "GOOGL", "META"}

    def plan(self, user_input: str) -> AgentPlan:
        if not user_input or not user_input.strip():
            raise ValueError("user_input must not be empty")

        text = user_input.lower()
        symbol = self._extract_symbol(user_input)
        market_bias = self._detect_market_bias(text)
        objective = self._detect_objective(text, market_bias)
        risk_profile = self._detect_risk_profile(text)
        strategy_key = self._select_strategy(market_bias, objective, risk_profile)
        rationale = self._build_rationale(market_bias, objective, risk_profile, strategy_key)

        return AgentPlan(
            user_input=user_input,
            symbol=symbol,
            market_bias=market_bias,
            objective=objective,
            risk_profile=risk_profile,
            strategy_key=strategy_key,
            rationale=rationale,
        )

    def _extract_symbol(self, user_input: str) -> str:
        tokens = re.findall(r"\b[A-Z]{1,5}\b", user_input)
        for token in tokens:
            if token in self._known_symbols:
                return token
        for token in tokens:
            if token not in {"AI", "API", "ETF"}:
                return token
        return "AAPL"

    def _detect_market_bias(self, text: str) -> MarketBias:
        bearish_words = {"bearish", "downside", "decline", "fall", "put", "protect", "hedge"}
        bullish_words = {"bullish", "upside", "rise", "growth", "rally", "call"}
        neutral_words = {"neutral", "range", "sideways", "income", "yield", "premium", "condor"}

        if any(word in text for word in bearish_words):
            return "bearish"
        if any(word in text for word in neutral_words):
            return "neutral"
        if any(word in text for word in bullish_words):
            return "bullish"
        return "neutral"

    def _detect_objective(self, text: str, market_bias: MarketBias) -> Objective:
        if any(word in text for word in ("income", "yield", "premium", "covered call")):
            return "income"
        if any(word in text for word in ("hedge", "protect", "insurance", "downside")):
            return "hedge"
        if any(word in text for word in ("range", "sideways", "neutral", "condor")):
            return "range"
        if market_bias in {"bullish", "bearish"}:
            return "directional"
        return "income"

    def _detect_risk_profile(self, text: str) -> RiskProfile:
        if any(word in text for word in ("conservative", "low risk", "safer", "defensive")):
            return "conservative"
        if any(word in text for word in ("aggressive", "high risk", "speculative", "leveraged")):
            return "aggressive"
        return "balanced"

    def _select_strategy(
        self,
        market_bias: MarketBias,
        objective: Objective,
        risk_profile: RiskProfile,
    ) -> StrategyKey:
        if objective == "income":
            return "covered_call" if risk_profile == "conservative" else "iron_condor"
        if objective == "hedge":
            return "protective_put"
        if objective == "range":
            return "iron_condor"
        if market_bias == "bullish":
            return "bull_call_spread"
        if market_bias == "bearish":
            return "bear_put_spread"
        return "covered_call"

    def _build_rationale(
        self,
        market_bias: MarketBias,
        objective: Objective,
        risk_profile: RiskProfile,
        strategy_key: StrategyKey,
    ) -> str:
        strategy_name = strategy_key.replace("_", " ").title()
        return (
            f"Detected {market_bias} bias, {objective} objective, and {risk_profile} risk profile; "
            f"selected {strategy_name} as the first-pass research strategy."
        )
