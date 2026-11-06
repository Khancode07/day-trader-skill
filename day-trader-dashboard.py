from __future__ import annotations
import json
from pathlib import Path
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf

# Read-only companion to the original scanner repository.
REPO_ROOT = Path(r"C:\day-trader-skill")
WATCHLIST_CANDIDATES = [
    REPO_ROOT / "trader-scanner" / "trader" / "watchlist.json",
    REPO_ROOT / "trader" / "watchlist.json",
    REPO_ROOT / "trader-scanner" / "watchlist.json",
]

st.set_page_config(page_title="Day Trader Terminal", page_icon="📈", layout="wide")
st.markdown("""
<style>
.stApp {background:#080d16;color:#e8eef8}
[data-testid="stSidebar"] {background:#0d1422}
[data-testid="stMetric"] {background:#111c2d;border:1px solid #23334b;padding:13px;border-radius:10px}
.terminal-note {color:#9eacc1;font-size:.85rem}
</style>
""", unsafe_allow_html=True)

def find_watchlist():
    return next((p for p in WATCHLIST_CANDIDATES if p.exists()), None)

@st.cache_data(ttl=20)
def load_watchlist(path, modified):
    del modified
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict) or not isinstance(data.get("hits"), list):
        raise ValueError("Expected a JSON object containing a 'hits' list.")
    return data

@st.cache_data(ttl=60, show_spinner=False)
def load_history(symbol, period, interval):
    df = yf.Ticker(symbol).history(period=period, interval=interval, auto_adjust=False)
    if df is None or df.empty:
        return pd.DataFrame()
    df = df.copy()
    df["SMA 20"] = df["Close"].rolling(20).mean()
    df["SMA 50"] = df["Close"].rolling(50).mean()
    delta = df["Close"].diff()
    gain, loss = delta.clip(lower=0), -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1/14, min_periods=14, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/14, min_periods=14, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, pd.NA)
    df["RSI 14"] = 100 - 100 / (1 + rs)
    return df

@st.cache_data(ttl=60, show_spinner=False)
def load_market_overview():
    instruments = {
        "S&P 500": "^GSPC",
        "Nasdaq Composite": "^IXIC",
        "Dow Jones": "^DJI",
        "NIFTY 50": "^NSEI",
        "BSE Sensex": "^BSESN",
    }
    rows = []
    for name, symbol in instruments.items():
        try:
            hist = yf.Ticker(symbol).history(period="5d", interval="1d", auto_adjust=False)
            if hist is None or len(hist) < 1:
                rows.append({"Index": name, "Symbol": symbol, "Last": None, "Change %": None})
                continue
            last = float(hist["Close"].iloc[-1])
            previous = float(hist["Close"].iloc[-2]) if len(hist) > 1 else last
            change = ((last / previous) - 1) * 100 if previous else 0.0
            rows.append({"Index": name, "Symbol": symbol, "Last": last, "Change %": change})
        except Exception:
            rows.append({"Index": name, "Symbol": symbol, "Last": None, "Change %": None})
    return pd.DataFrame(rows)

LABELS = {
    "breakout_20d":"20-day breakout", "bull_flag":"Bull flag",
    "reclaim_ma20":"Reclaim MA20", "oversold":"Oversold (RSI < 30)",
    "oversold_bounce":"Oversold bounce", "orb":"Opening-range breakout",
}
def label(key):
    return LABELS.get(key, str(key).replace("_", " ").title())

def candle_chart(df, symbol, sma):
    fig = go.Figure(go.Candlestick(
        x=df.index, open=df["Open"], high=df["High"], low=df["Low"],
        close=df["Close"], name=symbol
    ))
    if sma:
        for col in ("SMA 20", "SMA 50"):
            fig.add_trace(go.Scatter(x=df.index, y=df[col], mode="lines", name=col))
    fig.update_layout(
        template="plotly_dark", height=500, margin=dict(l=8,r=8,t=25,b=8),
        paper_bgcolor="#080d16", plot_bgcolor="#080d16",
        xaxis_rangeslider_visible=False, legend=dict(orientation="h",y=1.02)
    )
    fig.update_xaxes(gridcolor="#1b293d")
    fig.update_yaxes(gridcolor="#1b293d",side="right")
    return fig

def risk_calculator(reference_price):
    st.subheader("Position & risk calculator")
    a,b,c = st.columns(3)
    capital = a.number_input("Account size ($)", min_value=0.0, value=1000.0, step=100.0)
    risk_pct = a.number_input("Risk per trade (%)", min_value=0.1, max_value=5.0, value=1.0, step=0.1)
    entry = b.number_input("Planned entry ($)", min_value=0.01, value=max(float(reference_price),0.01), step=0.5)
    stop = b.number_input("Stop-loss ($)", min_value=0.01, value=max(float(reference_price)*0.97,0.01), step=0.5)
    target = c.number_input("Target ($)", min_value=0.01, value=max(float(reference_price)*1.06,0.01), step=0.5)
    per_share = entry-stop
    if capital <= 0 or per_share <= 0 or target <= entry:
        st.warning("Stop-loss must be below entry and target must be above entry.")
        return
    risk_cash = capital*risk_pct/100
    shares = int(risk_cash//per_share)
    x,y,z,w = st.columns(4)
    x.metric("Share quantity",f"{shares:,}")
    y.metric("Position value",f"${shares*entry:,.2f}")
    z.metric("Planned risk",f"${shares*per_share:,.2f}")
    w.metric("Reward / risk",f"1 : {(target-entry)/per_share:.2f}")
    st.caption("Educational estimate only. It does not place orders or guarantee execution.")

st.title("📈 DAY TRADER TERMINAL")
st.caption("Scanner companion • Market charts • Risk tools • Learning workspace")
st.markdown('<p class="terminal-note">Reads your original scanner output. Does not change scanner rules or place trades.</p>',unsafe_allow_html=True)

top_a, top_b = st.columns([4, 1])
with top_a:
    st.subheader("Market overview")
    st.caption("US and India benchmark indices • Yahoo Finance data may be delayed.")
with top_b:
    if st.button("Refresh market data", use_container_width=True):
        load_market_overview.clear()
        load_history.clear()
        st.rerun()

market = load_market_overview()
market_cols = st.columns(5)
for col, (_, item) in zip(market_cols, market.iterrows()):
    if pd.notna(item["Last"]):
        change = item["Change %"]
        col.metric(str(item["Index"]), f'{item["Last"]:,.2f}',
                   f'{change:+.2f}%' if pd.notna(change) else None)
    else:
        col.metric(str(item["Index"]), "Unavailable")
st.divider()

watch_path = find_watchlist()
if watch_path is None:
    st.error("watchlist.json was not found. Checked these locations:")
    st.code("\n".join(str(p) for p in WATCHLIST_CANDIDATES))
    st.info("Check the actual output location of scan.py. Update REPO_ROOT near the top if your repo is in another folder.")
    st.stop()
try:
    doc = load_watchlist(str(watch_path),watch_path.stat().st_mtime)
except Exception as e:
    st.error(f"Could not read scanner output: {e}")
    st.stop()

hits = doc["hits"]
m1,m2,m3,m4 = st.columns(4)
m1.metric("Universe",f'{doc.get("universe",0):,}')
m2.metric("Charts scanned",f'{doc.get("scanned",0):,}')
m3.metric("Matching setups",f'{len(hits):,}')
m4.metric("Failed",f'{doc.get("failed",0):,}')
st.caption(f'Mode: {str(doc.get("mode","unknown")).upper()}  •  Data through: {doc.get("as_of","—")}  •  Created: {doc.get("created_at","—")}  •  Source: {doc.get("source","—")}')
if doc.get("note"):
    st.info(doc["note"])
if not hits:
    st.warning("The latest scanner output has no matching setups.")
    st.stop()

df = pd.DataFrame(hits)
if "setups" not in df:
    df["setups"] = [[] for _ in range(len(df))]
df["Setup"] = df["setups"].apply(lambda xs:", ".join(label(x) for x in (xs or [])))
if "price" in df: df["Price ($)"] = pd.to_numeric(df["price"],errors="coerce")
if "rsi" in df: df["RSI"] = pd.to_numeric(df["rsi"],errors="coerce")
if "volume" in df: df["Volume"] = pd.to_numeric(df["volume"],errors="coerce")

st.sidebar.header("Terminal controls")
query = st.sidebar.text_input("Find ticker",placeholder="e.g. AAPL")
setup_options = sorted({str(x) for row in hits for x in (row.get("setups") or [])})
setups = st.sidebar.multiselect("Setup filter",setup_options,format_func=label)
rsi_range = st.sidebar.slider("RSI range",0.0,100.0,(0.0,100.0))
sort = st.sidebar.selectbox("Sort by",["Scanner order","Price: high to low","RSI: low to high","Volume: high to low"])
view = df.copy()
if query:
    view = view[view["symbol"].astype(str).str.contains(query.strip(),case=False)]
if setups:
    view = view[view["setups"].apply(lambda xs:any(x in setups for x in (xs or [])))]
if "RSI" in view:
    view = view[view["RSI"].fillna(-1).between(*rsi_range)]
if sort == "Price: high to low" and "Price ($)" in view: view = view.sort_values("Price ($)",ascending=False)
if sort == "RSI: low to high" and "RSI" in view: view = view.sort_values("RSI")
if sort == "Volume: high to low" and "Volume" in view: view = view.sort_values("Volume",ascending=False)

left,right = st.columns([1.7,1])
with left:
    st.subheader("Scanner watchlist")
    cols = [c for c in ["symbol","Setup","Price ($)","RSI","Volume","close_date","at"] if c in view]
    st.dataframe(view[cols],use_container_width=True,hide_index=True,height=430)
with right:
    st.subheader("Setup distribution")
    tally = {}
    for xs in view["setups"]:
        for x in xs or []: tally[x] = tally.get(x,0)+1
    if tally:
        chart = pd.DataFrame([{"Setup":label(k),"Matches":v} for k,v in tally.items()]).sort_values("Matches")
        fig = go.Figure(go.Bar(x=chart["Matches"],y=chart["Setup"],orientation="h"))
        fig.update_layout(template="plotly_dark",height=430,margin=dict(l=8,r=8,t=20,b=8),paper_bgcolor="#080d16",plot_bgcolor="#080d16",showlegend=False)
        st.plotly_chart(fig,use_container_width=True)
    else:
        st.caption("No matching setups for these filters.")

st.download_button("Download filtered CSV",view.drop(columns=["setups"],errors="ignore").to_csv(index=False).encode("utf-8"),"day_trader_watchlist.csv","text/csv")
st.divider()
st.subheader("Instrument workspace")
symbols = view["symbol"].astype(str).tolist()
if not symbols:
    st.info("No ticker matches your filters. Clear a filter to continue.")
    st.stop()
ticker = st.selectbox("Select ticker",symbols)
row = next((r for r in hits if str(r.get("symbol"))==ticker),{})
reference = float(row.get("price") or 100.0)
detail,chart_col = st.columns([1,2.2])
with detail:
    st.markdown(f"### {ticker}")
    st.metric("Scanner reference price",f"${reference:,.2f}")
    st.write("**Matched setups**")
    for item in row.get("setups",[]): st.write("• "+label(item))
    if row.get("rsi") is not None: st.metric("Scanner RSI",f'{float(row["rsi"]):.1f}')
    if row.get("volume") is not None: st.metric("Scanner volume",f'{int(row["volume"]):,}')
    st.caption(f'Scanner close date: {row.get("close_date",doc.get("as_of","—"))}')
with chart_col:
    period = st.selectbox("Chart period",["1mo","3mo","6mo","1y","2y"],index=2)
    interval = st.selectbox("Candle interval",["1d","1h","30m","15m"],index=0)
    sma = st.checkbox("Show SMA 20 / SMA 50",True)
    with st.spinner(f"Loading {ticker} chart..."):
        hist = load_history(ticker,period,interval)
    if hist.empty:
        st.warning("Yahoo chart data is unavailable right now. Scanner results are still shown.")
    else:
        latest_close = float(hist["Close"].iloc[-1])
        previous_close = float(hist["Close"].iloc[-2]) if len(hist) > 1 else latest_close
        daily_change = ((latest_close / previous_close) - 1) * 100 if previous_close else 0.0
        q1, q2, q3 = st.columns(3)
        q1.metric("Latest available price", f"${latest_close:,.2f}", f"{daily_change:+.2f}%")
        q2.metric("Latest volume", f'{int(hist["Volume"].iloc[-1]):,}')
        q3.metric("Latest RSI 14", f'{hist["RSI 14"].iloc[-1]:.1f}' if pd.notna(hist["RSI 14"].iloc[-1]) else "—")
        st.plotly_chart(candle_chart(hist,ticker,sma),use_container_width=True)
        vf = go.Figure(go.Bar(x=hist.index,y=hist["Volume"],name="Volume"))
        vf.update_layout(template="plotly_dark",height=150,margin=dict(l=8,r=8,t=8,b=8),paper_bgcolor="#080d16",plot_bgcolor="#080d16",showlegend=False)
        st.plotly_chart(vf,use_container_width=True)
        if pd.notna(hist.iloc[-1].get("RSI 14")): st.metric("Chart RSI 14",f'{hist.iloc[-1]["RSI 14"]:.1f}')

with st.expander("Risk calculator",expanded=False):
    risk_calculator(reference)
st.divider()
st.header("Paper-trade journal")
st.caption("Record hypothetical trades only. This journal does not connect to a broker or place orders.")
journal_path = Path(__file__).resolve().parent / "paper_trade_journal.csv"
journal_columns = ["Recorded at", "Ticker", "Direction", "Entry", "Stop loss", "Target", "Quantity", "Notes"]
if journal_path.exists():
    try:
        journal = pd.read_csv(journal_path)
    except Exception:
        journal = pd.DataFrame(columns=journal_columns)
else:
    journal = pd.DataFrame(columns=journal_columns)

with st.form("paper_trade_form", clear_on_submit=True):
    j1, j2, j3 = st.columns(3)
    trade_ticker = j1.text_input("Ticker", value=ticker).strip().upper()
    direction = j2.selectbox("Direction", ["Long", "Short"])
    quantity = j3.number_input("Quantity", min_value=1, value=1, step=1)
    j4, j5, j6 = st.columns(3)
    entry_price = j4.number_input("Planned entry", min_value=0.01, value=max(reference, 0.01), step=0.5)
    stop_price = j5.number_input("Stop loss", min_value=0.01, value=max(reference * 0.97, 0.01), step=0.5)
    target_price = j6.number_input("Target", min_value=0.01, value=max(reference * 1.06, 0.01), step=0.5)
    trade_notes = st.text_input("Trade thesis / notes", placeholder="Why are you considering this setup?")
    submitted = st.form_submit_button("Save paper trade")
    if submitted:
        valid = bool(trade_ticker) and quantity > 0
        valid = valid and ((direction == "Long" and stop_price < entry_price < target_price) or
                           (direction == "Short" and target_price < entry_price < stop_price))
        if not valid:
            st.error("Check ticker and price levels. Long: stop < entry < target. Short: target < entry < stop.")
        else:
            new_row = {
                "Recorded at": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S"),
                "Ticker": trade_ticker, "Direction": direction, "Entry": entry_price,
                "Stop loss": stop_price, "Target": target_price, "Quantity": int(quantity),
                "Notes": trade_notes,
            }
            updated = pd.concat([journal, pd.DataFrame([new_row])], ignore_index=True)
            updated.to_csv(journal_path, index=False)
            st.success("Paper trade saved to the local journal.")
            st.rerun()

if not journal.empty:
    st.dataframe(journal, use_container_width=True, hide_index=True)
    st.download_button("Download paper-trade journal", journal.to_csv(index=False).encode("utf-8"),
                       "paper_trade_journal.csv", "text/csv")
else:
    st.info("No paper trades recorded yet.")

with st.expander("Trading setup learning guide",expanded=False):
    st.markdown("""
**20-day breakout:** latest completed daily close is above the previous 20 daily closes.

**Bull flag:** a strong prior rise followed by a relatively tight five-session range. This is a pattern, not a guarantee.

**Reclaim MA20:** prior close was below its 20-day average and the latest close finished above it.

**Oversold:** RSI 14 is below 30. Oversold does not mean the price must bounce.

**Oversold bounce:** RSI was below 30 on the prior session and the latest close finished higher.

**Opening-range breakout:** scanner checks the first 15 minutes by default, then looks for a completed five-minute close above the range high.

**Practice rule:** write down the entry reason, invalidation level, target, and risk before judging a trade. Review a meaningful sample of paper trades before considering real money.
""")
st.divider()
st.caption("Educational tool only. Yahoo Finance data can be delayed or unavailable. No broker orders are sent.")
