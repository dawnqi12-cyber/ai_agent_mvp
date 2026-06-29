from src.agent import RuleBasedPlanner, run_agent_research


def test_planner_detects_conservative_income_prompt() -> None:
    plan = RuleBasedPlanner().plan("Analyze AAPL options and suggest a conservative income strategy")

    assert plan.symbol == "AAPL"
    assert plan.market_bias == "neutral"
    assert plan.objective == "income"
    assert plan.risk_profile == "conservative"
    assert plan.strategy_key == "covered_call"


def test_agent_demo_prompt_generates_complete_report() -> None:
    result = run_agent_research(
        "Analyze AAPL options and suggest a conservative income strategy",
        prefer_mock=True,
        period="6mo",
    )

    report = result.report_markdown

    assert result.plan.strategy_key == "covered_call"
    assert result.strategy.name == "Covered Call"
    assert result.simulation is not None
    assert "# 期权策略研究报告" in report
    assert "## 执行摘要" in report
    assert "## 市场快照" in report
    assert "## 波动率分析" in report
    assert "## 期权链观察" in report
    assert "## 策略建议" in report
    assert "## Payoff / 风险分析" in report
    assert "## 简化模拟结果" in report
    assert "## 风险披露" in report
    assert "## 非投资建议免责声明" in report
    assert "不构成投资" in report
