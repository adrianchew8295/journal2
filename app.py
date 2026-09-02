# 文件名：app.py
# 作用：AlphaCockpit Pro 顶级量化终端（100vh 零滚动 / 42px HUD / 28%战区 / 72%双层图 / AI抽屉）
import datetime
import json
import os
import pytz
import numpy as np
import pandas as pd
import streamlit as st

from data_fetcher import fetch_raw_data_with_retry
from futu_engine import compute_futu_13_params, simulate_trades_with_2b
from journal_manager import load_journal, append_to_journal

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

df_journal = load_journal()

# 4. 构建标准化数据模型 (Tab 1 Macro + Tab 3 Review)
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

# 序列化为前端安全 JSON 字符串
init_state_json = json.dumps({
    "macro": macro_data,
    "core13": core13_data,
    "review": review_data
}, ensure_ascii=False)

# 5. Streamlit 样式净化 (锁定 100vh 零全局滚动条)
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

# 6. 单文件注入纯原生 Webapp
terminal_html = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no" />
  <title>AlphaCockpit Pro</title>
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600;700&display=swap" rel="stylesheet" />
  <script src="https://cdn.plot.ly/plotly-2.32.0.min.js"></script>
  <style>
    :root {
      --bg-canvas: #080B10;
      --surface-card: rgba(18, 24, 38, 0.75);
      --surface-hover: rgba(255, 255, 255, 0.04);
      --border-subtle: rgba(255, 255, 255, 0.08);
      --border-active: rgba(56, 189, 248, 0.4);
      --bull: #00E676;
      --bull-bg: rgba(0, 230, 118, 0.12);
      --bear: #FF5252;
      --bear-bg: rgba(255, 82, 82, 0.12);
      --warn: #F59E0B;
      --warn-bg: rgba(245, 158, 11, 0.12);
      --accent: #38BDF8;
      --text-main: #E6EDF3;
      --text-muted: #8B949E;
      --text-dim: #6E7681;
      --font-mono: 'JetBrains Mono', monospace;
      --font-sans: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; user-select: none; }
    html, body {
      width: 100vw; height: 100vh; max-height: 100vh; overflow: hidden;
      background-color: var(--bg-canvas); color: var(--text-main);
      font-family: var(--font-sans); font-size: 12px; line-height: 1.3;
      -webkit-font-smoothing: antialiased;
    }
    ::-webkit-scrollbar { width: 4px; height: 4px; }
    ::-webkit-scrollbar-track { background: transparent; }
    ::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.12); border-radius: 2px; }
    ::-webkit-scrollbar-thumb:hover { background: rgba(255,255,255,0.25); }

    #app-container {
      display: flex; flex-direction: column; width: 100vw; height: 100vh;
      background: radial-gradient(circle at 50% 0%, rgba(56, 189, 248, 0.03) 0%, transparent 60%), var(--bg-canvas);
    }
    #top-hud {
      height: 42px; min-height: 42px; display: flex; align-items: center;
      justify-content: space-between; padding: 0 14px; background: var(--surface-card);
      border-bottom: 1px solid var(--border-subtle); backdrop-filter: blur(16px); z-index: 20;
    }
    .hud-left, .hud-center, .hud-right { display: flex; align-items: center; gap: 12px; }
    .brand-tag { font-weight: 800; font-size: 12px; letter-spacing: 0.08em; color: #fff; display: flex; align-items: center; gap: 6px; }
    .brand-tag span { background: linear-gradient(135deg, var(--accent), #818cf8); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
    .clock-group { display: flex; align-items: center; gap: 8px; background: rgba(0,0,0,0.3); padding: 3px 8px; border-radius: 4px; border: 1px solid var(--border-subtle); }
    .clock-item { font-family: var(--font-mono); font-size: 11px; color: var(--text-muted); }
    .clock-item b { color: var(--text-main); }
    .session-pill { display: flex; align-items: center; gap: 6px; padding: 3px 8px; border-radius: 12px; background: var(--bull-bg); border: 1px solid rgba(0, 230, 118, 0.3); color: var(--bull); font-size: 10px; font-weight: 700; }
    .status-dot { width: 6px; height: 6px; border-radius: 50%; background: var(--bull); box-shadow: 0 0 8px var(--bull); animation: pulse-dot 1.8s infinite; }
    .verdict-banner { padding: 4px 12px; border-radius: 4px; background: rgba(0, 230, 118, 0.08); border: 1px solid rgba(0, 230, 118, 0.25); font-weight: 600; font-size: 11px; color: var(--bull); white-space: nowrap; }
    .hud-metrics { display: flex; align-items: center; gap: 12px; font-family: var(--font-mono); font-size: 11px; }
    .hud-metric-val { font-weight: 700; color: #fff; }
    .btn-ai-pump {
      display: flex; align-items: center; gap: 6px; padding: 4px 10px; border-radius: 4px;
      background: linear-gradient(135deg, rgba(56, 189, 248, 0.2), rgba(129, 140, 248, 0.2));
      border: 1px solid var(--accent); color: #fff; font-weight: 600; font-size: 11px; cursor: pointer; transition: all 0.2s;
    }
    .btn-ai-pump:hover { background: linear-gradient(135deg, rgba(56, 189, 248, 0.35), rgba(129, 140, 248, 0.35)); box-shadow: 0 0 12px rgba(56, 189, 248, 0.3); }
    .kbd-shortcut { background: rgba(0,0,0,0.4); padding: 1px 4px; border-radius: 3px; font-size: 9px; color: var(--accent); border: 1px solid rgba(56, 189, 248, 0.4); }

    #main-deck { display: flex; flex: 1; height: calc(100vh - 42px); width: 100vw; overflow: hidden; }
    #mini-rail { width: 46px; min-width: 46px; background: #090D14; border-right: 1px solid var(--border-subtle); display: flex; flex-direction: column; align-items: center; padding: 10px 0; gap: 16px; z-index: 10; }
    .rail-btn { width: 32px; height: 32px; display: flex; align-items: center; justify-content: center; border-radius: 6px; color: var(--text-muted); cursor: pointer; transition: all 0.2s; }
    .rail-btn:hover, .rail-btn.active { color: var(--accent); background: rgba(56, 189, 248, 0.1); }

    #left-tactical { width: 28%; min-width: 310px; max-width: 380px; background: var(--surface-card); border-right: 1px solid var(--border-subtle); display: flex; flex-direction: column; overflow: hidden; backdrop-filter: blur(16px); }
    .tactical-zones { padding: 10px 12px; display: flex; flex-direction: column; gap: 8px; border-bottom: 1px solid var(--border-subtle); background: rgba(13, 17, 24, 0.6); }
    .zone-row { display: flex; gap: 8px; }
    .zone-card { flex: 1; padding: 6px 10px; border-radius: 4px; background: rgba(18, 24, 38, 0.9); border: 1px solid var(--border-subtle); }
    .zone-card.sbr { border-left: 3px solid var(--bear); }
    .zone-card.rbs { border-left: 3px solid var(--bull); }
    .zone-label { font-size: 9px; font-weight: 700; color: var(--text-muted); display: flex; justify-content: space-between; }
    .zone-range { font-family: var(--font-mono); font-size: 13px; font-weight: 700; margin-top: 2px; color: var(--text-main); }
    .anchors-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 4px; }
    .anchor-cell { background: rgba(255, 255, 255, 0.02); border: 1px solid var(--border-subtle); padding: 3px 4px; border-radius: 3px; text-align: center; }
    .anchor-tag { font-size: 8.5px; color: var(--text-dim); font-weight: 700; }
    .anchor-val { font-family: var(--font-mono); font-size: 10.5px; font-weight: 600; color: #cbd5e1; }

    .core13-section { flex: 1; display: flex; flex-direction: column; overflow: hidden; }
    .core13-header { height: 24px; display: flex; align-items: center; padding: 0 10px; font-size: 9.5px; font-weight: 700; color: var(--text-dim); border-bottom: 1px solid var(--border-subtle); background: rgba(0,0,0,0.25); }
    .core13-body { flex: 1; overflow-y: auto; }
    .core-row { height: 27px; min-height: 27px; display: flex; align-items: center; padding: 0 10px; border-bottom: 1px solid rgba(255,255,255,0.03); font-family: var(--font-mono); font-size: 11px; }
    .core-row:hover { background: var(--surface-hover); }
    .col-sym { width: 50px; font-weight: 700; color: #fff; font-family: var(--font-sans); }
    .col-tier { width: 26px; font-size: 9px; color: var(--text-dim); }
    .col-price { width: 58px; text-align: right; color: var(--text-main); font-weight: 500; }
    .col-chg { width: 52px; text-align: right; font-weight: 600; }
    .col-tag { flex: 1; text-align: right; font-size: 10px; font-family: var(--font-sans); font-weight: 600; }
    .tag-bull { color: var(--bull); }
    .tag-bear { color: var(--bear); }
    .tag-neutral { color: var(--text-muted); }

    #right-workspace { flex: 1; display: flex; flex-direction: column; overflow: hidden; background: var(--bg-canvas); }
    #track-strip { height: 34px; min-height: 34px; display: flex; align-items: center; justify-content: space-between; padding: 0 12px; background: #090D14; border-bottom: 1px solid var(--border-subtle); gap: 12px; }
    .weekday-pills { display: flex; align-items: center; gap: 6px; }
    .day-pill { display: flex; align-items: center; gap: 6px; padding: 2px 8px; border-radius: 4px; background: rgba(255,255,255,0.03); border: 1px solid var(--border-subtle); font-size: 10.5px; font-family: var(--font-mono); cursor: pointer; }
    .day-pill.active { border-color: var(--accent); background: rgba(56, 189, 248, 0.1); }
    .day-pill .name { font-weight: 700; color: var(--text-muted); font-family: var(--font-sans); }
    .day-pill .pnl-pos { color: var(--bull); font-weight: 700; }
    .day-pill .pnl-neg { color: var(--bear); font-weight: 700; }
    .day-pill .pnl-flat { color: var(--text-dim); }
    .day-summary-banner { display: flex; align-items: center; gap: 12px; font-size: 10.5px; color: var(--text-muted); }
    .day-summary-banner b { color: var(--text-main); font-family: var(--font-mono); }

    #chart-station { flex: 1; width: 100%; height: calc(100% - 34px); position: relative; }

    #ai-drawer {
      position: fixed; top: 0; right: -480px; width: 460px; height: 100vh;
      background: rgba(13, 17, 24, 0.95); border-left: 1px solid rgba(255, 255, 255, 0.12);
      backdrop-filter: blur(24px); box-shadow: -10px 0 30px rgba(0, 0, 0, 0.6);
      display: flex; flex-direction: column; z-index: 100; transition: right 0.28s cubic-bezier(0.16, 1, 0.3, 1);
    }
    #ai-drawer.open { right: 0; }
    .drawer-header { height: 48px; padding: 0 16px; display: flex; align-items: center; justify-content: space-between; border-bottom: 1px solid var(--border-subtle); }
    .drawer-title { font-weight: 700; font-size: 13px; color: #fff; display: flex; align-items: center; gap: 8px; }
    .btn-close { background: transparent; border: none; color: var(--text-muted); cursor: pointer; padding: 4px; border-radius: 4px; }
    .drawer-actions { padding: 10px 16px; border-bottom: 1px solid var(--border-subtle); background: rgba(0,0,0,0.25); display: flex; gap: 8px; }
    .btn-copy-all { flex: 1; padding: 7px 12px; background: linear-gradient(135deg, #0284c7, #4f46e5); border: none; border-radius: 4px; color: #fff; font-weight: 600; font-size: 11px; cursor: pointer; }
    .btn-toggle-state { padding: 7px 10px; background: rgba(255,255,255,0.05); border: 1px solid var(--border-subtle); border-radius: 4px; color: var(--text-muted); font-size: 10.5px; cursor: pointer; }
    .drawer-body { flex: 1; padding: 14px 16px; overflow-y: auto; display: flex; flex-direction: column; gap: 14px; }
    .prompt-block { background: rgba(0, 0, 0, 0.4); border: 1px solid var(--border-subtle); border-radius: 6px; padding: 10px 12px; font-family: var(--font-mono); font-size: 11px; line-height: 1.45; color: #cbd5e1; }
    .prompt-block-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px; font-weight: 700; font-size: 10.5px; color: var(--text-muted); }

    .status-badge { display: inline-flex; align-items: center; gap: 5px; padding: 2px 7px; border-radius: 10px; font-size: 9.5px; font-weight: 700; }
    .status-badge.computing { background: var(--warn-bg); color: var(--warn); border: 1px solid rgba(245, 158, 11, 0.35); animation: pulse-warn 1.5s infinite; }
    .status-badge.completed { background: var(--bull-bg); color: var(--bull); border: 1px solid rgba(0, 230, 118, 0.35); }

    @keyframes pulse-dot { 0%, 100% { opacity: 1; transform: scale(1); } 50% { opacity: 0.4; transform: scale(0.85); } }
    @keyframes pulse-warn { 0%, 100% { opacity: 1; } 50% { opacity: 0.55; } }

    #toast { position: fixed; bottom: 20px; left: 50%; transform: translateX(-50%) translateY(50px); background: #0284c7; color: #fff; padding: 6px 14px; border-radius: 20px; font-size: 11px; font-weight: 600; opacity: 0; transition: all 0.25s ease; z-index: 1000; }
    #toast.show { transform: translateX(-50%) translateY(0); opacity: 1; }
  </style>
</head>
<body>
  <div id="app-container">
    <header id="top-hud">
      <div class="hud-left">
        <div class="brand-tag">ALPHA<span>COCKPIT</span> <span style="font-size: 9px; color: var(--text-dim); font-weight: 500;">PRO</span></div>
        <div class="clock-group">
          <div class="clock-item">MYT <b id="clock-myt">--:--:--</b></div>
          <span style="color: var(--border-subtle);">|</span>
          <div class="clock-item">ET <b id="clock-et">--:--:--</b></div>
        </div>
        <div class="session-pill"><div class="status-dot"></div>22:00-24:00 MYT WINDOW ACTIVE</div>
      </div>
      <div class="hud-center">
        <div class="verdict-banner" id="hud-verdict">--</div>
      </div>
      <div class="hud-right">
        <div class="hud-metrics">
          <div>QQQ: <span class="hud-metric-val" id="hud-qqq">--</span></div>
          <div>ATR%: <span class="hud-metric-val" id="hud-atr" style="color: var(--accent);">--</span></div>
        </div>
        <button class="btn-ai-pump" onclick="toggleAIDrawer()">AI DATA PUMP <span class="kbd-shortcut">SPACE</span></button>
      </div>
    </header>

    <div id="main-deck">
      <nav id="mini-rail">
        <div class="rail-btn active" title="Cockpit Deck">⊞</div>
        <div class="rail-btn" title="Sync Futu 13 Lines" onclick="copyFutuLines()">⚡</div>
        <div class="rail-btn" style="margin-top: auto;" title="Connected">●</div>
      </nav>

      <aside id="left-tactical">
        <div class="tactical-zones">
          <div class="zone-row">
            <div class="zone-card sbr">
              <div class="zone-label"><span>PRIMARY SBR</span> <span>1H 阻力</span></div>
              <div class="zone-range" id="deck-sbr">--</div>
            </div>
            <div class="zone-card rbs">
              <div class="zone-label"><span>PRIMARY RBS</span> <span>1H 支撑</span></div>
              <div class="zone-range" id="deck-rbs">--</div>
            </div>
          </div>
          <div class="anchors-grid">
            <div class="anchor-cell"><div class="anchor-tag">PDH</div><div class="anchor-val" id="anc-pdh">--</div></div>
            <div class="anchor-cell"><div class="anchor-tag">PDL</div><div class="anchor-val" id="anc-pdl">--</div></div>
            <div class="anchor-cell"><div class="anchor-tag">PMH</div><div class="anchor-val" id="anc-pmh">--</div></div>
            <div class="anchor-cell"><div class="anchor-tag">PML</div><div class="anchor-val" id="anc-pml
