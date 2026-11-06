import json
from pathlib import Path

import pandas as pd
import streamlit as st
import yfinance as yf
import plotly.graph_objects as go


# ============================================================
# 1. PAGE CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="Day Trader Research Terminal",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Dashboard is stored separately from the original repository.
ROOT = Path(r"C:\day-trader-skill")

WATCHLIST_PATH = (
    ROOT / "trader-scanner" / "trader" / "watchlist.json"
)


# ============================================================
# 2. DASHBOARD HEADER
# ============================================================

st.title("📈 DAY TRADER RESEARCH TERMINAL")

st.caption(
    "Original Day Trader Skill integration | "
    "Market Research | Technical Analysis | Risk Education"
)

st.info(
    "Research and paper-learning dashboard. "
    "No broker connection or real-money order execution."
)


# ============================================================
# 3. SIDEBAR SETTINGS
# ============================================================

with st.sidebar:

    st.header("⚙️ Dashboard Settings")

    market = st.selectbox(
        "Select Market",
        ["US Scanner", "Indian NSE"],
    )

    search = st.text_input(
        "Search Stock Symbol",
        placeholder="Example: TSLA",
    ).strip().upper()

    setup_filter = st.selectbox(
        "Filter Setup",
        [
            "All",
            "breakout_20d",
            "bull_flag",
            "reclaim_ma20",
            "oversold",
            "oversold_bounce",
        ],
    )

    st.divider()

    st.caption("Data sources: Yahoo Finance and original scanner.")
    st.caption("Market data may be delayed or unavailable.")


# ============================================================
# 4. WATCHLIST LOADER
# ============================================================

@st.cache_data(ttl=300)
def load_watchlist(path, modified):

    with open(path, "r", encoding="utf-8") as file:
        data = json.load(file)

    if isinstance(data, dict):

        data = data.get(
            "hits",
            data.get(
                "watchlist",
                data.get("results", []),
            ),
        )

    if not isinstance(data, list):
        return []

    return data


def get_symbol(record):

    return str(
        record.get(
            "symbol",
            record.get("ticker", ""),
        )
    ).strip().upper()


def get_setups(record):

    setups = record.get("setups", [])

    if isinstance(setups, str):
        return [setups]

    if isinstance(setups, list):
        return [str(item) for item in setups]

    return []


def safe_number(value):

    try:
        if pd.isna(value):
            return None

        return float(value)

    except (TypeError, ValueError):
        return None


# ============================================================
# 5. LOAD MARKET WATCHLIST
# ============================================================

records = []

if market == "US Scanner":

    if not WATCHLIST_PATH.exists():

        st.error(
            f"Original scanner watchlist not found:\n"
            f"{WATCHLIST_PATH}"
        )

        st.stop()

    try:

        records = load_watchlist(
            str(WATCHLIST_PATH),
            WATCHLIST_PATH.stat().st_mtime,
        )

    except Exception as error:

        st.error(f"Watchlist loading failed: {error}")
        st.stop()

else:

    st.info(
        "NSE mode uses manually entered symbols. "
        "This is not an integrated NSE scanner."
    )

    nse_symbols = st.text_input(
        "NSE symbols separated by commas",
        "RELIANCE.NS,TCS.NS,INFY.NS,HDFCBANK.NS,^NSEI",
    )

    records = [
        {
            "symbol": symbol.strip().upper(),
            "setups": ["manual_nse_symbol"],
        }
        for symbol in nse_symbols.split(",")
        if symbol.strip()
    ]


# ============================================================
# 6. FILTER WATCHLIST
# ============================================================

filtered = []

for record in records:

    if not isinstance(record, dict):
        continue

    symbol = get_symbol(record)
    setups = get_setups(record)

    if not symbol:
        continue

    if search and search not in symbol:
        continue

    if (
        setup_filter != "All"
        and setup_filter not in setups
    ):
        continue

    filtered.append(record)


# ============================================================
# 7. MARKET OVERVIEW
# ============================================================

if not filtered:

    st.warning(
        "No matching stocks found. "
        "Change the filters or check the scanner watchlist."
    )

    st.stop()


setup_count = sum(
    len(get_setups(record))
    for record in filtered
)

col1, col2, col3 = st.columns(3)

col1.metric(
    "Matching Stocks",
    len(filtered),
)

col2.metric(
    "Setup Labels",
    setup_count,
)

col3.metric(
    "Selected Market",
    market,
)


# ============================================================
# 8. SCANNER WATCHLIST TABLE
# ============================================================

st.divider()

st.subheader("🔎 Scanner Watchlist")

rows = []

for record in filtered:

    rows.append({

        "Symbol": get_symbol(record),

        "Price": safe_number(
            record.get("price")
        ),

        "RSI": safe_number(
            record.get("rsi")
        ),

        "Volume": safe_number(
            record.get("volume")
        ),

        "Close Date": record.get("close_date"),

        "Setups": ", ".join(
            get_setups(record)
        ),

    })


table = pd.DataFrame(rows)

st.dataframe(
    table,
    use_container_width=True,
    hide_index=True,
)


st.download_button(
    label="⬇️ Download Watchlist CSV",

    data=table.to_csv(
        index=False
    ).encode("utf-8"),

    file_name="day_trader_watchlist.csv",

    mime="text/csv",
)


# ============================================================
# 9. HISTORICAL MARKET DATA
# ============================================================

st.divider()

st.subheader("📊 Stock Chart & Technical Analysis")

symbols = [
    get_symbol(record)
    for record in filtered
]

selected = st.selectbox(
    "Select Stock",
    symbols,
)

period = st.selectbox(
    "Chart History",
    ["1mo", "3mo", "6mo", "1y", "2y"],
    index=2,
)


@st.cache_data(ttl=300)
def load_history(symbol, history_period):

    df = yf.download(
        symbol,
        period=history_period,
        interval="1d",
        auto_adjust=True,
        progress=False,
        threads=False,
    )

    if df is None or df.empty:
        return pd.DataFrame()

    # Handle Yahoo Finance MultiIndex columns.
    if isinstance(df.columns, pd.MultiIndex):

        df.columns = df.columns.get_level_values(0)

    df = df.loc[
        :,
        ~df.columns.duplicated()
    ].copy()

    required = [
        "Open",
        "High",
        "Low",
        "Close",
        "Volume",
    ]

    if not all(
        column in df.columns
        for column in required
    ):

        return pd.DataFrame()

    # Ensure numeric price columns.
    for column in required:

        df[column] = pd.to_numeric(
            df[column],
            errors="coerce",
        )

    df = df.dropna(
        subset=["Open", "High", "Low", "Close"]
    )

    if df.empty:
        return pd.DataFrame()

    # Moving averages.
    df["SMA20"] = (
        df["Close"].rolling(20).mean()
    )

    df["SMA50"] = (
        df["Close"].rolling(50).mean()
    )

    # RSI 14.
    delta = df["Close"].diff()

    gain = delta.clip(
        lower=0
    ).ewm(
        alpha=1 / 14,
        min_periods=14,
        adjust=False,
    ).mean()

    loss = (-delta.clip(
        upper=0
    )).ewm(
        alpha=1 / 14,
        min_periods=14,
        adjust=False,
    ).mean()

    rs = gain / loss.replace(
        0,
        float("nan"),
    )

    df["RSI"] = 100 - (
        100 / (1 + rs)
    )

    df.loc[
        (loss == 0) & (gain > 0),
        "RSI",
    ] = 100

    df.loc[
        (loss == 0) & (gain == 0),
        "RSI",
    ] = 50

    return df


# ============================================================
# 10. LOAD AND DISPLAY CHART
# ============================================================

if st.button(
    "🔄 Refresh Market Data",
    type="primary",
):

    load_history.clear()
    st.rerun()


try:

    with st.spinner(
        f"Loading historical data for {selected}..."
    ):

        history = load_history(
            selected,
            period,
        )

    if history.empty:

        st.warning(
            "Historical data unavailable. "
            "Check internet connection or try another symbol."
        )

    else:

        latest_close = safe_number(
            history["Close"].iloc[-1]
        )

        latest_rsi = safe_number(
            history["RSI"].iloc[-1]
        )

        latest_sma20 = safe_number(
            history["SMA20"].iloc[-1]
        )

        latest_sma50 = safe_number(
            history["SMA50"].iloc[-1]
        )

        # ----------------------------------------------------
        # Market statistics
        # ----------------------------------------------------

        a, b, c, d = st.columns(4)

        a.metric(
            "Latest Available Close",
            f"{latest_close:.2f}"
            if latest_close is not None
            else "N/A",
        )

        b.metric(
            "RSI (14)",
            f"{latest_rsi:.1f}"
            if latest_rsi is not None
            else "N/A",
        )

        c.metric(
            "SMA 20",
            f"{latest_sma20:.2f}"
            if latest_sma20 is not None
            else "N/A",
        )

        d.metric(
            "SMA 50",
            f"{latest_sma50:.2f}"
            if latest_sma50 is not None
            else "N/A",
        )

        # ----------------------------------------------------
        # Candlestick chart
        # ----------------------------------------------------

        st.subheader(
            f"📈 {selected} Price Chart"
        )

        fig = go.Figure()

        fig.add_trace(
            go.Candlestick(

                x=history.index,

                open=history["Open"],

                high=history["High"],

                low=history["Low"],

                close=history["Close"],

                name="Price",

            )
        )

        fig.add_trace(
            go.Scatter(
                x=history.index,
                y=history["SMA20"],
                name="SMA 20",
            )
        )

        fig.add_trace(
            go.Scatter(
                x=history.index,
                y=history["SMA50"],
                name="SMA 50",
            )
        )

        fig.update_layout(

            template="plotly_dark",

            title=f"{selected} Daily Price Chart",

            height=580,

            xaxis_rangeslider_visible=False,

            hovermode="x unified",

            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1,
            ),

        )

        st.plotly_chart(
            fig,
            use_container_width=True,
        )

        # ----------------------------------------------------
        # Volume chart
        # ----------------------------------------------------

        st.subheader("📊 Trading Volume")

        volume_fig = go.Figure()

        volume_fig.add_trace(
            go.Bar(
                x=history.index,
                y=history["Volume"],
                name="Volume",
            )
        )

        volume_fig.update_layout(
            template="plotly_dark",
            height=250,
            showlegend=False,
        )

        st.plotly_chart(
            volume_fig,
            use_container_width=True,
        )

        # ----------------------------------------------------
        # RSI chart
        # ----------------------------------------------------

        st.subheader("RSI Indicator")

        rsi_fig = go.Figure()

        rsi_fig.add_trace(
            go.Scatter(
                x=history.index,
                y=history["RSI"],
                name="RSI 14",
            )
        )

        rsi_fig.add_hline(
            y=70,
            line_dash="dash",
            annotation_text="Overbought",
        )

        rsi_fig.add_hline(
            y=30,
            line_dash="dash",
            annotation_text="Oversold",
        )

        rsi_fig.update_layout(
            template="plotly_dark",
            height=280,
            yaxis_range=[0, 100],
        )

        st.plotly_chart(
            rsi_fig,
            use_container_width=True,
        )


        # ====================================================
        # 11. LEARNING MODE
        # ====================================================

        with st.expander(
            "🎓 Learn Technical Indicators"
        ):

            st.markdown(
                """
                **SMA 20:** Average closing price over 20 sessions.

                **SMA 50:** Average closing price over 50 sessions.

                **RSI 14:**
                - Above 70: Traditionally considered overbought.
                - Below 30: Traditionally considered oversold.
                - Around 50: Middle momentum zone.

                These are educational reference levels,
                not guaranteed buy or sell signals.
                """
            )


        # ====================================================
        # 12. HYPOTHETICAL RISK CALCULATOR
        # ====================================================

        st.divider()

        st.subheader(
            "🛡️ Hypothetical Risk Calculator"
        )

        st.caption(
            "Illustrative calculations only. "
            "Not a trade recommendation."
        )

        if latest_close is not None and latest_close > 0:

            entry = st.number_input(

                "Hypothetical Entry Price",

                min_value=0.01,

                value=float(
                    round(latest_close, 2)
                ),

                step=0.1,

            )

            side = st.radio(

                "Position Direction",

                ["Long", "Short"],

                horizontal=True,

            )

            stop_pct = st.number_input(

                "Stop Distance (%)",

                min_value=0.1,

                max_value=20.0,

                value=2.0,

                step=0.1,

            )

            rr = st.selectbox(

                "Reward / Risk Ratio",

                [1.5, 2.0, 3.0],

                index=1,

            )

            distance = entry * stop_pct / 100

            if side == "Long":

                stop_price = entry - distance

                target_price = entry + (
                    distance * rr
                )

            else:

                stop_price = entry + distance

                target_price = entry - (
                    distance * rr
                )

            x, y, z = st.columns(3)

            x.metric(
                "Example Stop",
                f"{stop_price:.2f}",
            )

            y.metric(
                "Example Target",
                f"{target_price:.2f}",
            )

            z.metric(
                "Reward / Risk",
                f"1:{rr:.1f}",
            )

            risk_budget = st.number_input(

                "Hypothetical Risk Budget",

                min_value=0.0,

                value=100.0,

                step=50.0,

            )

            quantity = (
                int(risk_budget / distance)
                if distance > 0
                else 0
            )

            st.write(
                f"Illustrative quantity: **{quantity}**"
            )

            st.caption(
                "Excludes fees, taxes, slippage, "
                "lot sizes, affordability and gap risk."
            )

        else:

            st.warning(
                "A valid closing price is required "
                "for the risk calculator."
            )


except Exception as error:

    st.error(
        f"Market data or chart request failed: {error}"
    )


# ============================================================
# 13. DISCLAIMER
# ============================================================

st.divider()

st.warning(
    """
    Research and education only.

    Historical market data may be delayed, incomplete,
    rate-limited or unavailable.

    Scanner matches are not guaranteed profitable trades.

    This dashboard does not validate strategy profitability.

    No broker is connected and no real orders are placed.
    """
)