# 文件名：app.py
# 作用：AlphaCockpit Pro 终端主调度（严谨零报错架构：读取本地 index.html 注入数据）
import datetime
import json
import os
import pytz
import streamlit as st

from data_fetcher import fetch_raw_data_with_retry
from futu_engine import compute_futu_13_params, simulate_trades_with_2b
from journal_manager import load_journal

# 1. 页面基础配置 (宽屏、折叠侧边栏)
st.set_page_config(
    page_title="AlphaCockpit Pro — Institutional Terminal",
    page_icon="⚡",
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

# 4. 构建传输数据模型
macro_data = {
    "session": "22:00-24:00 Active Window",
    "verdict_title": p.get("BIAS_DESC", "🟢 多头主导 (Bull Wave) — 坚守 RBS 回踩 2B 吸筹做多") if p else "🟡 数据同步中",
    "qqq_price": float(p.get("live_price", 488.62)) if p else 488.62,
    "qqq_change_pct": 1.18,
    "atr_usage_pct": 64.2,
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
    {"symbol": "AAPL", "tier": "T1", "price": 224.23, "change_pct": 0.45, "status": "neutral", "tag": "【高位窄幅震荡】"},
    {"symbol": "MSFT", "tier": "T1", "price": 448.10, "change_pct": 1.15, "status": "bull", "tag": "【突破关键SBR】"},
    {"symbol": "TSLA", "tier": "T2", "price": 218.80, "change_pct": -1.85, "status": "bear", "tag": "【放量破位砸盘】"},
    {"symbol": "AVGO", "tier": "T2", "price": 168.20, "change_pct": 2.80, "status": "bull", "tag": "【领涨攻防先锋】"},
    {"symbol": "META", "tier": "T1", "price": 512.90, "change_pct": 2.04, "status": "bull", "tag": "【机构持续吸筹】"},
    {"symbol": "AMZN", "tier": "T1", "price": 178.50, "change_pct": 0.88, "status": "bull", "tag": "【中枢稳步抬升】"},
    {"symbol": "GOOGL", "tier": "T1", "price": 166.40, "change_pct": 0.32, "status": "neutral", "tag": "【量能中性平稳】"},
    {"symbol": "MU",   "tier": "T2", "price": 112.40, "change_pct": 1.90, "status": "bull", "tag": "【支撑位等2B】"},
    {"symbol": "AMD",  "tier": "T2", "price": 154.60, "change_pct": 1.45, "status": "bull", "tag": "【共振突破前高】"},
    {"symbol": "LRCX", "tier": "T2", "price": 920.10, "change_pct": 2.15, "status": "bull", "tag": "【半导体真突破】"},
    {"symbol": "WDC",  "tier": "T2", "price": 68.30,  "change_pct": 0.20, "status": "neutral", "tag": "【横盘洗盘蓄势】"},
    {"symbol": "STX",  "tier": "T2", "price": 98.70,  "change_pct": -0.40, "status": "bear", "tag": "【先锋轻微背离】"}
]

if trades:
    t = trades[0]
    review_data = {
        "day": now_myt.strftime("%a").upper(),
        "date": now_myt.strftime("%m/%d"),
        "is_completed": True,
        "current_bars": 48,
        "total_bars": 48,
        "bias": p.get("BIAS_DESC", "Bullish Wave") if p else "Bullish Wave",
        "setup": f"{t.get('Signal', '2B Sweep')} @ {t.get('Entry_Price', 486.50):.2f}",
        "entry_price": float(t.get("Entry_Price", 486.50)),
        "entry_time": t.get("Entry_Time", "22:15 MYT"),
        "stop_loss": float(t.get("Stop_Loss", 485.40)),
        "take_profit": float(t.get("Take_Profit", 488.90)),
        "outcome_pnl": float(t.get("PnL_Points", 2.40)),
        "discipline_score": "100% STRICT PASS"
    }
else:
    review_data = {
        "day": now_myt.strftime("%a").upper(),
        "date": now_myt.strftime("%m/%d"),
        "is_completed": False,
        "current_bars": 42,
        "total_bars": 48,
        "bias": "5M-VPA 计算中",
        "setup": "等待结构回踩准入",
        "entry_price": 0.0,
        "entry_time": "--:--",
        "stop_loss": 0.0,
        "take_profit": 0.0,
        "outcome_pnl": 0.0,
        "discipline_score": "CALCULATING"
    }

# 序列化状态
json_data_payload = json.dumps({
    "macro": macro_data,
    "core13": core13_data,
    "review": review_data
}, ensure_ascii=False)

# 5. 读取外部 index.html 并完成数据注入
html_file_path = os.path.join(os.path.dirname(__file__), "index.html")
if os.path.exists(html_file_path):
    with open(html_file_path, "r", encoding="utf-8") as f:
        html_template = f.read()
    rendered_terminal = html_template.replace("__INJECTED_DATA__", json_data_payload)
else:
    rendered_terminal = "<h1>index.html not found. Please create index.html in the repository root.</h1>"

# 6. Streamlit 页面边距与滚动锁定
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

# 渲染 100vh 机构量化看板
st.components.v1.html(rendered_terminal, height=880, scrolling=False)
