import streamlit as st
import pandas as pd
import yfinance as yf
import pandas_ta as ta
import requests

# 1. Seiten-Konfiguration
st.set_page_config(
    page_title="S&P 500 Custom Screener",
    page_icon="🎛️",
    layout="wide"
)

# 2. Daten laden (GitHub-Quelle)
@st.cache_data
def get_sp500_tickers():
    try:
        url = "https://raw.githubusercontent.com/datasets/s-and-p-500-companies/master/data/constituents.csv"
        df = pd.read_csv(url)
        return df['Symbol'].tolist()
    except Exception as e:
        st.error(f"Fehler beim Laden der Ticker-Liste: {e}")
        return []

# 3. Der Screener mit flexiblen Filtern
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
            
            # Daten laden
            df = yf.download(t, period="6mo", progress=False, threads=False)
            if len(df) < 50: continue
            
            # Handling MultiIndex (passiert oft bei yfinance mass downloads)
            if isinstance(df.columns, pd.MultiIndex):
                close = df['Close'].iloc[:, 0]
                volume = df['Volume'].iloc[:, 0]
            else:
                close = df['Close']
                volume = df['Volume']

            # --- PRÜFUNGEN ---
            match_rsi = True
            match_ema = True
            match_vol = True
            
            # Werte für Anzeige
            current_rsi = 0.0
            dist_pct = 0.0
            
            # 1. RSI CHECK
            if use_rsi:
                rsi_series = ta.rsi(close, length=14)
                if rsi_series is None: continue
                current_rsi = rsi_series.iloc[-1]
                if current_rsi > rsi_thresh:
                    match_rsi = False
            
            # 2. EMA CHECK
            if use_ema:
                ema_series = ta.ema(close, length=50)
                if ema_series is None: continue
                current_ema = ema_series.iloc[-1]
                current_close = close.iloc[-1]
                
                dist_pct = abs(current_close - current_ema) / current_ema * 100
                if dist_pct > ema_tol:
                    match_ema = False
            
            # 3. VOLUME CHECK
            if use_vol:
                vol_recent = volume.iloc[-3:].mean()
                vol_prev = volume.iloc[-6:-3].mean()
                if vol_recent <= vol_prev:
                    match_vol = False
            
            # Wenn ALLE aktiven Filter passen -> hinzufügen
            if match_rsi and match_ema and match_vol:
                # Werte berechnen falls sie oben nicht berechnet wurden (weil Filter aus war)
                final_close = close.iloc[-1]
                
                # RSI berechnen für Anzeige, auch wenn Filter aus ist
                if not use_rsi:
                    rsi_series = ta.rsi(close, length=14)
                    current_rsi = rsi_series.iloc[-1] if rsi_series is not None else 0
                    
                # EMA Abstand berechnen für Anzeige, auch wenn Filter aus ist
                if not use_ema:
                    ema_series = ta.ema(close, length=50)
                    if ema_series is not None:
                        c_ema = ema_series.iloc[-1]
                        dist_pct = abs(final_close - c_ema) / c_ema * 100
                
                candidates.append({
                    "Ticker": t,
                    "Kurs ($)": round(final_close, 2),
                    "RSI": round(current_rsi, 2),
                    "Abstand EMA50 (%)": round(dist_pct, 2),
                })

        except Exception:
            continue
            
    status_text.empty()
    progress_bar.empty()
    return pd.DataFrame(candidates)

# --- FRONTEND ---

with st.sidebar:
    st.header("⚙️ Filter Einstellungen")
    
    # RSI Filter
    st.subheader("1. RSI Filter")
    use_rsi = st.checkbox("RSI Filter aktivieren", value=True)
    rsi_limit = st.slider("RSI Limit", 10, 80, 30, disabled=not use_rsi)
    
    st.divider()
    
    # EMA Filter
    st.subheader("2. EMA Filter")
    use_ema = st.checkbox("EMA 50 Nähe aktivieren", value=True)
    ema_tolerance = st.slider("Max. Abstand (%)", 0.5, 10.0, 2.0, step=0.5, disabled=not use_ema)
    
    st.divider()
    
    # Volumen Filter
    st.subheader("3. Volumen Filter")
    use_vol = st.checkbox("Steigendes Volumen", value=True)
    
    st.divider()
    
    start_btn = st.button("🚀 Scan Starten", type="primary")

# Hauptbereich
st.title("🎛️ S&P 500 Custom Screener")

# Anzeige der aktiven Strategie
active_filters = []
if use_rsi: active_filters.append(f"RSI < {rsi_limit}")
if use_ema: active_filters.append(f"EMA-Nähe < {ema_tolerance}%")
if use_vol: active_filters.append("Steigendes Volumen")

if not active_filters:
    st.warning("⚠️ Achtung: Keine Filter ausgewählt. Das wird ALLE 500 Aktien anzeigen.")
else:
    st.markdown(f"**Aktive Strategie:** {' • '.join(active_filters)}")

if start_btn:
    tickers = get_sp500_tickers()
    if tickers:
        with st.spinner('Scanne Markt...'):
            results = run_screener(tickers, use_rsi, rsi_limit, use_ema, ema_tolerance, use_vol)
        
        if not results.empty:
            st.success(f"{len(results)} Treffer gefunden!")
            st.dataframe(results, use_container_width=True, hide_index=True)
        else:
            st.warning("Keine Aktien gefunden.")
