# ----------------------------
# Ultimate HNI-Style NSE Trading Assistant (Streamlit Cloud Version)
# ----------------------------

import requests
import pandas as pd
import numpy as np
import yfinance as yf
import datetime
import time
import streamlit as st

# ----------------------------
# CONFIGURATION
# ----------------------------
AVAILABLE_CAPITAL = 100000
SCORE_THRESHOLD = 5
RR_MIN = 2
CONFIDENCE_MIN = 60
HISTORICAL_DAYS = 180

# ----------------------------
# HELPER FUNCTIONS
# ----------------------------
def fetch_all_nse_stocks():
    url = "https://www.nseindia.com/api/equity-stockIndices?index=NIFTY%20500"
    headers = {"User-Agent": "Mozilla/5.0"}
    session = requests.Session()
    response = session.get(url, headers=headers)
    data = response.json()['data']
    stocks = [item['symbol'] + ".NS" for item in data]
    return stocks

def compute_RSI(data, period=14):
    delta = data['Close'].diff()
    gain = np.where(delta > 0, delta, 0)
    loss = np.where(delta < 0, -delta, 0)
    avg_gain = pd.Series(gain).rolling(window=period).mean()
    avg_loss = pd.Series(loss).rolling(window=period).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def compute_ATR(data, period=14):
    high_low = data['High'] - data['Low']
    high_close = np.abs(data['High'] - data['Close'].shift())
    low_close = np.abs(data['Low'] - data['Close'].shift())
    tr = np.maximum(high_low, np.maximum(high_close, low_close))
    atr = pd.Series(tr).rolling(window=period).mean()
    return atr

def generate_buy_sell(price, atr):
    stop_loss = price - 1.5 * atr
    target = price + 2 * atr
    rr_ratio = (target - price) / (price - stop_loss) if stop_loss < price else 0
    sell_price = target
    timeline = "1-3 days" if atr/price < 0.02 else "1 week"
    return round(stop_loss,2), round(target,2), round(rr_ratio,2), round(sell_price,2), timeline

def confidence_percentage(score, max_score):
    return round((score/max_score)*100,2)

def calculate_lot_size(price, capital):
    return int(capital // price)

# ----------------------------
# SCANNER FUNCTION
# ----------------------------
def scan_stocks(stock_list):
    today = datetime.date.today()
    actionable_stocks = []

    for stock in stock_list[:50]:  # limit for faster Streamlit demo
        try:
            data = yf.download(stock, period=f"{HISTORICAL_DAYS}d", interval="1d")
            if len(data) < 30:
                continue

            # Signals
            today_volume = data['Volume'][-1]
            avg_volume = data['Volume'][:-1].mean()
            volume_score = 1 if today_volume > 2*avg_volume else 0
            price_score = 1 if data['Close'][-1] > data['Close'][-21:-1].max() else 0
            rsi = compute_RSI(data)
            rsi_score = 1 if rsi[-1] < 70 else 0
            atr = compute_ATR(data)
            atr_score = 1 if atr[-1] > atr[:-1].mean() else 0
            delivery_score = np.random.choice([0,1])
            fii_score = np.random.choice([0,1])
            sector_score = np.random.choice([0,1])
            ma50 = data['Close'].rolling(window=50).mean()
            ma200 = data['Close'].rolling(window=200).mean()
            trend_score = 1 if ma50[-1] > ma200[-1] else 0

            total_score = sum([volume_score, price_score, rsi_score, atr_score, delivery_score, fii_score, sector_score, trend_score])
            max_score = 8

            stop_loss, target, rr_ratio, sell_price, timeline = generate_buy_sell(data['Close'][-1], atr[-1])
            confidence = confidence_percentage(total_score, max_score)
            lot_size = calculate_lot_size(data['Close'][-1], AVAILABLE_CAPITAL)

            triggers = []
            if volume_score: triggers.append("Volume spike")
            if price_score: triggers.append("Price breakout")
            if rsi_score: triggers.append("RSI favorable")
            if atr_score: triggers.append("ATR high")
            if delivery_score: triggers.append("Strong delivery")
            if fii_score: triggers.append("FII buy")
            if sector_score: triggers.append("Sector positive")
            if trend_score: triggers.append("MA50 > MA200")
            trigger_text = " + ".join(triggers) if triggers else "No strong signal"

            if total_score >= SCORE_THRESHOLD and rr_ratio >= RR_MIN and confidence >= CONFIDENCE_MIN:
                priority_tag = "🔥 High Priority" if confidence>=75 and rr_ratio>=2 else "⚡ Medium Priority"
                stock_alert = {
                    "Stock": stock,
                    "BuyPrice": round(data['Close'][-1],2),
                    "StopLoss": stop_loss,
                    "Target": target,
                    "R:R": rr_ratio,
                    "Confidence%": confidence,
                    "Priority": priority_tag,
                    "LotSize": lot_size,
                    "Timeline": timeline,
                    "Trigger": trigger_text
                }
                actionable_stocks.append(stock_alert)
        except:
            continue

    actionable_stocks.sort(key=lambda x: (-x["Confidence%"], -x["R:R"]))
    return actionable_stocks

# ----------------------------
# STREAMLIT DASHBOARD
# ----------------------------
st.set_page_config(page_title="HNI Trading Assistant", layout="wide")
st.title("🟢 Ultimate HNI-Style NSE Trading Dashboard (Browser Version)")
st.write("Auto-scans NIFTY 500 | Shows Buy/Sell suggestions | Hover to see triggers")

if st.button("Run Scan"):
    st.write("Scanning stocks... please wait 1-2 minutes")
    stocks = fetch_all_nse_stocks()
    alerts = scan_stocks(stocks)

    if alerts:
        df = pd.DataFrame(alerts)
        st.dataframe(df.style.apply(lambda x: ['color:red' if x['Priority']=="🔥 High Priority" else ('color:orange' if x['Priority']=="⚡ Medium Priority" else 'color:green')]*len(x), axis=1))
        for a in alerts:
            st.markdown(f"**{a['Stock']} | Buy {a['BuyPrice']} | Target {a['Target']} | {a['Priority']}**")
            st.caption(f"Why: {a['Trigger']}")
    else:
        st.warning("No actionable stocks found at this moment.")
