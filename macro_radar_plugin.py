# 文件名: macro_radar_plugin.py
# 作用: Tab 1 纯大白话卡片清单流 (无抽象图表 · 红绿大字决策卡 + 13 标的卡片矩阵 · SNDK 永久保底)

import datetime
import numpy as np
import pandas as pd
import pytz
import requests
import streamlit as st
import yfinance as yf

tz_ny = pytz.timezone("America/New_York")
tz_myt = pytz.timezone("Asia/Kuala_Lumpur")

TIINGO_TOKEN = "bcffe3a5cf7eeef085e405cfa4a3e5691b976217"

# 13 核心标的配置
TICKERS_CONFIG = {
    "NVDA": {"name": "英伟达", "weight_desc": "👑 3.0x 核心", "weight": 3.0, "role": "算力总舵手"},
    "AAPL": {"name": "苹果", "weight_desc": "👑 3.0x 核心", "weight": 3.0, "role": "消费电子/中枢"},
    "MSFT": {"name": "微软", "weight_desc": "👑 3.0x 核心", "weight": 3.0, "role": "云端权重底座"},
    "AMZN": {"name": "亚马逊", "weight_desc": "🏛️ 2.0x 中枢", "weight": 2.0, "role": "电商与云"},
    "GOOGL": {"name": "谷歌", "weight_desc": "🏛️ 2.0x 中枢", "weight": 2.0, "role": "搜索广告"},
    "META": {"name": "Meta", "weight_desc": "🏛️ 2.0x 中枢", "weight": 2.0, "role": "社交生态"},
    "TSLA": {"name": "特斯拉", "weight_desc": "🏛️ 2.0x 中枢", "weight": 2.0, "role": "流动性先锋"},
    "AVGO": {"name": "博通", "weight_desc": "🏛️ 2.0x 中枢", "weight": 2.0, "role": "网络芯片核心"},
    "MU": {"name": "美光", "weight_desc": "🚀 1.0x 先锋", "weight": 1.0, "role": "存储/HBM龙头"},
    "AMD": {"name": "AMD", "weight_desc": "🚀 1.0x 先锋", "weight": 1.0, "role": "算力二当家"},
    "WDC": {"name": "西部数据", "weight_desc": "🚀 1.0x 先锋", "weight": 1.0, "role": "存储与硬盘"},
    "STX": {"name": "希捷", "weight_desc": "🚀 1.0x 先锋", "weight": 1.0, "role": "企业级存储"},
    "SNDK": {"name": "闪迪", "weight_desc": "🚀 1.0x 先锋", "weight": 1.0, "role": "存储情绪标的"},
}

ALL_SYMBOLS = ["QQQ"] + list(TICKERS_CONFIG.keys())


def fetch_from_tiingo_5m(ticker):
    try:
        start_date = (datetime.datetime.now(tz_ny) - datetime.timedelta(days=5)).strftime("%Y-%m-%d")
        url = f"https://api.tiingo.com/iex/{ticker}/prices?startDate={start_date}&resampleFreq=5min&token={TIINGO_TOKEN}&columns=open,high,low,close,volume"
        resp = requests.get(url, headers={"Content-Type": "application/json"}, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            if data and isinstance(data, list) and len(data) > 0:
                df = pd.DataFrame(data)
                df["date"] = pd.to_datetime(df["date"])
                df.set_index("date", inplace=True)
                df.rename(columns={"open": "Open", "high": "High", "low": "Low", "close": "Close", "volume": "Volume"}, inplace=True)
                df = df[["Open", "High", "Low", "Close", "Volume"]].dropna().sort_index()
                if not df.empty:
                    df.index = df.index.tz_localize("UTC").tz_convert(tz_ny) if df.index.tz is None else df.index.tz_convert(tz_ny)
                    return df
    except Exception:
        pass
    return None


@st.cache_data(ttl=180)
def fetch_radar_data_advanced():
    data_5m, data_daily = {}, {}
    for sym in ALL_SYMBOLS:
        df_5m = fetch_from_tiingo_5m("SNDK") if sym == "SNDK" else None
        if df_5m is None or df_5m.empty:
            try:
                ticker = yf.Ticker(sym)
                df_yf = ticker.history(period="5d", interval="5m", prepost=True)
                if df_yf is not None and not df_yf.empty:
                    if isinstance(df_yf.columns, pd.MultiIndex):
                        df_yf.columns = df_yf.columns.get_level_values(0)
                    sub = df_yf[["Open", "High", "Low", "Close", "Volume"]].dropna(subset=["Close"]).copy()
                    if not sub.empty:
                        sub.index = sub.index.tz_localize("UTC").tz_convert(tz_ny) if sub.index.tz is None else sub.index.tz_convert(tz_ny)
                        df_5m = sub
            except Exception:
                pass
        if df_5m is not None and not df_5m.empty:
            data_5m[sym] = df_5m

        try:
            ticker = yf.Ticker(sym)
            df_1d = ticker.history(period="1mo", interval="1d")
            if df_1d is not None and not df_1d.empty:
                if isinstance(df_1d.columns, pd.MultiIndex):
                    df_1d.columns = df_1d.columns.get_level_values(0)
                sub_1d = df_1d[["Open", "High", "Low", "Close", "Volume"]].dropna(subset=["Close"]).copy()
                if not sub_1d.empty:
                    data_daily[sym] = sub_1d
        except Exception:
            pass

    return data_5m, data_daily


def compute_radar_facts_integrated(data_5m, data_daily):
    if "QQQ" not in data_5m or data_5m["QQQ"].empty:
        return None

    qqq_5m = data_5m["QQQ"]
    latest_ts_ny = qqq_5m.index[-1]
    latest_date_ny = latest_ts_ny.date()
    day_slice = {sym: df[df.index.date == latest_date_ny].copy() for sym, df in data_5m.items() if not df.empty}
    if "QQQ" not in day_slice or day_slice["QQQ"].empty:
        return None

    qqq_df = day_slice["QQQ"]
    qqq_base = float(qqq_df["Open"].iloc[0])
    qqq_curr = float(qqq_df["Close"].iloc[-1])
    qqq_high = float(qqq_df["High"].max())
    qqq_low = float(qqq_df["Low"].min())
    qqq_chg = ((qqq_curr - qqq_base) / qqq_base) * 100

    atr_used_pct = 0.0
    if "QQQ" in data_daily and len(data_daily["QQQ"]) >= 14:
        d_df = data_daily["QQQ"]
        tr = np.maximum(d_df["High"] - d_df["Low"], np.maximum((d_df["High"] - d_df["Close"].shift(1)).abs(), (d_df["Low"] - d_df["Close"].shift(1)).abs()))
        atr_1d_val = float(tr.rolling(14).mean().iloc[-1])
        if atr_1d_val > 0:
            atr_used_pct = ((qqq_high - qqq_low) / atr_1d_val) * 100

    bull_count, bear_count = 0, 0
    stock_cards = []

    for sym, cfg in TICKERS_CONFIG.items():
        w = cfg["weight"]
        found = False

        if sym in day_slice and len(day_slice[sym]) > 0:
            s_df = day_slice[sym]
            b_p = float(s_df["Open"].iloc[0])
            c_p = float(s_df["Close"].iloc[-1])
            if b_p > 0 and not np.isnan(b_p) and not np.isnan(c_p):
                chg = ((c_p - b_p) / b_p) * 100
                spread = chg - qqq_chg
                found = True

                if spread >= 0:
                    bull_count += 1
                    status_tag = "🟢 水上领跑"
                    border_color = "#10B981"
                    action_txt = "【主力单独拉升护盘】" if spread >= 0.3 else "【小幅强于大盘】"
                else:
                    bear_count += 1
                    status_tag = "🔴 水下抛售"
                    border_color = "#EF4444"
                    action_txt = "🚨【主力放量杀跌砸盘】" if spread <= -0.4 else "【水下跟随下挫】"

                stock_cards.append({
                    "sym": sym,
                    "name": cfg["name"],
                    "role": cfg["role"],
                    "weight_desc": cfg["weight_desc"],
                    "price": c_p,
                    "chg": chg,
                    "spread": spread,
                    "status_tag": status_tag,
                    "border_color": border_color,
                    "action_txt": action_txt,
                })

        # 保底机制（确保 SNDK 及任何数据延迟标的 100% 渲染卡片）
        if not found:
            bear_count += 1
            stock_cards.append({
                "sym": sym,
                "name": cfg["name"],
                "role": cfg["role"],
                "weight_desc": cfg["weight_desc"],
                "price": 0.0,
                "chg": 0.0,
                "spread": -0.01,
                "status_tag": "⚪ 同步整理",
                "border_color": "#4B5563",
                "action_txt": "【盘前数据同步中】",
            })

    # 按强弱排序
    stock_cards.sort(key=lambda x: x["spread"], reverse=True)

    return {
        "timestamp_myt": latest_ts_ny.astimezone(tz_myt).strftime("%Y-%m-%d %H:%M MYT"),
        "qqq_curr": qqq_curr,
        "qqq_chg": qqq_chg,
        "atr_used_pct": atr_used_pct,
        "bull_count": bull_count,
        "bear_count": bear_count,
        "stock_cards": stock_cards
    }


def render_macro_radar_tab():
    st.subheader("📡 13 核心标的资金状态卡片流 (大白话实操罗盘)")

    if st.button("🔄 刷新最新主力资金卡片", key="btn_refresh_cards_final"):
        st.cache_data.clear()
        st.rerun()

    with st.spinner("正在提取 13 核心标的资金状态卡片数据..."):
        d_5m, d_daily = fetch_radar_data_advanced()

    res = compute_radar_facts_integrated(d_5m, d_daily)
    if not res:
        st.warning("行情连接中，请稍后点击上方刷新。")
        return

    bull_cnt = res["bull_count"]
    bear_cnt = res["bear_count"]
    atr_used = res["atr_used_pct"]

    # 1. 顶层：大白话最终决策大卡片
    if atr_used >= 100:
        d_title = "🚨 最终判决：日内波动空间已打满 (≥100%)"
        d_reason = "今日能量已释放完毕，后续将进入极窄垃圾横盘期。"
        d_action = "【实操建议】：今晚 22:00-24:00 严禁追单，严格空仓防守！"
        d_color = "#EF4444"
    elif bull_cnt >= 9:
        d_title = "🟢 最终判决：主力真金白银拉升 (多头绝对占优)"
        d_reason = f"全场有 {bull_cnt}/13 只科技股处于水上领跑状态，芯片与巨头合力进攻。"
        d_action = "【实操建议】：踩到 1H 支撑战区 (RBS) 放心买入 CALL，做多胜率极高！"
        d_color = "#10B981"
    elif bear_cnt >= 8:
        d_title = "🚨 最终判决：主力大举砸盘出逃 (严禁追多！)"
        d_reason = f"全场有 {bear_cnt}/13 只科技股深潜水下，只有 1-2 只巨头在护盘演戏，属于典型诱多陷阱。"
        d_action = "【实操建议】：绝对不开 CALL，反弹到阻力战区 (SBR/PMH) 专等 2B 假突破做空 (PUT)！"
        d_color = "#EF4444"
    else:
        d_title = "🟡 最终判决：多空力量胶着 (震荡防守)"
        d_reason = f"多头 {bull_cnt} 家 vs 空头 {bear_cnt} 家，主力资金分化严重，未形成合力。"
        d_action = "【实操建议】：无确定性大单边，严格等待战区边缘与 2B 扫损确认。"
        d_color = "#F59E0B"

    st.markdown(f"""
    <div style='background-color:#111827; border:3px solid {d_color}; border-radius:12px; padding:18px 24px; margin-bottom:20px;'>
        <div style='font-size:22px; font-weight:900; color:{d_color};'>{d_title}</div>
        <div style='font-size:14px; color:#E5E7EB; margin-top:8px;'><b>原因解析</b>: {d_reason}</div>
        <div style='font-size:15px; font-weight:700; color:#FCD34D; margin-top:8px;'>{d_action}</div>
    </div>
    """, unsafe_allow_html=True)

    # 2. 第二层：四大宏观事实指标卡
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("🎯 QQQ 现价", f"${res['qqq_curr']:.2f}", f"{res['qqq_chg']:+.2f}%")
    m2.metric("🔋 ATR 波幅消耗", f"{atr_used:.1f}%", "🚨 空间耗尽" if atr_used >= 100 else "动能充沛")
    m3.metric("🟢 主力买入 (水上)", f"{bull_cnt} 只", f"占比 {(bull_cnt/13)*100:.0f}%")
    m4.metric("🔴 主力抛售 (水下)", f"{bear_cnt} 只", f"占比 {(bear_cnt/13)*100:.0f}%")

    st.markdown("---")

    # 3. 第三层：13 只标的独立卡片流矩阵 (3 列自适应排列)
    st.markdown("#### 📋 13 核心标的即时状态卡片矩阵 (从强到弱排布)")

    cols = st.columns(3)
    for idx, card in enumerate(res["stock_cards"]):
        col_idx = idx % 3
        with cols[col_idx]:
            p_str = f"${card['price']:.2f}" if card['price'] > 0 else "同步中"
            chg_str = f"{card['chg']:+.2f}%" if card['price'] > 0 else "-"
            chg_color = "#10B981" if card['chg'] >= 0 else "#EF4444"

            st.markdown(f"""
            <div style='background:rgba(22, 27, 34, 0.85); border:1.5px solid {card["border_color"]}; border-radius:10px; padding:12px 14px; margin-bottom:14px; box-shadow:0 4px 6px -1px rgba(0,0,0,0.3);'>
                <div style='display:flex; justify-content:space-between; align-items:center;'>
                    <span style='font-size:16px; font-weight:800; color:#F9FAFB;'>{card["sym"]} <span style='font-size:13px; color:#9CA3AF;'>({card["name"]})</span></span>
                    <span style='font-size:11px; font-weight:700; color:#93C5FD; background:#1E3A8A; padding:2px 6px; border-radius:4px;'>{card["weight_desc"]}</span>
                </div>
                <div style='margin-top:6px; display:flex; justify-content:space-between; align-items:center;'>
                    <span style='font-size:12px; color:#9CA3AF;'>现价: <b style='color:#F3F4F6;'>{p_str}</b></span>
                    <span style='font-size:13px; font-weight:700; color:{chg_color};'>{chg_str}</span>
                </div>
                <div style='margin-top:4px; font-size:11px; color:#D1D5DB;'>
                    <b>相对大盘</b>: <span style='color:{card["border_color"]}; font-weight:700;'>{card["spread"]:+.2f}%</span>
                </div>
                <div style='margin-top:8px; padding-top:6px; border-top:1px dashed #374151; font-size:12px; font-weight:700; color:{card["border_color"]};'>
                    {card["action_txt"]}
                </div>
            </div>
            """, unsafe_allow_html=True)
