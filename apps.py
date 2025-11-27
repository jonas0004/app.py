import streamlit as st
import pandas as pd
import yfinance as yf
import pandas_ta as ta
import requests

# 1. Seiten-Konfiguration
st.set_page_config(
    page_title="S&P 500 Screener Pro",
    page_icon="🚀",
    layout="wide"
)

# 2. Daten laden (Von GitHub statt Wikipedia -> Viel stabiler)
@st.cache_data
def get_sp500_tickers():
    try:
        url = "https://raw.githubusercontent.com/datasets/s-and-p-500-companies/master/data/constituents.csv"
        df = pd.read_csv(url)
        return df['Symbol'].tolist()
    except Exception as e:
        st.error(f"Fehler beim Laden der Ticker-Liste: {e}")
        return []

# 3. Der eigentliche Screener
def run_screener(tickers, rsi_threshold, ema_dist_pct):
    candidates = []
    
    # Progress Bar Setup
    progress_bar = st.progress(0)
    status_text = st.empty()
    total_tickers = len(tickers)
    
    # Loop durch ALLE Ticker
    for i, t in enumerate(tickers):
        try:
            # Update Progress (nur alle 5 Ticker, spart Rechenzeit im UI)
            if i % 5 == 0:
                progress_bar.progress((i + 1) / total_tickers)
                status_text.text(f"Analysiere {i+1} von {total_tickers}: {t}...")
            
            # Daten laden (letzte 6 Monate)
            # threads=False verhindert manchmal API-Probleme bei Massenabfragen
            df = yf.download(t, period="6mo", progress=False, threads=False)
            
            # Check ob genug Daten da sind
            if len(df) < 50: continue
            
            # --- INDIKATOREN BERECHNEN ---
            
            # 1. RSI (14)
            # Wir nutzen 'Close' - bei Multi-Index Dataframes von yfinance sicherstellen, dass es 1D ist
            if isinstance(df.columns, pd.MultiIndex):
                close_series = df['Close'].iloc[:, 0]
                volume_series = df['Volume'].iloc[:, 0]
            else:
                close_series = df['Close']
                volume_series = df['Volume']

            rsi_val = ta.rsi(close_series, length=14)
            if rsi_val is None: continue # Falls Berechnung fehlschlägt
            
            # 2. EMA (50)
            ema_val = ta.ema(close_series, length=50)
            if ema_val is None: continue

            # 3. Volumen Trend (Avg 3 Tage vs Avg davor)
            vol_recent = volume_series.iloc[-3:].mean()
            vol_prev = volume_series.iloc[-6:-3].mean()
            
            # Letzte Werte holen
            current_close = close_series.iloc[-1]
            current_rsi = rsi_val.iloc[-1]
            current_ema = ema_val.iloc[-1]
            
            # --- FILTER LOGIK ---
            
            # Kriterium A: RSI im Keller?
            cond_rsi = current_rsi < rsi_threshold
            
            # Kriterium B: Preis nah am 50er EMA?
            # Berechnung: Wie viel % ist der Preis vom EMA entfernt?
            dist_pct = abs(current_close - current_ema) / current_ema * 100
            cond_ema = dist_pct < ema_dist_pct
            
            # Kriterium C: Volumen steigt?
            cond_vol = vol_recent > vol_prev
            
            if cond_rsi and cond_ema and cond_vol:
                candidates.append({
                    "Ticker": t,
                    "Kurs ($)": round(current_close, 2),
                    "RSI": round(current_rsi, 2),
                    "Abstand EMA50 (%)": round(dist_pct, 2),
                    "Volumen-Trend": "Steigend 📈"
                })
                
        except Exception as e:
            # Fehler bei einzelner Aktie ignorieren wir, damit der Scan weiterläuft
            continue
            
    # Aufräumen
    status_text.empty()
    progress_bar.empty()
    
    return pd.DataFrame(candidates)

# --- FRONTEND ---

with st.sidebar:
    st.header("⚙️ Scanner Einstellungen")
    
    rsi_limit = st.slider("RSI Limit (Maximal)", 10, 50, 30, help="Alles unter diesem Wert gilt als überverkauft.")
    ema_tolerance = st.slider("Max. Abstand zu EMA50 (%)", 0.5, 5.0, 2.0, step=0.1, help="Wie nah muss der Kurs am 50-Tage-Durchschnitt sein?")
    
    st.markdown("---")
    start_btn = st.button("🚀 Scan Starten", type="primary")
    st.caption("Hinweis: Der Scan von 500 Aktien kann 2-4 Minuten dauern.")

st.title("📈 S&P 500 Opportunity Screener")
st.markdown(f"**Aktuelle Strategie:** Suche Aktien mit RSI < **{rsi_limit}**, die weniger als **{ema_tolerance}%** vom 50er EMA entfernt sind und **steigendes Volumen** zeigen.")

if start_btn:
    tickers = get_sp500_tickers()
    
    if not tickers:
        st.error("Konnte keine Ticker laden. Prüfe deine Internetverbindung.")
    else:
        with st.spinner(f'Scanne {len(tickers)} Aktien im S&P 500... Bitte warten...'):
            results = run_screener(tickers, rsi_limit, ema_tolerance)
        
        if not results.empty:
            st.success(f"Fertig! {len(results)} Treffer gefunden.")
            
            # Ergebnisse Sortieren nach RSI (am stärksten überverkauft zuerst)
            results = results.sort_values(by="RSI", ascending=True)
            
            st.dataframe(
                results.style.background_gradient(subset=['RSI'], cmap='RdYlGn_r'),
                use_container_width=True,
                hide_index=True
            )
        else:
            st.warning("Keine Treffer mit diesen strengen Kriterien. Versuch mal, den RSI auf 40 zu erhöhen oder den EMA-Abstand zu vergrößern.")

