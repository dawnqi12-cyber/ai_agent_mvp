"""Future Streamlit entry point for the Option Strategy Research Agent."""


def main() -> None:
    """Keep the current MVP intentionally light."""
    try:
        import streamlit as st
    except ModuleNotFoundError:
        print("Streamlit is not installed yet. Install dependencies with: pip install -r requirements.txt")
        return

    st.set_page_config(page_title="Option Strategy Research Agent", layout="wide")
    st.title("Option Strategy Research Agent")
    st.caption("MVP skeleton: data, pricing, Greeks, strategy, backtest, and report tools.")
    st.info("Core research features will be implemented in later phases.")


if __name__ == "__main__":
    main()
