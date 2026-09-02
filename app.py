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

# 读取月历历史用于顶部 5-Day Strip
df_journal = load_journal()

# 4. 构建数据模型 (Tab 1 Macro + Tab 3 Review)
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
    {"symbol": "MU",   tier": "T2", "price": 112.40, "change_pct": 1.90, "status": "bull", "tag": "【支撑位等2B】"},
    {"symbol": "AMD",  tier": "T2", "price": 154.60, "change_pct": 1.45, "status": "bull", "tag": "【共振突破前高】"},
    {"symbol": "LRCX", tier: "T2", "price": 920.10, "change_pct": 2.15, "status": "bull", "tag": "【半导体真突破】"},
    {"symbol": "WDC",  tier: "T2", "price": 68.30,  change_pct": 0.20, "status": "neutral", "tag": "【横盘洗盘蓄势】"},
    {"symbol": "STX",  tier: "T2", "price": 98.70,  change_pct: -0.40, "status": "bear", "tag": "【先锋轻微背离】"}
]

# 5M 走势与复盘封装
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

# 序列化为前端 JSON
json_state = json.dumps({
    "macro": macro_data,
    "core13": core13_data,
    "review": review_data
}, ensure_ascii=False)

# 5. Streamlit 主页面渲染：消除边距，注入 100vh 机构终端
st.markdown("""
<style>
    /* 彻底消除 Streamlit 默认留白与全局滚动条 */
    #MainMenu, header, footer { visibility: hidden !important; height: 0 !important; }
    .block-container {
        padding: 0 !important;
        margin: 0 !important;
        max-width: 100vw !important;
        height: 100vh !important;
        overflow: hidden !important;
    }
    iframe { border: none !important; }
</style>
""", unsafe_allow_html=True)

# 6. 单文件嵌入 AlphaCockpit Pro 终端 HTML / JS / Plotly 引擎
terminal_html = f"""
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
    :root {{
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
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; user-select: none; }}
    html, body {{
      width: 100vw; height: 100vh; max-height: 100vh; overflow: hidden;
      background-color: var(--bg-canvas); color: var(--text-main);
      font-family: var(--font-sans); font-size: 12px; line-height: 1.3;
      -webkit-font-smoothing: antialiased;
    }}
    .font-mono {{ font-family: var(--font-mono); }}
    ::-webkit-scrollbar {{ width: 4px; height: 4px; }}
    ::-webkit-scrollbar-track {{ background: transparent; }}
    ::-webkit-scrollbar-thumb {{ background: rgba(255,255,255,0.12); border-radius: 2px; }}
    ::-webkit-scrollbar-thumb:hover {{ background: rgba(255,255,255,0.25); }}

    #app-container {{
      display: flex; flex-direction: column; width: 100vw; height: 100vh;
      background: radial-gradient(circle at 50% 0%, rgba(56, 189, 248, 0.03) 0%, transparent 60%), var(--bg-canvas);
    }}
    #top-hud {{
      height: 42px; min-height: 42px; display: flex; align-items: center;
      justify-content: space-between; padding: 0 14px; background: var(--surface-card);
      border-bottom: 1px solid var(--border-subtle); backdrop-filter: blur(16px); z-index: 20;
    }}
    .hud-left, .hud-center, .hud-right {{ display: flex; align-items: center; gap: 12px; }}
    .brand-tag {{ font-weight: 800; font-size: 12px; letter-spacing: 0.08em; color: #fff; display: flex; align-items: center; gap: 6px; }}
    .brand-tag span {{ background: linear-gradient(135deg, var(--accent), #818cf8); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }}
    .clock-group {{ display: flex; align-items: center; gap: 8px; background: rgba(0,0,0,0.3); padding: 3px 8px; border-radius: 4px; border: 1px solid var(--border-subtle); }}
    .clock-item {{ font-family: var(--font-mono); font-size: 11px; color: var(--text-muted); }}
    .clock-item b {{ color: var(--text-main); }}
    .session-pill {{ display: flex; align-items: center; gap: 6px; padding: 3px 8px; border-radius: 12px; background: var(--bull-bg); border: 1px solid rgba(0, 230, 118, 0.3); color: var(--bull); font-size: 10px; font-weight: 700; }}
    .status-dot {{ width: 6px; height: 6px; border-radius: 50%; background: var(--bull); box-shadow: 0 0 8px var(--bull); animation: pulse-dot 1.8s infinite; }}
    .verdict-banner {{ padding: 4px 12px; border-radius: 4px; background: rgba(0, 230, 118, 0.08); border: 1px solid rgba(0, 230, 118, 0.25); font-weight: 600; font-size: 11px; color: var(--bull); white-space: nowrap; }}
    .hud-metrics {{ display: flex; align-items: center; gap: 12px; font-family: var(--font-mono); font-size: 11px; }}
    .hud-metric-val {{ font-weight: 700; color: #fff; }}
    .btn-ai-pump {{
      display: flex; align-items: center; gap: 6px; padding: 4px 10px; border-radius: 4px;
      background: linear-gradient(135deg, rgba(56, 189, 248, 0.2), rgba(129, 140, 248, 0.2));
      border: 1px solid var(--accent); color: #fff; font-weight: 600; font-size: 11px; cursor: pointer; transition: all 0.2s;
    }}
    .btn-ai-pump:hover {{ background: linear-gradient(135deg, rgba(56, 189, 248, 0.35), rgba(129, 140, 248, 0.35)); box-shadow: 0 0 12px rgba(56, 189, 248, 0.3); }}
    .kbd-shortcut {{ background: rgba(0,0,0,0.4); padding: 1px 4px; border-radius: 3px; font-size: 9px; color: var(--accent); border: 1px solid rgba(56, 189, 248, 0.4); }}

    #main-deck {{ display: flex; flex: 1; height: calc(100vh - 42px); width: 100vw; overflow: hidden; }}
    #mini-rail {{ width: 46px; min-width: 46px; background: #090D14; border-right: 1px solid var(--border-subtle); display: flex; flex-direction: column; align-items: center; padding: 10px 0; gap: 16px; z-index: 10; }}
    .rail-btn {{ width: 32px; height: 32px; display: flex; align-items: center; justify-content: center; border-radius: 6px; color: var(--text-muted); cursor: pointer; transition: all 0.2s; }}
    .rail-btn:hover, .rail-btn.active {{ color: var(--accent); background: rgba(56, 189, 248, 0.1); }}

    #left-tactical {{ width: 28%; min-width: 310px; max-width: 380px; background: var(--surface-card); border-right: 1px solid var(--border-subtle); display: flex; flex-direction: column; overflow: hidden; backdrop-filter: blur(16px); }}
    .tactical-zones {{ padding: 10px 12px; display: flex; flex-direction: column; gap: 8px; border-bottom: 1px solid var(--border-subtle); background: rgba(13, 17, 24, 0.6); }}
    .zone-row {{ display: flex; gap: 8px; }}
    .zone-card {{ flex: 1; padding: 6px 10px; border-radius: 4px; background: rgba(18, 24, 38, 0.9); border: 1px solid var(--border-subtle); }}
    .zone-card.sbr {{ border-left: 3px solid var(--bear); }}
    .zone-card.rbs {{ border-left: 3px solid var(--bull); }}
    .zone-label {{ font-size: 9px; font-weight: 700; color: var(--text-muted); display: flex; justify-content: space-between; }}
    .zone-range {{ font-family: var(--font-mono); font-size: 13px; font-weight: 700; margin-top: 2px; color: var(--text-main); }}
    .anchors-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 4px; }}
    .anchor-cell {{ background: rgba(255, 255, 255, 0.02); border: 1px solid var(--border-subtle); padding: 3px 4px; border-radius: 3px; text-align: center; }}
    .anchor-tag {{ font-size: 8.5px; color: var(--text-dim); font-weight: 700; }}
    .anchor-val {{ font-family: var(--font-mono); font-size: 10.5px; font-weight: 600; color: #cbd5e1; }}

    .core13-section {{ flex: 1; display: flex; flex-direction: column; overflow: hidden; }}
    .core13-header {{ height: 24px; display: flex; align-items: center; padding: 0 10px; font-size: 9.5px; font-weight: 700; color: var(--text-dim); border-bottom: 1px solid var(--border-subtle); background: rgba(0,0,0,0.25); }}
    .core13-body {{ flex: 1; overflow-y: auto; }}
    .core-row {{ height: 27px; min-height: 27px; display: flex; align-items: center; padding: 0 10px; border-bottom: 1px solid rgba(255,255,255,0.03); font-family: var(--font-mono); font-size: 11px; }}
    .core-row:hover {{ background: var(--surface-hover); }}
    .col-sym {{ width: 50px; font-weight: 700; color: #fff; font-family: var(--font-sans); }}
    .col-tier {{ width: 26px; font-size: 9px; color: var(--text-dim); }}
    .col-price {{ width: 58px; text-align: right; color: var(--text-main); font-weight: 500; }}
    .col-chg {{ width: 52px; text-align: right; font-weight: 600; }}
    .col-tag {{ flex: 1; text-align: right; font-size: 10px; font-family: var(--font-sans); font-weight: 600; }}
    .tag-bull {{ color: var(--bull); }}
    .tag-bear {{ color: var(--bear); }}
    .tag-neutral {{ color: var(--text-muted); }}

    #right-workspace {{ flex: 1; display: flex; flex-direction: column; overflow: hidden; background: var(--bg-canvas); }}
    #track-strip {{ height: 34px; min-height: 34px; display: flex; align-items: center; justify-content: space-between; padding: 0 12px; background: #090D14; border-bottom: 1px solid var(--border-subtle); gap: 12px; }}
    .weekday-pills {{ display: flex; align-items: center; gap: 6px; }}
    .day-pill {{ display: flex; align-items: center; gap: 6px; padding: 2px 8px; border-radius: 4px; background: rgba(255,255,255,0.03); border: 1px solid var(--border-subtle); font-size: 10.5px; font-family: var(--font-mono); cursor: pointer; }}
    .day-pill.active {{ border-color: var(--accent); background: rgba(56, 189, 248, 0.1); }}
    .day-pill .name {{ font-weight: 700; color: var(--text-muted); font-family: var(--font-sans); }}
    .day-pill .pnl-pos {{ color: var(--bull); font-weight: 700; }}
    .day-pill .pnl-neg {{ color: var(--bear); font-weight: 700; }}
    .day-pill .pnl-flat {{ color: var(--text-dim); }}
    .day-summary-banner {{ display: flex; align-items: center; gap: 12px; font-size: 10.5px; color: var(--text-muted); }}
    .day-summary-banner b {{ color: var(--text-main); font-family: var(--font-mono); }}

    #chart-station {{ flex: 1; width: 100%; height: calc(100% - 34px); position: relative; }}

    #ai-drawer {{
      position: fixed; top: 0; right: -480px; width: 460px; height: 100vh;
      background: rgba(13, 17, 24, 0.95); border-left: 1px solid rgba(255, 255, 255, 0.12);
      backdrop-filter: blur(24px); box-shadow: -10px 0 30px rgba(0, 0, 0, 0.6);
      display: flex; flex-direction: column; z-index: 100; transition: right 0.28s cubic-bezier(0.16, 1, 0.3, 1);
    }}
    #ai-drawer.open {{ right: 0; }}
    .drawer-header {{ height: 48px; padding: 0 16px; display: flex; align-items: center; justify-content: space-between; border-bottom: 1px solid var(--border-subtle); }}
    .drawer-title {{ font-weight: 700; font-size: 13px; color: #fff; display: flex; align-items: center; gap: 8px; }}
    .btn-close {{ background: transparent; border: none; color: var(--text-muted); cursor: pointer; padding: 4px; border-radius: 4px; }}
    .drawer-actions {{ padding: 10px 16px; border-bottom: 1px solid var(--border-subtle); background: rgba(0,0,0,0.25); display: flex; gap: 8px; }}
    .btn-copy-all {{ flex: 1; padding: 7px 12px; background: linear-gradient(135deg, #0284c7, #4f46e5); border: none; border-radius: 4px; color: #fff; font-weight: 600; font-size: 11px; cursor: pointer; }}
    .btn-toggle-state {{ padding: 7px 10px; background: rgba(255,255,255,0.05); border: 1px solid var(--border-subtle); border-radius: 4px; color: var(--text-muted); font-size: 10.5px; cursor: pointer; }}
    .drawer-body {{ flex: 1; padding: 14px 16px; overflow-y: auto; display: flex; flex-direction: column; gap: 14px; }}
    .prompt-block {{ background: rgba(0, 0, 0, 0.4); border: 1px solid var(--border-subtle); border-radius: 6px; padding: 10px 12px; font-family: var(--font-mono); font-size: 11px; line-height: 1.45; color: #cbd5e1; }}
    .prompt-block-header {{ display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px; font-weight: 700; font-size: 10.5px; color: var(--text-muted); }}

    .status-badge {{ display: inline-flex; align-items: center; gap: 5px; padding: 2px 7px; border-radius: 10px; font-size: 9.5px; font-weight: 700; }}
    .status-badge.computing {{ background: var(--warn-bg); color: var(--warn); border: 1px solid rgba(245, 158, 11, 0.35); animation: pulse-warn 1.5s infinite; }}
    .status-badge.completed {{ background: var(--bull-bg); color: var(--bull); border: 1px solid rgba(0, 230, 118, 0.35); }}

    @keyframes pulse-dot {{ 0%, 100% {{ opacity: 1; transform: scale(1); }} 50% {{ opacity: 0.4; transform: scale(0.85); }} }}
    @keyframes pulse-warn {{ 0%, 100% {{ opacity: 1; }} 50% {{ opacity: 0.55; }} }}

    #toast {{ position: fixed; bottom: 20px; left: 50%; transform: translateX(-50%) translateY(50px); background: #0284c7; color: #fff; padding: 6px 14px; border-radius: 20px; font-size: 11px; font-weight: 600; opacity: 0; transition: all 0.25s ease; z-index: 1000; }}
    #toast.show {{ transform: translateX(-50%) translateY(0); opacity: 1; }}
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
        <div class="verdict-banner" id="hud-verdict">{macro_data['verdict_title']}</div>
      </div>
      <div class="hud-right">
        <div class="hud-metrics">
          <div>QQQ: <span class="hud-metric-val">${macro_data['qqq_price']:.2f} (+{macro_data['qqq_change_pct']}%)</span></div>
          <div>ATR%: <span class="hud-metric-val" style="color: var(--accent);">{macro_data['atr_usage_pct']}%</span></div>
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
              <div class="zone-range">{macro_data['primary_sbr'][0]:.2f} - {macro_data['primary_sbr'][1]:.2f}</div>
            </div>
            <div class="zone-card rbs">
              <div class="zone-label"><span>PRIMARY RBS</span> <span>1H 支撑</span></div>
              <div class="zone-range">{macro_data['primary_rbs'][0]:.2f} - {macro_data['primary_rbs'][1]:.2f}</div>
            </div>
          </div>
          <div class="anchors-grid">
            <div class="anchor-cell"><div class="anchor-tag">PDH</div><div class="anchor-val">{macro_data['anchors']['pdh']:.2f}</div></div>
            <div class="anchor-cell"><div class="anchor-tag">PDL</div><div class="anchor-val">{macro_data['anchors']['pdl']:.2f}</div></div>
            <div class="anchor-cell"><div class="anchor-tag">PMH</div><div class="anchor-val">{macro_data['anchors']['pmh']:.2f}</div></div>
            <div class="anchor-cell"><div class="anchor-tag">PML</div><div class="anchor-val">{macro_data['anchors']['pml']:.2f}</div></div>
          </div>
        </div>
        <div class="core13-section">
          <div class="core13-header">
            <span style="width: 50px;">SYMBOL</span><span style="width: 26px;">TIER</span>
            <span style="width: 58px; text-align: right;">PRICE</span><span style="width: 52px; text-align: right;">CHG</span>
            <span style="flex: 1; text-align: right;">ACTION</span>
          </div>
          <div class="core13-body" id="core13-list"></div>
        </div>
      </aside>

      <main id="right-workspace">
        <div id="track-strip">
          <div class="weekday-pills">
            <div class="day-pill"><span class="name">MON</span> <span class="pnl-pos">+1.80 pt</span></div>
            <div class="day-pill active"><span class="name">TUE</span> <span class="pnl-pos">+{review_data['outcome_pnl']:.2f} pt</span></div>
            <div class="day-pill"><span class="name">WED</span> <span class="pnl-flat">⚪ 纪律空仓</span></div>
            <div class="day-pill"><span class="name">THU</span> <span class="pnl-neg">-0.90 pt</span></div>
            <div class="day-pill"><span class="name">FRI</span> <span class="pnl-pos">+3.10 pt</span></div>
          </div>
          <div class="day-summary-banner">
            <span>ACTIVE TRADE:</span>
            <span>Setup: <b>{review_data['setup']}</b></span>
            <span>Entry: <b>{review_data['entry_price']:.2f}</b></span>
            <span>TP: <b style="color: var(--bull);">{review_data['take_profit']:.2f} (+{review_data['outcome_pnl']:.2f} pt)</b></span>
          </div>
        </div>
        <div id="chart-station"></div>
      </main>
    </div>

    <div id="ai-drawer">
      <div class="drawer-header">
        <div class="drawer-title">⚡ AI CONTEXT AGGREGATOR</div>
        <button class="btn-close" onclick="toggleAIDrawer()">✕</button>
      </div>
      <div class="drawer-actions">
        <button class="btn-copy-all" onclick="copyAIPrompt()">1-CLICK COPY FOR LLM</button>
        <button class="btn-toggle-state" onclick="toggleReviewState()">Toggle State: <b id="state-label">Completed</b></button>
      </div>
      <div class="drawer-body">
        <div class="prompt-block">
          <div class="prompt-block-header"><span>SECTION 1: Macro & Core 13 Snapshot</span><span class="status-badge completed">LIVE SYNC</span></div>
          <pre id="prompt-section-macro" style="white-space: pre-wrap;"></pre>
        </div>
        <div class="prompt-block">
          <div class="prompt-block-header"><span>SECTION 2: 5M VPA & Execution Deep Review</span><span id="review-status-badge" class="status-badge completed">COMPLETED</span></div>
          <pre id="prompt-section-review" style="white-space: pre-wrap;"></pre>
        </div>
      </div>
    </div>
    <div id="toast">Prompt Copied to Clipboard!</div>
  </div>

  <script>
    const terminalState = {json_state};

    function updateClocks() {{
      const now = new Date();
      document.getElementById('clock-myt').innerText = new Intl.DateTimeFormat('en-GB', {{ timeZone: "Asia/Kuala_Lumpur", hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' }}).format(now);
      document.getElementById('clock-et').innerText = new Intl.DateTimeFormat('en-GB', {{ timeZone: "America/New_York", hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' }}).format(now);
    }}
    setInterval(updateClocks, 1000); updateClocks();

    function renderCore13() {{
      const container = document.getElementById('core13-list');
      container.innerHTML = terminalState.core13.map(row => {{
        const tagClass = row.status === 'bull' ? 'tag-bull' : (row.status === 'bear' ? 'tag-bear' : 'tag-neutral');
        const chgColor = row.change_pct >= 0 ? 'var(--bull)' : 'var(--bear)';
        const chgSign = row.change_pct > 0 ? '+' : '';
        return `
          <div class="core-row">
            <span class="col-sym">${{row.symbol}}</span>
            <span class="col-tier">${{row.tier}}</span>
            <span class="col-price">$${{row.price.toFixed(2)}}</span>
            <span class="col-chg" style="color: ${{chgColor}}">${{chgSign}}${{row.change_pct.toFixed(2)}}%</span>
            <span class="col-tag ${{tagClass}}">${{row.tag}}</span>
          </div>`;
      }}).join('');
    }}
    renderCore13();

    function updateAIDrawerContent() {{
      const {{ macro, core13, review }} = terminalState;
      const anomalies = core13.filter(c => Math.abs(c.change_pct) >= 1.5 || c.status === 'bull').slice(0, 5)
        .map(c => `- ${{c.symbol.padEnd(5)}}: $${{c.price.toFixed(2)}} (${{c.change_pct >= 0 ? '+' : ''}}${{c.change_pct.toFixed(2)}}%) | ${{c.tag}}`).join('\\n');

      const macroPrompt = `[MACRO VERDICT]\\nSession: ${{macro.session}}\\nQQQ Price: $${{macro.qqq_price}} (+${{macro.qqq_change_pct}}%) | ATR Usage: ${{macro.atr_usage_pct}}%\\nMarket Tone: Bullish Wave (${{macro.leading_count}}/${{macro.total_count}} Leading)\\nPrimary RBS (Support): ${{macro.primary_rbs[0].toFixed(2)}} - ${{macro.primary_rbs[1].toFixed(2)}}\\nPrimary SBR (Resistance): ${{macro.primary_sbr[0].toFixed(2)}} - ${{macro.primary_sbr[1].toFixed(2)}}\\n\\n[CORE 13 ANOMALIES]\\n${{anomalies}}`;
      document.getElementById('prompt-section-macro').innerText = macroPrompt;

      const badge = document.getElementById('review-status-badge');
      if (!review.is_completed) {{
        badge.className = 'status-badge computing';
        badge.innerText = `⏳ COMPUTING (${{review.current_bars}}/${{review.total_bars}} Bars)`;
        document.getElementById('prompt-section-review').innerText = `[STATUS: 5M-VPA 深度量价计算中 (${{review.current_bars}}/${{review.total_bars}} Bars)... 尚未生成最终结论]\\n当前进度: ${{review.current_bars}} / ${{review.total_bars}} 根K线\\n提示: 盘中实时数据持续注入中，当日最终胜率与盈亏比复盘尚未生成。`;
      }} else {{
        badge.className = 'status-badge completed';
        badge.innerText = `COMPLETED (${{review.total_bars}}/${{review.total_bars}} BARS)`;
        document.getElementById('prompt-section-review').innerText = `[EXECUTION DETAIL - ${{review.day}} ${{review.date}}]\\nBias: ${{review.bias}}\\nSetup: ${{review.setup}}\\nEntry: ${{review.entry_price.toFixed(2)}} (${{review.entry_time}})\\nStop Loss: ${{review.stop_loss.toFixed(2)}}\\nTake Profit: ${{review.take_profit.toFixed(2)}}\\nResult: +${{review.outcome_pnl.toFixed(2)}} pt (Target Reached)\\nDiscipline Score: ${{review.discipline_score}}`;
      }}
    }}

    function toggleAIDrawer() {{
      const drawer = document.getElementById('ai-drawer');
      drawer.classList.toggle('open');
      if (drawer.classList.contains('open')) updateAIDrawerContent();
    }}

    function toggleReviewState() {{
      terminalState.review.is_completed = !terminalState.review.is_completed;
      terminalState.review.current_bars = terminalState.review.is_completed ? 48 : 42;
      document.getElementById('state-label').innerText = terminalState.review.is_completed ? 'Completed' : 'Computing (42/48)';
      updateAIDrawerContent();
    }}

    function copyAIPrompt() {{
      const p1 = document.getElementById('prompt-section-macro').innerText;
      const p2 = document.getElementById('prompt-section-review').innerText;
      const task = `[TASK FOR AI]: 请基于上述宏观结构、Core 13强弱与复盘指标，严格按照定量逻辑，给出下一交易窗口的入场风险评估及关键阻力/支撑策略。`;
      const fullText = `# QUANT DESK SNAPSHOT & CONTEXT\\n\\n## SECTION 1: MACRO & CORE 13 SNAPSHOT\\n${{p1}}\\n\\n## SECTION 2: 5M VPA & EXECUTION DEEP REVIEW\\n${{p2}}\\n\\n---\\n${{task}}`;
      navigator.clipboard.writeText(fullText).then(() => showToast("Full Context Prompt Copied for LLM!"));
    }}

    function copyFutuLines() {{
      const sbr = terminalState.macro.primary_sbr;
      const rbs = terminalState.macro.primary_rbs;
      const futu = `TREND_BIAS := 1;\\nSBR_TOP := ${{sbr[1].toFixed(2)}};\\nSBR_BOT := ${{sbr[0].toFixed(2)}};\\nRBS_TOP := ${{rbs[1].toFixed(2)}};\\nRBS_BOT := ${{rbs[0].toFixed(2)}};`;
      navigator.clipboard.writeText(futu).then(() => showToast("Futu 13-Line Script Copied!"));
    }}

    function showToast(msg) {{
      const toast = document.getElementById('toast');
      toast.innerText = msg; toast.classList.add('show');
      setTimeout(() => toast.classList.remove('show'), 2200);
    }}

    window.addEventListener('keydown', (e) => {{
      if (e.code === 'Space' && e.target.tagName !== 'INPUT' && e.target.tagName !== 'TEXTAREA') {{
        e.preventDefault(); toggleAIDrawer();
      }}
    }});

    function renderPlotlyChart() {{
      const times = [], opens = [], highs = [], lows = [], closes = [], raw_volumes = [];
      let basePrice = 485.50;
      for (let i = 0; i < 32; i++) {{
        const totalMinutes = 21 * 60 + 30 + i * 5;
        times.push(`${{String(Math.floor(totalMinutes / 60) % 24).padStart(2, '0')}}:${{String(totalMinutes % 60).padStart(2, '0')}}`);
        let o, h_bar, l_bar, c, vol;
        if (i === 0) {{ o = 487.20; h_bar = 488.50; l_bar = 486.80; c = 487.80; vol = 1450000; }}
        else if (i === 9) {{ o = 486.60; l_bar = 486.10; h_bar = 487.10; c = 486.90; vol = 380000; }}
        else if (i > 9 && i <= 24) {{
          basePrice += 0.15 + (Math.random() * 0.1);
          o = basePrice - 0.1; c = basePrice + 0.1; h_bar = c + 0.15; l_bar = o - 0.15; vol = 120000 + Math.random() * 90000;
        }} else {{
          basePrice += (Math.random() - 0.48) * 0.25;
          o = basePrice - 0.08; c = basePrice + 0.08; h_bar = Math.max(o, c) + 0.12; l_bar = Math.min(o, c) - 0.12; vol = 95000 + Math.random() * 60000;
        }}
        opens.push(o); highs.push(h_bar); lows.push(l_bar); closes.push(c); raw_volumes.push(vol);
      }}

      const sortedVols = [...raw_volumes].sort((a, b) => a - b);
      const vol_p95 = sortedVols[Math.floor(sortedVols.length * 0.95)];
      const clipped_volumes = raw_volumes.map(v => Math.min(v, vol_p95));
      const bar_colors = closes.map((c, idx) => c >= opens[idx] ? '#00E676' : '#FF5252');

      const traceCandle = {{
        type: 'candlestick', x: times, open: opens, high: highs, low: lows, close: closes, yaxis: 'y1', name: 'QQQ 5M',
        increasing: {{ line: {{ color: '#00E676', width: 1.2 }}, fillcolor: '#00E676' }},
        decreasing: {{ line: {{ color: '#FF5252', width: 1.2 }}, fillcolor: '#FF5252' }}
      }};
      const traceVolume = {{
        type: 'bar', x: times, y: clipped_volumes, yaxis: 'y2', name: 'VPA Vol (P95 Clip)',
        marker: {{ color: bar_colors, line: {{ color: bar_colors, width: 0.5 }} }}
      }};

      const layout = {{
        template: 'plotly_dark', paper_bgcolor: '#080B10', plot_bgcolor: '#080B10',
        margin: {{ l: 45, r: 45, t: 15, b: 25 }}, showlegend: false, hovermode: 'x unified',
        grid: {{ rows: 2, columns: 1, pattern: 'independent', roworder: 'top to bottom' }},
        yaxis: {{ domain: [0.26, 1.0], side: 'right', gridcolor: 'rgba(255,255,255,0.05)', zeroline: false, tickfont: {{ family: 'JetBrains Mono', size: 10, color: '#8B949E' }} }},
        yaxis2: {{ domain: [0.0, 0.22], side: 'right', gridcolor: 'rgba(255,255,255,0.04)', zeroline: false, tickfont: {{ family: 'JetBrains Mono', size: 8.5, color: '#6E7681' }} }},
        xaxis: {{ anchor: 'y2', type: 'category', gridcolor: 'rgba(255,255,255,0.05)', tickfont: {{ family: 'JetBrains Mono', size: 9.5, color: '#8B949E' }} }},
        shapes: [
          {{ type: 'rect', xref: 'paper', yref: 'y1', x0: 0, x1: 1, y0: {macro_data['primary_sbr'][0]:.2f}, y1: {macro_data['primary_sbr'][1]:.2f}, fillcolor: 'rgba(255, 82, 82, 0.12)', line: {{ color: 'rgba(255, 82, 82, 0.4)', width: 1, dash: 'dash' }}, layer: 'below' }},
          {{ type: 'rect', xref: 'paper', yref: 'y1', x0: 0, x1: 1, y0: {macro_data['primary_rbs'][0]:.2f}, y1: {macro_data['primary_rbs'][1]:.2f}, fillcolor: 'rgba(0, 230, 118, 0.12)', line: {{ color: 'rgba(0, 230, 118, 0.4)', width: 1, dash: 'dash' }}, layer: 'below' }},
          {{ type: 'line', xref: 'paper', yref: 'y1', x0: 0, x1: 1, y0: {macro_data['anchors']['pdh']:.2f}, y1: {macro_data['anchors']['pdh']:.2f}, line: {{ color: '#F59E0B', width: 1, dash: 'dot' }} }}
        ],
        annotations: [
          {{ xref: 'paper', yref: 'y1', x: 0.98, y: {macro_data['primary_sbr'][1]:.2f}, text: 'PRIMARY SBR [{macro_data['primary_sbr'][0]:.2f} - {macro_data['primary_sbr'][1]:.2f}]', showarrow: false, font: {{ family: 'Inter', size: 9.5, color: '#FF5252' }}, xanchor: 'right' }},
          {{ xref: 'paper', yref: 'y1', x: 0.98, y: {macro_data['primary_rbs'][0]:.2f}, text: 'PRIMARY RBS [{macro_data['primary_rbs'][0]:.2f} - {macro_data['primary_rbs'][1]:.2f}]', showarrow: false, font: {{ family: 'Inter', size: 9.5, color: '#00E676' }}, xanchor: 'right' }},
          {{ x: '22:15', y: 486.50, yref: 'y1', text: '🚀 BUY 486.50 (2B Sweep)', showarrow: true, arrowhead: 2, arrowcolor: '#00E676', ax: 0, ay: 32, bgcolor: '#0D1118', bordercolor: '#00E676', borderwidth: 1, font: {{ family: 'JetBrains Mono', size: 9.5, color: '#00E676' }} }},
          {{ x: '23:30', y: 488.90, yref: 'y1', text: '🏁 TP 488.90 (+2.40 pt)', showarrow: true, arrowhead: 2, arrowcolor: '#38BDF8', ax: 0, ay: -32, bgcolor: '#0D1118', bordercolor: '#38BDF8', borderwidth: 1, font: {{ family: 'JetBrains Mono', size: 9.5, color: '#38BDF8' }} }}
        ]
      }};
      Plotly.newPlot('chart-station', [traceCandle, traceVolume], layout, {{ responsive: true, displayModeBar: false }});
    }}

    window.addEventListener('DOMContentLoaded', () => {{
      renderPlotlyChart();
      updateAIDrawerContent();
    }});
    window.addEventListener('resize', () => {{ Plotly.Plots.resize('chart-station'); }});
  </script>
</body>
</html>
"""

# 渲染完整机构级独立 DOM (高度锁定 100vh)
st.components.v1.html(terminal_html, height=880, scrolling=False)
