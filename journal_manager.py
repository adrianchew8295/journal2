# 文件名：journal_manager.py
# 作用：月历账本存储与管理模块 (支持强制覆盖与全量回溯)
import os
import numpy as np
import pandas as pd

CSV_FILE = "monthly_trade_records.csv"
RECORD_COLUMNS = [
    "Date_MYT", "TREND_BIAS", "EMA20_1H", "ATR_1H", 
    "SBR_TOP", "SBR_BOT", "RBS_TOP", "RBS_BOT",
    "SBR2_TOP", "SBR2_BOT", "RBS2_TOP", "RBS2_BOT", 
    "PDH", "PDL", "PMH", "PML",
    "Signal", "Entry_MYT", "Entry_ET", "Exit_MYT", "Exit_ET", 
    "Entry_Price", "Exit_Price", "SL", "TP", "PnL_Points", 
    "Reason", "Result"
]

def load_journal():
    if not os.path.exists(CSV_FILE):
        df_init = pd.DataFrame(columns=RECORD_COLUMNS)
        df_init.to_csv(CSV_FILE, index=False, encoding="utf-8-sig")
        return df_init
    df_read = pd.read_csv(CSV_FILE)
    for col in RECORD_COLUMNS:
        if col not in df_read.columns:
            df_read[col] = np.nan
    return df_read

def append_to_journal(date_str, params, trades, overwrite=False):
    """
    追加或覆盖记录到月历账本
    """
    df_cur = load_journal()
    
    if overwrite and not df_cur.empty:
        df_cur = df_cur[df_cur["Date_MYT"].astype(str) != str(date_str)].copy()
    elif not df_cur.empty and str(date_str) in df_cur["Date_MYT"].astype(str).values:
        return False, "当天记录已存在"

    rows = []
    base_info = {
        "Date_MYT": date_str,
        "TREND_BIAS": params["TREND_BIAS"],
        "EMA20_1H": params.get("EMA20_1H", 0.0),
        "ATR_1H": params.get("ATR_1H", 0.0),
        "SBR_TOP": params["SBR_TOP"], "SBR_BOT": params["SBR_BOT"],
        "RBS_TOP": params["RBS_TOP"], "RBS_BOT": params["RBS_BOT"],
        "SBR2_TOP": params["SBR2_TOP"], "SBR2_BOT": params["SBR2_BOT"],
        "RBS2_TOP": params["RBS2_TOP"], "RBS2_BOT": params["RBS2_BOT"],
        "PDH": params["PDH"], "PDL": params["PDL"],
        "PMH": params["PMH"], "PML": params["PML"]
    }

    if trades:
        for t in trades:
            r = dict(base_info)
            r.update(t)
            rows.append(r)
    else:
        empty_t = {
            "Signal": "NO_TRADE", "Entry_MYT": "-", "Entry_ET": "-",
            "Exit_MYT": "-", "Exit_ET": "-", "Entry_Price": 0.0,
            "Exit_Price": 0.0, "SL": 0.0, "TP": 0.0, "PnL_Points": 0.0,
            "Reason": "窗口期无2B/战区信号 (或 Bias=0 纪律空仓)", "Result": "无"
        }
        r = dict(base_info)
        r.update(empty_t)
        rows.append(r)

    df_new = pd.DataFrame(rows)[[c for c in RECORD_COLUMNS if c in rows[0]]]
    df_combined = pd.concat([df_cur, df_new], ignore_index=True) if not df_cur.empty else df_new
    df_combined.to_csv(CSV_FILE, index=False, encoding="utf-8-sig")
    return True, f"成功记录 {date_str} 数据"
