"""Streamlit UI for the Option Strategy Research Agent demo."""

from __future__ import annotations

from datetime import date

import pandas as pd
import plotly.graph_objects as go

try:
    import streamlit as st
except ModuleNotFoundError:  # pragma: no cover - helpful when dependencies are not installed.
    st = None

from src.agent.planner import RuleBasedPlanner
from src.agent.tools import AgentToolkit
from src.data import MarketDataClient
from src.strategies import StrategyResult


MARKET_VIEW_OPTIONS = {
    "收益型": "income",
    "看涨": "bullish",
    "看跌": "bearish",
    "中性": "neutral",
    "对冲保护": "hedge",
}
RISK_PROFILE_OPTIONS = {
    "保守": "conservative",
    "平衡": "balanced",
    "激进": "aggressive",
}


def _cache_data(func):
    if st is None:
        return func
    return st.cache_data(show_spinner=False)(func)


def main() -> None:
    """Run the local Streamlit demo."""

    if st is None:
        print("Streamlit is not installed yet. Install dependencies with: pip install -r requirements.txt")
        return

    st.set_page_config(
        page_title="期权策略研究 Agent",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    _inject_css()

    st.markdown(
        """
        <div class="app-header">
          <div>
            <p class="eyebrow">量化投研 Agent MVP</p>
            <h1>期权策略研究 Agent</h1>
            <p class="subtle">集市场数据、期权分析、策略构建、简化模拟与研究报告生成于一体的本地投研工作台。</p>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    controls = _render_sidebar()
    expirations = _load_expirations(controls["ticker"], controls["prefer_mock"])
    expiration = st.sidebar.selectbox("到期日", expirations, index=0)
    st.sidebar.caption("Mock 数据模式可以保证无网络环境下完整演示。")

    if st.sidebar.button("运行 Agent", type="primary", use_container_width=True):
        _run_and_render(controls, expiration)
    else:
        _render_empty_state(controls["ticker"], expiration)


def _render_sidebar() -> dict[str, object]:
    st.sidebar.title("研究参数")
    ticker = st.sidebar.text_input("标的代码", value="AAPL").strip().upper() or "AAPL"
    market_view_label = st.sidebar.selectbox("市场观点", list(MARKET_VIEW_OPTIONS), index=0)
    risk_profile_label = st.sidebar.select_slider(
        "风险偏好",
        options=list(RISK_PROFILE_OPTIONS),
        value="保守",
    )
    period = st.sidebar.selectbox("历史窗口", ["6mo", "1y", "2y"], index=1)
    prefer_mock = st.sidebar.toggle("使用 Mock 数据", value=True)
    return {
        "ticker": ticker,
        "market_view": MARKET_VIEW_OPTIONS[market_view_label],
        "risk_profile": RISK_PROFILE_OPTIONS[risk_profile_label],
        "period": period,
        "prefer_mock": prefer_mock,
    }


@_cache_data
def _load_expirations(ticker: str, prefer_mock: bool) -> list[str]:
    client = MarketDataClient(prefer_mock=prefer_mock)
    try:
        return client.get_expirations(ticker)
    except Exception:
        fallback = MarketDataClient(prefer_mock=True)
        return fallback.get_expirations(ticker)


def _run_and_render(controls: dict[str, object], expiration: str) -> None:
    ticker = str(controls["ticker"])
    market_view = str(controls["market_view"])
    risk_profile = str(controls["risk_profile"])
    period = str(controls["period"])
    prefer_mock = bool(controls["prefer_mock"])
    prompt = f"Analyze {ticker} options and suggest a {risk_profile} {market_view} strategy"

    with st.spinner("正在运行投研工作流..."):
        planner = RuleBasedPlanner()
        plan = planner.plan(prompt)
        toolkit = AgentToolkit(prefer_mock=prefer_mock)
        market_data = toolkit.get_market_data(ticker, period=period)
        option_chain = toolkit.get_option_chain(ticker, expiration=expiration)
        greeks = toolkit.calculate_greeks(
            spot=market_data.snapshot.price,
            strike=_reference_strike(option_chain, market_data.snapshot.price, plan.strategy_key),
            time_to_expiry=_time_to_expiry(expiration),
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
        )

    _render_snapshot(market_data, option_chain)
    _render_data_source_notice(market_data, prefer_mock)
    overview_tab, strategy_tab, analytics_tab, report_tab = st.tabs(
        ["总览", "策略", "分析", "研究报告"]
    )

    with overview_tab:
        _render_option_chain_summary(option_chain)
        _render_simulation(simulation)

    with strategy_tab:
        _render_strategy(strategy)
        _render_payoff_chart(strategy)

    with analytics_tab:
        _render_greeks(greeks)
        _render_history_chart(market_data.history, ticker)

    with report_tab:
        st.markdown(report)
        st.download_button(
            "下载 Markdown 报告",
            data=report,
            file_name=f"{ticker.lower()}_option_strategy_report.md",
            mime="text/markdown",
            use_container_width=True,
        )


def _render_snapshot(market_data, option_chain) -> None:
    snapshot = market_data.snapshot
    calls_count = len(option_chain.calls)
    puts_count = len(option_chain.puts)
    cols = st.columns(4)
    cols[0].metric("当前价格", f"{snapshot.price:.2f} {snapshot.currency}")
    cols[1].metric("历史波动率", f"{market_data.historical_volatility:.2%}")
    cols[2].metric("期权合约数", f"{calls_count + puts_count}")
    cols[3].metric("数据来源", _provider_label(market_data.provider))


def _render_data_source_notice(market_data, prefer_mock: bool) -> None:
    if market_data.provider != "mock":
        st.success("当前使用 yfinance 真实数据。")
        return
    if prefer_mock:
        st.info("当前开启了 Mock 数据模式，因此使用本地模拟数据。")
        return
    reason = market_data.fallback_reason or "yfinance 未返回可用数据"
    st.warning(f"已尝试 yfinance，但获取失败，已自动回退到 Mock 数据。原因：{reason}")


def _render_option_chain_summary(option_chain) -> None:
    st.subheader("期权链摘要")
    summary = pd.DataFrame(
        [
            _chain_side_summary("看涨期权", option_chain.calls),
            _chain_side_summary("看跌期权", option_chain.puts),
        ]
    )
    st.dataframe(summary, use_container_width=True, hide_index=True)

    col1, col2 = st.columns(2)
    with col1:
        st.caption("看涨期权")
        st.dataframe(_compact_chain(option_chain.calls), use_container_width=True, hide_index=True)
    with col2:
        st.caption("看跌期权")
        st.dataframe(_compact_chain(option_chain.puts), use_container_width=True, hide_index=True)


def _render_strategy(strategy: StrategyResult) -> None:
    st.subheader(_strategy_label(strategy.name))
    st.write(_market_view_text(strategy.name, strategy.market_view))

    cols = st.columns(3)
    cols[0].metric("最大收益", _format_metric(strategy.max_profit))
    cols[1].metric("最大亏损", _format_metric(strategy.max_loss))
    cols[2].metric("盈亏平衡点", ", ".join(f"{point:.2f}" for point in strategy.breakeven_points))

    st.caption("策略组合腿")
    legs = pd.DataFrame(
        [
            {
                "工具": _instrument_label(leg.instrument),
                "方向": _position_label(leg.position),
                "数量": leg.quantity,
                "行权价": leg.strike,
                "权利金/价格": leg.premium,
                "说明": _leg_description_label(leg.description),
            }
            for leg in strategy.legs
        ]
    )
    st.dataframe(legs, use_container_width=True, hide_index=True)

    risk_col, fit_col = st.columns(2)
    with risk_col:
        st.caption("主要风险")
        for risk in strategy.risks:
            st.write(f"- {_risk_label(risk)}")
    with fit_col:
        st.caption("适用环境")
        st.write(f"适合：{_environment_label(strategy.suitable_market)}")
        st.write(f"不适合：{_environment_label(strategy.unsuitable_market)}")


def _render_greeks(greeks) -> None:
    st.subheader("Greeks 希腊值")
    greeks_frame = pd.DataFrame(
        [
            {"指标": "Delta", "数值": greeks.delta},
            {"指标": "Gamma", "数值": greeks.gamma},
            {"指标": "Theta", "数值": greeks.theta},
            {"指标": "Vega", "数值": greeks.vega},
            {"指标": "Rho", "数值": greeks.rho},
        ]
    )
    st.dataframe(greeks_frame, use_container_width=True, hide_index=True)


def _render_payoff_chart(strategy: StrategyResult) -> None:
    st.subheader("到期 Payoff 曲线")
    payoff = strategy.payoff_curve
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=payoff["underlying_price"],
            y=payoff["payoff"],
            mode="lines",
            name="到期收益",
            line={"color": "#0f766e", "width": 3},
        )
    )
    fig.add_hline(y=0, line_color="#525252", line_dash="dash")
    fig.update_layout(
        height=420,
        margin={"l": 30, "r": 20, "t": 20, "b": 30},
        xaxis_title="到期标的价格",
        yaxis_title="收益",
        template="plotly_white",
    )
    st.plotly_chart(fig, use_container_width=True)


def _render_simulation(simulation) -> None:
    st.subheader("简化策略模拟")
    if simulation is None:
        st.info("当前策略暂未接入简化模拟。")
        return

    cols = st.columns(4)
    cols[0].metric("累计收益", f"{simulation.cumulative_return:.2%}")
    cols[1].metric("最大回撤", f"{simulation.max_drawdown:.2%}")
    cols[2].metric("胜率", f"{simulation.win_rate:.2%}")
    cols[3].metric("平均收益", f"{simulation.average_return:.2%}")

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=simulation.equity_curve["date"],
            y=simulation.equity_curve["equity"],
            mode="lines+markers",
            name="权益曲线",
            line={"color": "#2563eb", "width": 3},
        )
    )
    fig.update_layout(
        height=360,
        margin={"l": 30, "r": 20, "t": 20, "b": 30},
        xaxis_title="日期",
        yaxis_title="权益",
        template="plotly_white",
    )
    st.plotly_chart(fig, use_container_width=True)
    st.caption("说明：该简化模拟仅用于教育和研究，不构成真实交易建议。")


def _render_history_chart(history: pd.DataFrame, ticker: str) -> None:
    st.subheader("历史价格")
    close_col = "Adj Close" if "Adj Close" in history.columns else "Close"
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=history.index,
            y=history[close_col],
            mode="lines",
            name=ticker,
            line={"color": "#7c2d12", "width": 2},
        )
    )
    fig.update_layout(
        height=360,
        margin={"l": 30, "r": 20, "t": 20, "b": 30},
        xaxis_title="日期",
        yaxis_title="价格",
        template="plotly_white",
    )
    st.plotly_chart(fig, use_container_width=True)


def _render_empty_state(ticker: str, expiration: str) -> None:
    col1, col2, col3 = st.columns(3)
    col1.info(f"标的代码：{ticker}")
    col2.info(f"到期日：{expiration}")
    col3.info("等待运行")
    st.markdown(
        """
        <div class="empty-panel">
          <h3>本地投研工作台已就绪</h3>
          <p>在左侧配置输入参数，然后运行 Agent，即可生成策略推荐、分析视图、简化模拟结果和 Markdown 研究报告。</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _chain_side_summary(side: str, frame: pd.DataFrame) -> dict[str, object]:
    return {
        "类型": side,
        "合约数": len(frame),
        "最低行权价": float(frame["strike"].min()) if not frame.empty else None,
        "最高行权价": float(frame["strike"].max()) if not frame.empty else None,
        "隐含波动率中位数": float(frame["impliedVolatility"].median()) if "impliedVolatility" in frame else None,
        "总未平仓量": int(frame["openInterest"].sum()) if "openInterest" in frame else None,
    }


def _compact_chain(frame: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "contractSymbol",
        "strike",
        "lastPrice",
        "bid",
        "ask",
        "volume",
        "openInterest",
        "impliedVolatility",
        "inTheMoney",
    ]
    available = [column for column in columns if column in frame.columns]
    return frame[available].head(12).rename(
        columns={
            "contractSymbol": "合约代码",
            "strike": "行权价",
            "lastPrice": "最新价",
            "bid": "买价",
            "ask": "卖价",
            "volume": "成交量",
            "openInterest": "未平仓量",
            "impliedVolatility": "隐含波动率",
            "inTheMoney": "实值",
        }
    )


def _reference_strike(option_chain, spot: float, strategy_key: str) -> float:
    frame = option_chain.puts if strategy_key in {"protective_put", "bear_put_spread"} else option_chain.calls
    target = spot * 0.95 if strategy_key in {"protective_put", "bear_put_spread"} else spot * 1.05
    filtered = (
        frame[frame["strike"] <= target]
        if strategy_key in {"protective_put", "bear_put_spread"}
        else frame[frame["strike"] >= target]
    )
    candidates = filtered if not filtered.empty else frame
    selected = candidates.iloc[(candidates["strike"] - target).abs().argsort()].iloc[0]
    return float(selected["strike"])


def _time_to_expiry(expiration: str) -> float:
    expiry = pd.Timestamp(expiration).date()
    days = max((expiry - date.today()).days, 1)
    return days / 365


def _format_metric(value: float) -> str:
    if value == float("inf"):
        return "无限"
    return f"{value:.2f}"


def _provider_label(provider: str) -> str:
    if provider == "mock":
        return "Mock 数据"
    if provider == "yfinance":
        return "yfinance"
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


def _instrument_label(instrument: str) -> str:
    return {"stock": "股票", "call": "看涨期权", "put": "看跌期权"}.get(instrument, instrument)


def _position_label(position: str) -> str:
    return {"long": "买入", "short": "卖出"}.get(position, position)


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


def _inject_css() -> None:
    st.markdown(
        """
        <style>
        .block-container {
            padding-top: 2rem;
            padding-bottom: 3rem;
            max-width: 1320px;
        }
        .app-header {
            border: 1px solid #d7ded9;
            border-radius: 8px;
            padding: 1.4rem 1.6rem;
            margin-bottom: 1.2rem;
            background: #fbfcfa;
        }
        .app-header h1 {
            margin: 0;
            font-size: 2.1rem;
            letter-spacing: 0;
            color: #111827;
        }
        .eyebrow {
            text-transform: uppercase;
            font-size: 0.78rem;
            letter-spacing: 0.08rem;
            color: #0f766e;
            font-weight: 700;
            margin-bottom: 0.35rem;
        }
        .subtle {
            color: #4b5563;
            margin: 0.45rem 0 0 0;
            max-width: 860px;
        }
        .empty-panel {
            border: 1px solid #e5e7eb;
            border-radius: 8px;
            padding: 1.4rem;
            margin-top: 1rem;
            background: #ffffff;
        }
        .empty-panel h3 {
            margin-top: 0;
            color: #111827;
        }
        div[data-testid="stMetric"] {
            border: 1px solid #e5e7eb;
            border-radius: 8px;
            padding: 0.8rem 1rem;
            background: #ffffff;
            color: #111827;
        }
        div[data-testid="stMetric"] * {
            color: #111827 !important;
        }
        div[data-testid="stMetricLabel"] p {
            color: #4b5563 !important;
            font-weight: 600;
        }
        div[data-testid="stMetricValue"] {
            color: #111827 !important;
            font-weight: 700;
        }
        div[data-testid="stMetricDelta"] {
            color: #374151 !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
