
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.io as pio
import requests
import os
import csv
from datetime import datetime, timedelta
from streamlit_autorefresh import st_autorefresh
from email.mime.text import MIMEText
import smtplib

st.set_page_config(layout="wide")

# Email Alert Function
def send_email_alert(subject, body, to_email, from_email, app_password):
    try:
        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = from_email
        msg["To"] = to_email
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(from_email, app_password)
            server.send_message(msg)
        return True
    except Exception as e:
        st.error(f"Email send failed: {e}")
        return False

# Save chart as image
def save_chart_as_image(fig, symbol, level):
    filename = f"{symbol}_{level}_alert.png"
    pio.write_image(fig, filename, format="png", width=1200, height=800)

# Log event to CSV
def log_event(event_type, price, support, resistance, symbol):
    file_path = "event_log.csv"
    file_exists = os.path.isfile(file_path)
    with open(file_path, "a", newline="") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["Timestamp", "Symbol", "Event", "Price", "Support", "Resistance"])
        writer.writerow([
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            symbol, event_type, f"{price:.2f}", f"{support:.2f}", f"{resistance:.2f}"
        ])

# Save data snapshot
def save_data_snapshot(df, symbol):
    filename = f"{symbol}_snapshot.csv"
    df.tail(20).to_csv(filename, index=False)

# Auto-refresh
refresh_seconds = st.sidebar.selectbox("🔁 Auto-Refresh Interval (seconds)", [15, 30, 60, 120, 300], index=2)
st_autorefresh(interval=refresh_seconds * 1000, key="crypto_refresh")

st.markdown("## 📊 Crypto Support & Resistance Analyzer")

# Email setup
st.sidebar.markdown("### 📧 Email Alert Settings")
enable_email = st.sidebar.checkbox("Enable Email Alerts", value=False)
to_email = st.sidebar.text_input("Your Email (To)", "")
from_email = st.sidebar.text_input("Sender Gmail (From)", "")
app_password = st.sidebar.text_input("App Password", type="password")

if st.sidebar.button("📨 Send Test Email"):
    if send_email_alert("Test Crypto Alert", "This is a test alert from the Streamlit app.", to_email, from_email, app_password):
        st.sidebar.success("Test email sent!")

col1, col2 = st.columns([1, 9])
with col1:
    if st.button("❌ Exit App"):
        os._exit(0)

# Load symbols
symbol_df = pd.read_excel("crypto_symbol.xlsx")
#symbol_df = pd.read_excel("D:/OneDrive/Documents/shares/CRYPTODATA/crypto_symbol.xlsx")
symbols = symbol_df["symbol"].dropna().unique().tolist()
symbol = st.selectbox("Select Crypto Symbol", symbols)

api_key = "cn2AZpCgLd44PYFPCHVkmqZouGukDFXL"
interval = st.selectbox("Select Interval", ["5min", "15min", "30min", "1hour", "4hour", "1day"], index=3)

# Fetch data
url = f"https://financialmodelingprep.com/api/v3/historical-chart/{interval}/{symbol}?apikey={api_key}"
response = requests.get(url)

if response.status_code == 200:
    raw_data = response.json()
    if isinstance(raw_data, list) and len(raw_data) > 0:
        df = pd.DataFrame(raw_data)
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date")

        
        # 📅 Date pickers for custom range
        st.markdown("### 📅 Select Date Range")
        from_date = st.date_input("From Date", value=datetime.now().date() - timedelta(days=7))
        to_date = st.date_input("To Date", value=datetime.now().date())

        from_datetime = pd.to_datetime(from_date)
        to_datetime = pd.to_datetime(to_date) + pd.Timedelta(days=1)

        if from_datetime < to_datetime:
            df = df[(df["date"] >= from_datetime) & (df["date"] < to_datetime)]
        else:
            st.warning("⚠️ 'From Date' must be earlier than 'To Date'. Showing default range instead.")
            now = pd.to_datetime("now")
            if interval in ["1hour", "4hour"]:
                df = df[df["date"] >= (now - timedelta(days=7))]
            elif interval == "1day":
                df = df[df["date"] >= (now - timedelta(days=10))]


        support = df["low"].min()
        resistance = df["high"].max()
        st.markdown(f"### 🧭 Current Levels for **{symbol}**")
        st.metric("🔻 Support", f"{support:.2f}")
        st.metric("🔺 Resistance", f"{resistance:.2f}")

        diff = resistance - support
        fib_levels = {
            "Fib 0.0": resistance,
            "Fib 0.382": resistance - 0.382 * diff,
            "Fib 0.618": resistance - 0.618 * diff,
            "Fib 1.0": support,
        }
        pivot = (support + resistance + df["close"].iloc[-1]) / 3

        show_fib = st.checkbox("Show Fibonacci Levels", value=True)
        show_pivot = st.checkbox("Show Pivot Level", value=True)

        fig = go.Figure(data=[go.Candlestick(
            x=df["date"], open=df["open"], high=df["high"],
            low=df["low"], close=df["close"], name="Candlestick"
        )])
        fig.add_hline(y=support, line=dict(color="red", dash="dot"), annotation_text="Support", annotation_position="top left")
        fig.add_hline(y=resistance, line=dict(color="green", dash="dot"), annotation_text="Resistance", annotation_position="top left")

        if show_fib:
            for name, level in fib_levels.items():
                fig.add_hline(y=level, line=dict(color="blue", dash="dash"), annotation_text=name, annotation_position="top right")
        if show_pivot:
            fig.add_hline(y=pivot, line=dict(color="orange", dash="dash"), annotation_text="Pivot", annotation_position="top right")

        fig.update_layout(height=800, title=f"{symbol} - Support & Resistance + Fib + Pivot", yaxis_title="Price", xaxis_title="Time")
        st.plotly_chart(fig, use_container_width=True)

        latest_close = df["close"].iloc[-1]
        threshold = 0.001 * latest_close

        if abs(latest_close - support) <= threshold:
            st.toast(f"⚠️ Price is near Support Level ({support:.2f})", icon="⚠️")
            save_chart_as_image(fig, symbol, "support")
            log_event("Support", latest_close, support, resistance, symbol)
            save_data_snapshot(df, symbol)
            if enable_email:
                send_email_alert("Support Alert", f"{symbol} is near support at {support:.2f}. Current: {latest_close:.2f}", to_email, from_email, app_password)

        if abs(latest_close - resistance) <= threshold:
            st.toast(f"🚨 Price is near Resistance Level ({resistance:.2f})", icon="🚨")
            save_chart_as_image(fig, symbol, "resistance")
            log_event("Resistance", latest_close, support, resistance, symbol)
            save_data_snapshot(df, symbol)
            if enable_email:
                send_email_alert("Resistance Alert", f"{symbol} is near resistance at {resistance:.2f}. Current: {latest_close:.2f}", to_email, from_email, app_password)
    else:
        st.error("No data returned.")
else:
    st.error("❌ Failed to fetch data from API.")
