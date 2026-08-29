# 文件 2：data_fetcher.py
# 作用：QQQ 數據抓取引擎（Tiingo + YahooFinance 雙備份）
import datetime
from datetime import timedelta
import time
import pandas as pd
import pytz
import requests
import yfinance as yf

TIINGO_TOKEN = "bcffe3a5cf7eeef085e405cfa4a3e5691b976217"
TICKER = "QQQ"

tz_myt = pytz.timezone("Asia/Kuala_Lumpur")
tz_ny = pytz.timezone("America/New_York")

def fetch_raw_data_with_retry(period_5m="1mo", max_retries=3):
    df_1h, df_5m = None, None
    err_log = []
    now_myt = datetime.datetime.now(tz_myt)
    start_str = (now_myt - timedelta(days=60)).strftime("%Y-%m-%d")

    for attempt in range(max_retries):
        url = f"https://api.tiingo.com/iex/{TICKER}/prices?startDate={start_str}&resampleFreq=1hour&token={TIINGO_TOKEN}&columns=open,high,low,close,volume"
        try:
            resp = requests.get(url, headers={"Content-Type": "application/json"}, timeout=6)
            if resp.status_code == 200:
                data = resp.json()
                if data and isinstance(data, list) and len(data) >= 30:
                    df_t = pd.DataFrame(data)
                    df_t["date"] = pd.to_datetime(df_t["date"])
                    df_t.set_index("date", inplace=True)
                    df_t.rename(columns={"open": "Open", "high": "High", "low": "Low", "close": "Close", "volume": "Volume"}, inplace=True)
                    df_1h = df_t[["Open", "High", "Low", "Close", "Volume"]].sort_index()
                    df_1h.index = df_1h.index.tz_localize("UTC").tz_convert(tz_ny) if df_1h.index.tz is None else df_1h.index.tz_convert(tz_ny)
                    break
        except Exception:
            time.sleep(1)

    if df_1h is None:
        try:
            df_yf = yf.download(TICKER, period="2mo", interval="1h", prepost=True, progress=False)
            if df_yf is not None and not df_yf.empty:
                if isinstance(df_yf.columns, pd.MultiIndex):
                    df_yf.columns = df_yf.columns.get_level_values(0)
                df_1h = df_yf[["Open", "High", "Low", "Close", "Volume"]].dropna().copy()
                df_1h.index = df_1h.index.tz_localize("UTC").tz_convert(tz_ny) if df_1h.index.tz is None else df_1h.index.tz_convert(tz_ny)
        except Exception as e:
            err_log.append("YahooFinance 1H 失败: " + str(e))

    for attempt in range(max_retries):
        try:
            df_5m_raw = yf.download(TICKER, period=period_5m, interval="5m", prepost=True, progress=False)
            if df_5m_raw is not None and not df_5m_raw.empty:
                if isinstance(df_5m_raw.columns, pd.MultiIndex):
                    df_5m_raw.columns = df_5m_raw.columns.get_level_values(0)
                df_5m = df_5m_raw[["Open", "High", "Low", "Close", "Volume"]].dropna().copy()
                df_5m.index = df_5m.index.tz_localize("UTC").tz_convert(tz_ny) if df_5m.index.tz is None else df_5m.index.tz_convert(tz_ny)
                break
        except Exception as e:
            err_log.append("YahooFinance 5M 失败: " + str(e))
            time.sleep(1)

    return df_1h, df_5m, err_log
