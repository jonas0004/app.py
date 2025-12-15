import streamlit as st
import pandas as pd
import yfinance as yf
import pandas_ta as ta
import requests

st.set_page_config(
    page_title="S&P 500 Custom Screener",
    page_icon="🎛️",
    layout="wide"
)

# loading data
@st.cache_data
def get_sp500_tickers():
    try:
        url = "https://raw.githubusercontent.com/datasets/s-and-p-500-companies/master/data/constituents.csv"
        df = pd.read_csv(url)
        return df['Symbol'].tolist()
    except Exception as e:
        st.error(f"Fehler beim Laden der Ticker-Liste: {e}")
        return []

#  screener
def run_screener(tickers, use_rsi, rsi_thresh, use_ema, ema_tol, use_vol):
    candidates = []
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    total_tickers = len(tickers)
    
    for i, t in enumerate(tickers):
        try:
            if i % 10 == 0:
                progress_bar.progress((i + 1) / total_tickers)
                status_text.text(f"Analysiere {i+1}/{total_tickers}: {t}...")
            
        
            df = yf.download(t, period="6mo", progress=False, threads=False)
            if len(df) < 50: continue
            
         
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            
            close = df['Close']
            volume = df['Volume']

            match_rsi = True
            match_ema = True
            match_vol = True
            
            current_rsi = 0.0
            raw_dist_pct = 0.0  
            abs_dist_pct = 0.0 
            
            final_close = close.iloc[-1]

            # 1. RSI CHECK
            rsi_series = ta.rsi(close, length=14)
            if rsi_series is not None:
                current_rsi = rsi_series.iloc[-1]
                if use_rsi and current_rsi > rsi_thresh:
                    match_rsi = False
            else:
                match_rsi = False

            # 2. EMA CHECK
            ema_series = ta.ema(close, length=50)
            if ema_series is not None:
                current_ema = ema_series.iloc[-1]
                
               
                raw_dist_pct = (final_close - current_ema) / current_ema * 100
                
         
                abs_dist_pct = abs(raw_dist_pct)
                
                if use_ema and abs_dist_pct > ema_tol:
                    match_ema = False
            else:
                match_ema = False

            # 3. VOLUME CHECK
            if use_vol:
                vol_recent = volume.iloc[-3:].mean()
                vol_prev = volume.iloc[-6:-3].mean()
                if vol_recent <= vol_prev:
                    match_vol = False
            
            # adding when all criteria is fulfilled
            if match_rsi and match_ema and match_vol:
                candidates.append({
                    "Ticker": t,
                    "Kurs ($)": round(final_close, 2),
                    "RSI": round(current_rsi, 2),
                    "Abstand EMA50 (%)": raw_dist_pct, 
                    "_abs_dist": abs_dist_pct 
                })

        except Exception:
            continue
            
    status_text.empty()
    progress_bar.empty()
    return pd.DataFrame(candidates)


# FRONTEND

st.set_page_config(layout="wide", page_title="S&P 500 Screener & Chart", page_icon="📈")

st.title("🎯 S&P 500 Analyse-Cockpit")

left_col, right_col = st.columns([1, 1], gap="large")

# left side: SCREENER 
with left_col:
    st.subheader("1. Aktiensuche")
    
    with st.expander("⚙️ Filter Einstellungen", expanded=False):
        f_col1, f_col2 = st.columns(2)
        with f_col1:
            use_rsi = st.checkbox("RSI Filter", value=True)
            rsi_limit = st.slider("Max RSI", 10, 80, 30)
            use_vol = st.checkbox("Volumen ↑", value=True)
        with f_col2:
            use_ema = st.checkbox("EMA Filter", value=True)
            ema_tol = st.slider("EMA tol (%)", 0.5, 10.0, 2.0)

    if st.button("🚀 Scan Starten", use_container_width=True):
        tickers = get_sp500_tickers()
        with st.spinner('Scanne...'):
            st.session_state['scan_results'] = run_screener(tickers, use_rsi, rsi_limit, use_ema, ema_tol, use_vol)

    if 'scan_results' in st.session_state and not st.session_state['scan_results'].empty:
        results = st.session_state['scan_results']
        st.success(f"{len(results)} Treffer.")
        
        results = results.sort_values(by="_abs_dist", ascending=True)
        

        def color_ema_dist(val):
            color = '#ff4b4b' if val < 0 else '#3dd56d'
            return f'color: {color}'
        
   
        event = st.dataframe(
            results.drop(columns=["_abs_dist"]).style
                   .map(color_ema_dist, subset=['Abstand EMA50 (%)'])
                   .format({"Kurs ($)": "{:.2f}", "RSI": "{:.2f}", "Abstand EMA50 (%)": "{:+.2f}%"}),
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
        st.info("Starte den Scan, um Ergebnisse zu sehen.")
        selected_ticker = None

# right side: charts
with right_col:
    st.subheader("2. Detail-Chart")
    
    if selected_ticker:
        st.write(f"### Analyse: {selected_ticker}")
        
        
        chart_data = yf.download(selected_ticker, period="1y", progress=False)
        
    
        if isinstance(chart_data.columns, pd.MultiIndex):
            chart_data.columns = chart_data.columns.get_level_values(0)
        
        chart_data['EMA50'] = ta.ema(chart_data['Close'], length=50)
        
        # chart with ema
        st.line_chart(chart_data[['Close', 'EMA50']], color=["#29b5e8", "#ff4b4b"])
        
        # 2. RSI-chart
        chart_data['RSI'] = ta.rsi(chart_data['Close'], length=14)
        
        st.write("RSI Indikator")
        st.line_chart(chart_data[['RSI']], color=["#FFA500"])
        
        if not chart_data.empty:
            latest = chart_data.iloc[-1]
            m1, m2, m3 = st.columns(3)
            m1.metric("Kurs", f"{latest['Close']:.2f} $")
            m2.metric("RSI", f"{latest['RSI']:.2f}")
            
            vol_str = f"{latest['Volume'] / 1e6:.1f}M" if latest['Volume'] > 1e6 else f"{latest['Volume']:.0f}"
            m3.metric("Volumen", vol_str)
        
    else:
        st.empty()
        st.markdown(
            """
            <div style='text-align: center; padding: 100px; color: #666;'>
                👈 <b>Choose a stock</b><br>
                to see the chart and details
            </div>
            """, unsafe_allow_html=True
        )
