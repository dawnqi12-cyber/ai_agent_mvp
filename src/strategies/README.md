# Strategies

Explainable option strategy definitions and expiration payoff calculators.

Implemented strategies:

- Covered Call
- Protective Put
- Bull Call Spread
- Bear Put Spread
- Iron Condor

Each constructor returns a `StrategyResult` with the strategy name, market view,
legs, max profit, max loss, breakeven points, payoff curve data, key risks, and
suitable / unsuitable market environments.
