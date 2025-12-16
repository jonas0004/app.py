import streamlit as st
import pandas as pd
import yfinance as yf
import pandas_ta as ta
import requests

st.set_page_config(
    page_title="S&P 500 Smart Screener",
    page_icon="📈",
    layout="wide"
)

@st.cache_data
def get_sp500_tickers():
    try:
        url = "https://raw.githubusercontent.com/datasets/s-and-p-500-companies/master/data/constituents.csv"
        df = pd.read_csv(url)
        return df['Symbol'].tolist()
    except Exception as e:
        st.error(f"Error loading ticker list: {e}")
        return []

def run_screener(tickers, use_rsi, rsi_thresh, use_ema, ema_tol, use_vol):
    candidates = []
    progress_bar = st.progress(0)
    status_text = st.empty()
    total = len(tickers)
    
    for i, ticker in enumerate(tickers):
        try:
            if i % 10 == 0:
                progress_bar.progress((i + 1) / total)
                status_text.text(f"Analyzing {i+1}/{total}: {ticker}...")
            
            df = yf.download(ticker, period="6mo", progress=False, threads=False)
            if len(df) < 50: 
                continue
            
            # yfinance sometimes returns multi-index columns
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            
            close = df['Close']
            volume = df['Volume']
            current_price = close.iloc[-1]

            match_rsi = True
            match_ema = True
            match_vol = True
            
            current_rsi = 0.0
            distance_pct = 0.0
            abs_distance = 0.0

            # RSI check
            rsi_series = ta.rsi(close, length=14)
            if rsi_series is not None:
                current_rsi = rsi_series.iloc[-1]
                if use_rsi and current_rsi > rsi_thresh:
                    match_rsi = False
            else:
                match_rsi = False

            # EMA proximity check
            ema_series = ta.ema(close, length=50)
            if ema_series is not None:
                ema_value = ema_series.iloc[-1]
                distance_pct = (current_price - ema_value) / ema_value * 100
                abs_distance = abs(distance_pct)
                
                if use_ema and abs_distance > ema_tol:
                    match_ema = False
            else:
                match_ema = False

            # Volume trend check
            if use_vol:
                recent_vol = volume.iloc[-3:].mean()
                prev_vol = volume.iloc[-6:-3].mean()
                if recent_vol <= prev_vol:
                    match_vol = False
            
            if match_rsi and match_ema and match_vol:
                candidates.append({
                    "Ticker": ticker,
                    "Price ($)": round(current_price, 2),
                    "RSI": round(current_rsi, 2),
                    "EMA50 Distance (%)": distance_pct,
                    "_abs_dist": abs_distance
                })

        except:
            continue
            
    status_text.empty()
    progress_bar.empty()
    return pd.DataFrame(candidates)


st.title("📈 S&P 500 Smart Screener")
st.caption("Real-time technical analysis across the S&P 500 index")

left_col, right_col = st.columns([1, 1], gap="large")

with left_col:
    st.subheader("🔍 Stock Screening")
    
    with st.expander("⚙️ Filter Settings", expanded=False):
        f_col1, f_col2 = st.columns(2)
        
        with f_col1:
            use_rsi = st.checkbox("RSI Filter", value=True, help="Find oversold stocks")
            rsi_limit = st.slider("Max RSI", 10, 80, 30, disabled=not use_rsi)
            use_vol = st.checkbox("Rising Volume", value=True)
            
        with f_col2:
            use_ema = st.checkbox("EMA50 Filter", value=True)
            ema_tol = st.slider("Max Distance (%)", 0.5, 10.0, 2.0, disabled=not use_ema)

    if st.button("🚀 Start Scan", use_container_width=True, type="primary"):
        tickers = get_sp500_tickers()
        
        if not tickers:
            st.error("Failed to load tickers")
        else:
            with st.spinner(f'Scanning {len(tickers)} stocks...'):
                st.session_state['scan_results'] = run_screener(
                    tickers, use_rsi, rsi_limit, use_ema, ema_tol, use_vol
                )

    if 'scan_results' in st.session_state and not st.session_state['scan_results'].empty:
        results = st.session_state['scan_results']
        st.success(f"✅ Found {len(results)} opportunities")
        
        results = results.sort_values(by="_abs_dist", ascending=True)
        
        def color_ema_dist(val):
            return f"color: {'#ff4b4b' if val < 0 else '#3dd56d'}"
        
        event = st.dataframe(
            results.drop(columns=["_abs_dist"])
                   .style
                   .map(color_ema_dist, subset=['EMA50 Distance (%)'])
                   .format({
                       "Price ($)": "{:.2f}", 
                       "RSI": "{:.2f}", 
                       "EMA50 Distance (%)": "{:+.2f}%"
                   }),
            use_container_width=True,
            hide_index=True,
            on_select="rerun",
            selection_mode="single-row"
        )
        
        selected_ticker = None
        if event.selection.rows:
            idx = event.selection.rows[0]
            selected_ticker = results.iloc[idx]['Ticker']
    else:
        st.info("👆 Click 'Start Scan' to begin")
        selected_ticker = None


with right_col:
    st.subheader("📊 Detail View")
    
    if selected_ticker:
        st.write(f"### {selected_ticker}")
        
        chart_data = yf.download(selected_ticker, period="1y", progress=False)
        
        if isinstance(chart_data.columns, pd.MultiIndex):
            chart_data.columns = chart_data.columns.get_level_values(0)
        
        chart_data['EMA50'] = ta.ema(chart_data['Close'], length=50)
        
        st.write("**Price & 50-Day EMA**")
        st.line_chart(chart_data[['Close', 'EMA50']], color=["#29b5e8", "#ff4b4b"])
        
        chart_data['RSI'] = ta.rsi(chart_data['Close'], length=14)
        st.write("**RSI Indicator**")
        st.line_chart(chart_data[['RSI']], color=["#FFA500"])
        
        if not chart_data.empty:
            latest = chart_data.iloc[-1]
            m1, m2, m3 = st.columns(3)
            
            m1.metric("Current Price", f"${latest['Close']:.2f}")
            m2.metric("RSI", f"{latest['RSI']:.2f}")
            
            vol_str = f"{latest['Volume'] / 1e6:.1f}M" if latest['Volume'] > 1e6 else f"{int(latest['Volume']):,}"
            m3.metric("Volume", vol_str)
        
    else:
        st.markdown(
            """
            <div style='text-align: center; padding: 120px 20px; color: #888;'>
                <h3>👈 Select a stock from the results</h3>
                <p>Click any row to view detailed analysis</p>
            </div>
            """, 
            unsafe_allow_html=True
        )
