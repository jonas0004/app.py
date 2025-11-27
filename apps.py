import streamlit as st
import pandas as pd
import yfinance as yf
import pandas_ta as ta

# 1. Seiten-Konfiguration (Titel, Layout, Icon)
st.set_page_config(
    page_title="S&P 500 Screener",
    page_icon="📈",
    layout="wide"  # Nutzt den ganzen Bildschirm
)

# 2. Funktion zum Laden der Daten (mit Cache für Speed)
@st.cache_data
def get_sp500_tickers():
    # Eine stabile, gepflegte Liste von einem Data-Provider auf GitHub
    url = "https://raw.githubusercontent.com/datasets/s-and-p-500-companies/master/data/constituents.csv"
    df = pd.read_csv(url)
    return df['Symbol'].tolist()


# 3. Screener-Logik
def run_screener(tickers, rsi_threshold, ema_dist_pct):
    candidates = []
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    # Wir nehmen zum Testen erstmal nur die ersten 50 Ticker, um Zeit zu sparen (für alle: tickers[:])
    for i, t in enumerate(tickers):
        try:
            status_text.text(f"Analysiere {t}...")
            progress_bar.progress((i + 1) / 50)
            
            # Daten laden (letzte 6 Monate reichen für EMA50)
            df = yf.download(t, period="6mo", progress=False)
            
            if len(df) < 50: continue
            
            # Indikatoren berechnen
            df['RSI'] = ta.rsi(df['Close'], length=14)
            df['EMA50'] = ta.ema(df['Close'], length=50)
            
            # Volumen-Trend (Durchschnitt letzte 3 Tage vs. davor)
            vol_recent = df['Volume'].iloc[-3:].mean()
            vol_prev = df['Volume'].iloc[-6:-3].mean()
            
            latest = df.iloc[-1]
            
            # Kriterien prüfen
            cond_rsi = latest['RSI'] < rsi_threshold
            cond_ema = abs(latest['Close'] - latest['EMA50']) / latest['EMA50'] < (ema_dist_pct / 100)
            cond_vol = vol_recent > vol_prev # Volumen steigt an
            
            if cond_rsi and cond_ema and cond_vol:
                candidates.append({
                    "Ticker": t,
                    "Kurs ($)": round(latest['Close'], 2),
                    "RSI": round(latest['RSI'], 2),
                    "Abstand EMA50 (%)": round(((latest['Close'] - latest['EMA50']) / latest['EMA50']) * 100, 2)
                })
        except Exception as e:
            continue
            
    status_text.empty()
    progress_bar.empty()
    return pd.DataFrame(candidates)

# --- FRONTEND AUFBAU ---

# Sidebar für Einstellungen
with st.sidebar:
    st.header("⚙️ Einstellungen")
    st.write("Passe deine Strategie an:")
    
    rsi_limit = st.slider("RSI Limit (Überverkauft)", 10, 50, 30)
    ema_tolerance = st.slider("Max. Abstand zu EMA50 (%)", 1.0, 10.0, 2.0)
    
    start_btn = st.button("🔍 Markt scannen", type="primary")
    
    st.markdown("---")
    st.info("Dieses Tool scannt den S&P 500 nach deiner Strategie.")

# Hauptbereich
st.title("📈 Pro Stock Screener")
st.markdown(f"**Strategie:** RSI < {rsi_limit} • Nähe EMA50 (< {ema_tolerance}%) • Steigendes Volumen")

if start_btn:
    with st.spinner('Lade Marktdaten...'):
        tickers = get_sp500_tickers()
        results = run_screener(tickers, rsi_limit, ema_tolerance)
    
    if not results.empty:
        # Metriken oben anzeigen
        col1, col2, col3 = st.columns(3)
        col1.metric("Gefundene Aktien", len(results))
        col2.metric("Niedrigster RSI", results['RSI'].min())
        col3.metric("Bester Einstieg", results.sort_values('RSI').iloc[0]['Ticker'])
        
        st.success(f"{len(results)} Kaufkandidaten gefunden!")
        
        # Interaktive Tabelle
        st.dataframe(
            results.style.background_gradient(subset=['RSI'], cmap='RdYlGn_r'),
            use_container_width=True,
            hide_index=True
        )
    else:
        st.warning("Keine Aktien gefunden, die diesen Kriterien entsprechen. Versuch, die Toleranz zu erhöhen.")

else:
    st.write("👈 Klicke links auf **'Markt scannen'**, um zu starten.")
