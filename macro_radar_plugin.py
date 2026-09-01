# 文件名: macro_radar_plugin.py
# 作用: 13 标的多空拔河罗盘 (SNDK 永久保底显示 + 极简 1 秒大白话决策)

import datetime
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import pytz
import requests
import streamlit as st
import yfinance as yf

tz_ny = pytz.timezone("America/New_York")
tz_myt = pytz.timezone("Asia/Kuala_Lumpur")

TIINGO_TOKEN = "bcffe3a5cf7eeef085e405cfa4a3e5691b976217"

TICKERS_CONFIG = {
    "NVDA": {"name": "英伟达", "weight_desc": "👑 3.0x 核心", "weight": 3.0},
    "AAPL": {"name": "苹果", "weight_desc": "👑 3.0x 核心", "weight": 3.0},
    "MSFT": {"name": "微软", "weight_desc": "👑 3.0x 核心", "weight": 3.0},
    "AMZN": {"name": "亚马逊", "weight_desc": "🏛️ 2.0x 中枢", "weight": 2.0},
    "GOOGL": {"name": "谷歌", "weight_desc": "🏛️ 2.0x 中枢", "weight": 2.0},
    "META": {"name": "Meta", "weight_desc": "🏛️ 2.0x 中枢", "weight": 2.0},
    "TSLA": {"name": "特斯拉", "weight_desc": "🏛️ 2.0x 中枢", "weight": 2.0},
    "AVGO": {"name": "博通", "weight_desc": "🏛️ 2.0x 中枢", "weight": 2.0},
    "MU": {"name": "美光", "weight_desc": "🚀 1.0x 先锋", "weight": 1.0},
    "AMD": {"name": "AMD", "weight_desc": "🚀 1.0x 先锋", "weight": 1.0},
    "WDC": {"name": "西部数据", "weight_desc": "🚀 1.0x 先锋", "weight": 1.0},
    "STX": {"name": "希捷", "weight_desc": "🚀 1.0x 先锋", "weight": 1.0},
    "SNDK": {"name": "闪迪", "weight_desc": "🚀 1.0x 先锋", "weight": 1.0},
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

    bull_power, bear_power = 0.0, 0.0
    stock_rows = []

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
                    bull_power += w
                    status_icon = "🟢"
                    action_txt = "【主力买入 / 强于大盘】" if spread >= 0.3 else "【小幅护盘】"
                else:
                    bear_power += w
                    status_icon = "🔴"
                    action_txt = "🚨【主力放量砸盘】" if spread <= -0.5 else "【水下跟跌】"

                stock_rows.append({
                    "状态": status_icon,
                    "代码": sym,
                    "公司": cfg["name"],
                    "影响力权重": cfg["weight_desc"],
                    "现价 ($)": round(c_p, 2),
                    "今日涨跌": f"{chg:+.2f}%",
                    "相对大盘差值": round(spread, 2),
                    "白话实操动作": action_txt,
                    "Weight": w
                })

        # 保底机制：若接口数据延迟，依然强制加入列表显示
        if not found:
            bear_power += (w * 0.5)
            stock_rows.append({
                "状态": "⚪",
                "代码": sym,
                "公司": cfg["name"],
                "影响力权重": cfg["weight_desc"],
                "现价 ($)": 0.00,
                "今日涨跌": "0.00%",
                "相对大盘差值": -0.01,
                "白话实操动作": "【盘前数据同步中】",
                "Weight": w
            })

    df_result = pd.DataFrame(stock_rows).sort_values(by="相对大盘差值", ascending=False)
    total_power = max(bull_power + bear_power, 1.0)
    bull_pct = (bull_power / total_power) * 100
    bear_pct = (bear_power / total_power) * 100

    return {
        "timestamp_myt": latest_ts_ny.astimezone(tz_myt).strftime("%Y-%m-%d %H:%M MYT"),
        "qqq_curr": qqq_curr,
        "qqq_chg": qqq_chg,
        "atr_used_pct": atr_used_pct,
        "bull_power": bull_power,
        "bear_power": bear_power,
        "bull_pct": bull_pct,
        "bear_pct": bear_pct,
        "df_result": df_result
    }


def render_macro_radar_tab():
    st.subheader("📡 13 核心标的多空拔河罗盘 (1秒看懂主力意图)")

    if st.button("🔄 刷新最新主力拔河战况", key="btn_refresh_tug_of_war_v2"):
        st.cache_data.clear()
        st.rerun()

    with st.spinner("正在提取 13 标的最新多空拔河数据..."):
        d_5m, d_daily = fetch_radar_data_advanced()

    res = compute_radar_facts_integrated(d_5m, d_daily)
    if not res:
        st.warning("行情连接中，请稍后点击上方刷新。")
        return

    bull_p = res["bull_pct"]
    bear_p = res["bear_pct"]
    atr_used = res["atr_used_pct"]

    # 1. 最终白话大字判决条
    if atr_used >= 100:
        verdict_title = "🚨 最终判决：今日波动空间已耗尽 (≥100%)"
        verdict_sub = "能量已放完，后面全是垃圾震荡，今晚严格空仓睡觉！"
        v_color = "#EF4444"
    elif bull_p >= 70:
        verdict_title = "🟢 最终判决：主力真金白银拉升 (多头绝对占优)"
        verdict_sub = "大部分科技股都在带头大涨，多头配合度极高，踩到支撑位放心买 CALL！"
        v_color = "#10B981"
    elif bear_p >= 65:
        verdict_title = "🚨 最终判决：主力大举砸盘出逃 (严禁做多！)"
        verdict_sub = "只有 1-2 只巨头在硬撑门面，芯片科技股全在水下杀跌，买 CALL 必被套，专等 2B 破位做空！"
        v_color = "#EF4444"
    else:
        verdict_title = "🟡 最终判决：多空力量五五开 (横盘拉锯)"
        verdict_sub = "主力意见不统一，没有单边大行情，严格按战区纪律防守。"
        v_color = "#F59E0B"

    st.markdown(f"""
    <div style='background-color:#111827; border:3px solid {v_color}; border-radius:12px; padding:16px 20px; margin-bottom:20px; text-align:center;'>
        <div style='font-size:22px; font-weight:900; color:{v_color};'>{verdict_title}</div>
        <div style='font-size:14px; color:#F3F4F6; margin-top:6px;'>{verdict_sub}</div>
    </div>
    """, unsafe_allow_html=True)

    # 2. 拔河计分板柱状图
    st.markdown("#### ⚖️ 今日多空力量拔河对比条")
    fig_bar = go.Figure()

    fig_bar.add_trace(go.Bar(
        y=["主力拔河力量"], x=[res["bull_power"]],
        name=f"🟢 多头做多力量 ({bull_p:.0f}%)",
        orientation="h",
        marker=dict(color="#10B981"),
        text=[f"🟢 多头: {bull_p:.0f}%"],
        textposition="inside",
        insidetextanchor="middle"
    ))

    fig_bar.add_trace(go.Bar(
        y=["主力拔河力量"], x=[res["bear_power"]],
        name=f"🔴 空头砸盘力量 ({bear_p:.0f}%)",
        orientation="h",
        marker=dict(color="#EF4444"),
        text=[f"🔴 空头: {bear_p:.0f}%"],
        textposition="inside",
        insidetextanchor="middle"
    ))

    fig_bar.update_layout(
        barmode="stack",
        height=130,
        margin=dict(l=10, r=10, t=10, b=10),
        template="plotly_dark",
        paper_bgcolor="#0B0F19",
        plot_bgcolor="#0B0F19",
        xaxis=dict(showgrid=False, showticklabels=False, zeroline=False),
        yaxis=dict(showticklabels=False),
        legend=dict(orientation="h", yanchor="bottom", y=1.05, xanchor="center", x=0.5, font=dict(size=13, color="#FFFFFF"))
    )
    st.plotly_chart(fig_bar, use_container_width=True, config={"displayModeBar": False})

    st.markdown("---")

    # 3. 13 标的完整站队清单
    st.markdown("#### 📋 13 核心标的即时站队表 (从最强到最弱)")
    df_show = res["df_result"][["状态", "代码", "公司", "影响力权重", "现价 ($)", "今日涨跌", "白话实操动作"]]
    st.dataframe(df_show, use_container_width=True, hide_index=True)
