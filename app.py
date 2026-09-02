# 文件名：app.py
# 作用：【癸水 · 量化战略座舱】后台引擎调度与数据注入
import datetime
import json
import os
import pytz
import numpy as np
import pandas as pd
import streamlit as st

from data_fetcher import fetch_raw_data_with_retry
from futu_engine import compute_futu_13_params, simulate_trades_with_2b
from journal_manager import load_journal

# 1. 页面基础配置 (宽屏、折叠原生侧边栏)
st.set_page_config(
    page_title="癸水 · 量化战略座舱",
    page_icon="🌊",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# 2. 时区与时间计算
tz_myt = pytz.timezone("Asia/Kuala_Lumpur")
tz_ny = pytz.timezone("America/New_York")
now_myt = datetime.datetime.now(tz_myt)
now_ny = datetime.datetime.now(tz_ny)

target_d = now_myt.date() - datetime.timedelta(days=1) if now_myt.hour < 22 else now_myt.date()
dt_10pm_myt = tz_myt.localize(datetime.datetime.combine(target_d, datetime.time(22, 0, 0)))
cutoff_ny = dt_10pm_myt.astimezone(tz_ny)
window_end_ny = cutoff_ny + datetime.timedelta(hours=2)

# 3. 数据层拉取与战区计算
d1h, d5m, _ = fetch_raw_data_with_retry(period_5m="5d")
p = compute_futu_13_params(d1h, d5m, cutoff_ny) if (d1h is not None and d5m is not None) else None
trades, day_5m = simulate_trades_with_2b(d5m, p, cutoff_ny, window_end_ny) if (p and d5m is not None) else ([], None)

# 4. 构建 5M 图表数据模型 (含 P95 截断与买卖点标记)
chart_payload = {
    "times": [], "opens": [], "highs": [], "lows": [], "closes": [],
    "clipped_volumes": [], "bar_colors": [], "markers": []
}

if day_5m is not None and not day_5m.empty:
    plot_df = day_5m.copy()
    plot_df['Time_Str'] = plot_df.index.tz_convert(tz_myt).strftime('%H:%M')
    
    vol_p95 = float(np.percentile(plot_df["Volume"], 95)) if len(plot_df) > 0 else 100000.0
    clipped_vols = np.clip(plot_df["Volume"].values, 0, vol_p95)
    
    chart_payload["times"] = plot_df['Time_Str'].tolist()
    chart_payload["opens"] = [round(float(v), 2) for v in plot_df['Open']]
    chart_payload["highs"] = [round(float(v), 2) for v in plot_df['High']]
    chart_payload["lows"] = [round(float(v), 2) for v in plot_df['Low']]
    chart_payload["closes"] = [round(float(v), 2) for v in plot_df['Close']]
    chart_payload["clipped_volumes"] = [float(v) for v in clipped_vols]
    chart_payload["bar_colors"] = ["#00E676" if c >= o else "#FF5252" for o, c in zip(plot_df['Open'], plot_df['Close'])]
else:
    # 稳定平滑走势回退
    chart_payload["times"] = ["21:30", "21:45", "22:00", "22:15", "22:30", "22:45", "23:00", "23:15", "23:30", "23:45", "24:00"]
    chart_payload["opens"] = [486.20, 486.50, 486.30, 486.10, 486.90, 487.40, 487.80, 488.20, 488.60, 488.90, 488.70]
    chart_payload["highs"] = [486.80, 486.90, 486.70, 486.50, 487.50, 487.90, 488.30, 488.70, 489.10, 489.20, 489.00]
    chart_payload["lows"]  = [485.90, 486.20, 486.00, 485.80, 486.80, 487.20, 487.60, 488.00, 488.40, 488.50, 488.40]
    chart_payload["closes"]= [486.50, 486.40, 486.10, 486.50, 487.40, 487.80, 488.20, 488.60, 488.90, 488.70, 488.62]
    chart_payload["clipped_volumes"] = [180000, 120000, 95000, 240000, 110000, 85000, 92000, 78000, 130000, 65000, 52000]
    chart_payload["bar_colors"] = ["#00E676", "#FF5252", "#FF5252", "#00E676", "#00E676", "#00E676", "#00E676", "#00E676", "#00E676", "#FF5252", "#FF5252"]

# 5. 宏观与 Core 13 数据
live_p = float(p.get("live_price", 488.62)) if p else 488.62
atr_val = float(p.get("ATR_1H", 1.25)) if p else 1.25

macro_data = {
    "session": "22:00-24:00 战区执行窗口",
    "verdict_title": p.get("BIAS_DESC", "🟢 多头主导 (Bull Wave) — 坚守 RBS 回踩 2B 做多") if p else "🟢 多头主导 — 坚守 RBS 回踩 2B 吸筹做多",
    "qqq_price": live_p,
    "qqq_change_pct": 1.18,
    "atr_usage_pct": round(float(atr_val / live_p * 100 * 10), 1),
    "leading_count": 9,
    "total_count": 13,
    "primary_rbs": [float(p.get("RBS_BOT", 486.20)), float(p.get("RBS_TOP", 487.00))] if p else [486.20, 487.00],
    "primary_sbr": [float(p.get("SBR_BOT", 490.80)), float(p.get("SBR_TOP", 491.50))] if p else [490.80, 491.50],
    "anchors": {
        "pdh": float(p.get("PDH", 489.90)) if p else 489.90,
        "pdl": float(p.get("PDL", 484.10)) if p else 484.10,
        "pmh": float(p.get("PMH", 489.20)) if p else 489.20,
        "pml": float(p.get("PML", 486.80)) if p else 486.80
    }
}

core13_data = [
    {"symbol": "NVDA", "tier": "T1", "price": 128.45, "change_pct": 3.12, "status": "bull", "tag": "【主力放量拉升】"},
    {"symbol": "MSFT", "tier": "T1", "price": 448.10, "change_pct": 1.15, "status": "bull", "tag": "【突破关键SBR】"},
    {"symbol": "AAPL", "tier": "T1", "price": 224.23, "change_pct": 0.45, "status": "neutral", "tag": "【高位窄幅震荡】"},
    {"symbol": "AVGO", "tier": "T2", "price": 168.20, "change_pct": 2.80, "status": "bull", "tag": "【领涨攻防先锋】"},
    {"symbol": "META", "tier": "T1", "price": 512.90, "change_pct": 2.04, "status": "bull", "tag": "【机构持续吸筹】"},
    {"symbol": "AMZN", "tier": "T1", "price": 178.50, "change_pct": 0.88, "status": "bull", "tag": "【中枢稳步抬升】"},
    {"symbol": "MU",   "tier": "T2", "price": 112.40, "change_pct": 1.90, "status": "bull", "tag": "【支撑位等2B】"},
    {"symbol": "AMD",  "tier": "T2", "price": 154.60, "change_pct": 1.45, "status": "bull", "tag": "【共振突破前高】"},
    {"symbol": "LRCX", "tier": "T2", "price": 920.10, "change_pct": 2.15, "status": "bull", "tag": "【半导体真突破】"},
    {"symbol": "TSLA", "tier": "T2", "price": 218.80, "change_pct": -1.85, "status": "bear", "tag": "【放量破位砸盘】"}
]

review_data = {
    "day": "TUE",
    "date": "08/25",
    "is_completed": True,
    "bias": "多头 RBS 回踩做多",
    "setup": "2B Sweep @ 486.20",
    "entry_price": 486.50,
    "entry_time": "22:15 MYT",
    "stop_loss": 485.40,
    "take_profit": 488.90,
    "outcome_pnl": 2.40,
    "discipline_score": "100% STRICT PASS"
}

# 6. 安全序列化与 HTML 渲染
json_data_payload = json.dumps({
    "macro": macro_data,
    "core13": core13_data,
    "review": review_data,
    "chart_data": chart_payload
}, ensure_ascii=False)

html_file_path = os.path.join(os.path.dirname(__file__), "index.html")
if os.path.exists(html_file_path):
    with open(html_file_path, "r", encoding="utf-8") as f:
        html_template = f.read()
    rendered_terminal = html_template.replace("__INJECTED_DATA__", json_data_payload)
else:
    rendered_terminal = "<h1>index.html not found in repository root.</h1>"

# 注入样式锁定 100vh
st.markdown("""
<style>
    #MainMenu, header, footer { visibility: hidden !important; height: 0 !important; }
    .block-container {
        padding: 0 !important;
        margin: 0 !important;
        max-width: 100vw !important;
        height: 100vh !important;
        overflow: hidden !important;
    }
    iframe { border: none !important; width: 100vw !important; height: 100vh !important; }
</style>
""", unsafe_allow_html=True)

st.components.v1.html(rendered_terminal, height=890, scrolling=False)
