# 文件 4：journal_manager.py
# 作用：交易賬本讀寫與回溯存檔模塊
import os
import numpy as np
import pandas as pd

CSV_FILE = "monthly_trade_records.csv"

RECORD_COLUMNS = [
    "Date_MYT", "TREND_BIAS", "EMA20_1H", "ATR_1H", "SBR_TOP", "SBR_BOT", "RBS_TOP", "RBS_BOT",
    "SBR2_TOP", "SBR2_BOT", "RBS2_TOP", "RBS2_BOT", "PDH", "PDL", "PMH", "PML",
    "Signal", "Entry_MYT", "Entry_ET", "Exit_MYT", "Exit_ET", "Entry_Price", "Exit_Price", "SL", "TP", "PnL_Points", "Reason", "Result"
]

def load_journal():
    if not os.path.exists(CSV_FILE):
        df_init = pd.DataFrame(columns=RECORD_COLUMNS)
        df_init.to_csv(CSV_FILE, index=False, encoding="utf-8-sig")
        return df_init
    df_read = pd.read_csv(CSV_FILE)
    for col in RECORD_COLUMNS:
        if col not in df_read.columns: df_read[col] = np.nan
    return df_read

def append_to_journal(date_str, params, trades):
    df_cur = load_journal()
    if not df_cur.empty and date_str in df_cur["Date_MYT"].astype(str).values: return False, "当天记录已存在"

    rows = []
    base_info = {
        "Date_MYT": date_str, "TREND_BIAS": params["TREND_BIAS"], "EMA20_1H": params.get("EMA20_1H", 0.0), "ATR_1H": params.get("ATR_1H", 0.0),
        "SBR_TOP": params["SBR_TOP"], "SBR_BOT": params["SBR_BOT"], "RBS_TOP": params["RBS_TOP"], "RBS_BOT": params["RBS_BOT"],
        "SBR2_TOP": params["SBR2_TOP"], "SBR2_BOT": params["SBR2_BOT"], "RBS2_TOP": params["RBS2_TOP"], "RBS2_BOT": params["RBS2_BOT"],
        "PDH": params["PDH"], "PDL": params["PDL"], "PMH": params["PMH"], "PML": params["PML"]
    }

    if trades:
        for t in trades:
            r = dict(base_info); r.update(t); rows.append(r)
    else:
        empty_t = {
            "Signal": "NO_TRADE", "Entry_MYT": "-", "Entry_ET": "-", "Exit_MYT": "-", "Exit_ET": "-",
            "Entry_Price": 0.0, "Exit_Price": 0.0, "SL": 0.0, "TP": 0.0, "PnL_Points": 0.0, "Reason": "窗口期无2B/战区信号", "Result": "无"
        }
        r = dict(base_info); r.update(empty_t); rows.append(r)

    df_new = pd.DataFrame(rows)[[c for c in RECORD_COLUMNS if c in rows[0]]]
    df_new.to_csv(CSV_FILE, index=False, encoding="utf-8-sig", mode="a" if os.path.exists(CSV_FILE) else "w", header=not os.path.exists(CSV_FILE))
    return True, f"成功记录 {len(rows)} 条明细"
