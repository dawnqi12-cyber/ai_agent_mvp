"""Command-line demo for the options research Agent."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.agent import run_agent_research


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the options research Agent demo.")
    parser.add_argument(
        "prompt",
        nargs="?",
        default="Analyze AAPL options and suggest a conservative income strategy",
    )
    parser.add_argument("--live-data", action="store_true", help="Try yfinance before mock fallback.")
    parser.add_argument("--period", default="1y", help="Historical price period for simulation.")
    parser.add_argument(
        "--llm-enhance",
        action="store_true",
        help="Optionally enhance report wording if OPENAI_API_KEY and openai package are available.",
    )
    args = parser.parse_args()

    result = run_agent_research(
        args.prompt,
        prefer_mock=not args.live_data,
        period=args.period,
        enable_llm_enhancement=args.llm_enhance,
    )
    print(result.report_markdown)


if __name__ == "__main__":
    main()
