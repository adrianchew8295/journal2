# 文件名: macro_radar_plugin.py
# 作用: 旗舰级交互式资金轮动看板 (支持 4 象限资金轮动 + 加权双浪 + 智能白话结论)

import datetime
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import pytz
import requests
import streamlit as st
import yfinance as yf

tz_ny = pytz.timezone("America/New_York")
tz_myt = pytz.timezone("Asia/Kuala_Lumpur")

TIINGO_TOKEN = "bcffe3a5cf7eeef085e405cfa4a3e5691b976217"

# 13 核心标的配置
TICKERS_CONFIG = {
    "NVDA": {"name": "英伟达", "tier": "巨头", "weight": 3.0, "role": "AI算力总舵手"},
    "AAPL": {"name": "苹果", "tier": "巨头", "weight": 3.0, "role": "消费电子/防守中枢"},
    "MSFT": {"name": "微软", "tier": "巨头", "weight": 3.0, "role": "云端权重底座"},
    "AMZN": {"name": "亚马逊", "tier": "巨头", "weight": 2.0, "role": "电商与云权重"},
    "GOOGL": {"name": "谷歌", "tier": "巨头", "weight": 2.0, "role": "搜索广告权重"},
    "META": {"name": "Meta", "tier": "巨头", "weight": 2.0, "role": "社交开源生态"},
    "TSLA": {"name": "特斯拉", "tier": "巨头", "weight": 2.0, "role": "流动性先锋"},
    "AVGO": {"name": "博通", "tier": "先锋", "weight": 2.0, "role": "网络与芯片核心"},
    "MU": {"name": "美光", "tier": "先锋", "weight": 1.0, "role": "存储/HBM龙头"},
    "AMD": {"name": "AMD", "tier": "先锋", "weight": 1.0, "role": "算力二当家"},
    "WDC": {"name": "西部数据", "tier": "先锋", "weight": 1.0, "role": "存储与硬盘"},
    "STX": {"name": "希捷", "tier": "先锋", "weight": 1.0, "role": "企业级存储"},
    "SNDK": {"name": "闪迪", "tier": "先锋", "weight": 1.0, "role": "存储情绪标的"},
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
    data_5m, data_daily, data_weekly = {}, {}, {}
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
            df_1d = ticker.history(period="3mo", interval="1d")
            if df_1d is not None and not df_1d.empty:
                if isinstance(df_1d.columns, pd.MultiIndex):
                    df_1d.columns = df_1d.columns.get_level_values(0)
                sub_1d = df_1d[["Open", "High", "Low", "Close", "Volume"]].dropna(subset=["Close"]).copy()
                if not sub_1d.empty: data_daily[sym] = sub_1d

            df_1w = ticker.history(period="6mo", interval="1wk")
            if df_1w is not None and not df_1w.empty:
                if isinstance(df_1w.columns, pd.MultiIndex):
                    df_1w.columns = df_1w.columns.get_level_values(0)
                sub_1w = df_1w[["Open", "High", "Low", "Close", "Volume"]].dropna(subset=["Close"]).copy()
                if not sub_1w.empty: data_weekly[sym] = sub_1w
        except Exception:
            pass

    return data_5m, data_daily, data_weekly


def compute_radar_facts_integrated(data_5m, data_daily, data_weekly):
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
    qqq_norm = (qqq_df["Close"] / qqq_base) * 100

    atr_used_pct = 0.0
    atr_1d_val = 4.0
    if "QQQ" in data_daily and len(data_daily["QQQ"]) >= 14:
        d_df = data_daily["QQQ"]
        tr = np.maximum(d_df["High"] - d_df["Low"], np.maximum((d_df["High"] - d_df["Close"].shift(1)).abs(), (d_df["Low"] - d_df["Close"].shift(1)).abs()))
        atr_1d_val = float(tr.rolling(14).mean().iloc[-1])
        if atr_1d_val > 0:
            atr_used_pct = ((qqq_high - qqq_low) / atr_1d_val) * 100

    t1_series_list, t1_weights = [], []
    t2_series_list, t2_weights = [], []
    facts_table = []
    above_qqq_count = 0
    total_active = 0

    for sym, cfg in TICKERS_CONFIG.items():
        w = cfg["weight"]
        has_valid_data = False

        if sym in day_slice and len(day_slice[sym]) > 0:
            s_df = day_slice[sym]
            b_p = float(s_df["Open"].iloc[0])
            c_p = float(s_df["Close"].iloc[-1])
            
            if b_p > 0 and not np.isnan(b_p) and not np.isnan(c_p):
                chg = ((c_p - b_p) / b_p) * 100
                s_norm = (s_df["Close"] / b_p) * 100
                spread = (s_norm - qqq_norm).dropna()

                if not spread.empty:
                    latest_sp = float(spread.iloc[-1])
                    if not np.isnan(latest_sp):
                        has_valid_data = True
                        vol_ratio = 1.0
                        d_ma50 = c_p
                        if sym in data_daily and len(data_daily[sym]) >= 5:
                            avg_vol = float(data_daily[sym]["Volume"].iloc[-20:].mean())
                            cum_vol = float(s_df["Volume"].sum())
                            vol_ratio = cum_vol / (avg_vol * (len(s_df) / 78)) if avg_vol > 0 else 1.0
                            if len(data_daily[sym]) >= 50:
                                d_ma50 = float(data_daily[sym]["Close"].rolling(50).mean().iloc[-1])

                        pwl_val = c_p * 0.95
                        if sym in data_weekly and len(data_weekly[sym]) >= 2:
                            pwl_val = float(data_weekly[sym]["Low"].iloc[-2])

                        if cfg["tier"] == "巨头":
                            t1_series_list.append(spread * w)
                            t1_weights.append(w)
                        else:
                            t2_series_list.append(spread * w)
                            t2_weights.append(w)

                        if latest_sp >= 0:
                            above_qqq_count += 1
                        total_active += 1

                        is_near_pwl = (c_p <= pwl_val * 1.015)
                        if latest_sp >= 0.2 and vol_ratio >= 1.25:
                            action_tag = "🟢 放量领跑"
                            quadrant = "真拉升龙头"
                        elif latest_sp <= -0.5 and vol_ratio >= 1.5:
                            action_tag = "🔴 坚决出逃"
                            quadrant = "放量砸盘"
                        elif latest_sp >= 0:
                            action_tag = "🟡 弱势护盘"
                            quadrant = "水上震荡"
                        else:
                            action_tag = "⚪ 水下跟跌"
                            quadrant = "弱势跟跌"

                        facts_table.append({
                            "Ticker": sym,
                            "Name": cfg["name"],
                            "Tier": cfg["tier"],
                            "Weight_Num": w,
                            "Weight": f"{w:.1f}x",
                            "Price": round(c_p, 2),
                            "ChangePct": round(chg, 2),
                            "SpreadVsQQQ": round(latest_sp, 2),
                            "VolumeRatio": round(vol_ratio, 2),
                            "BubbleSize": max(min(vol_ratio * 18, 55), 14),
                            "ActionTag": action_tag,
                            "Quadrant": quadrant
                        })

        if not has_valid_data:
            facts_table.append({
                "Ticker": sym, "Name": cfg["name"], "Tier": cfg["tier"], "Weight_Num": w, "Weight": f"{w:.1f}x",
                "Price": 0.0, "ChangePct": 0.0, "SpreadVsQQQ": 0.0, "VolumeRatio": 0.0, "BubbleSize": 12,
                "ActionTag": "⚪ 待同步", "Quadrant": "离线"
            })

    t1_wave = (pd.concat(t1_series_list, axis=1).sum(axis=1) / sum(t1_weights)).dropna() if t1_series_list else pd.Series(dtype=float)
    t2_wave = (pd.concat(t2_series_list, axis=1).sum(axis=1) / sum(t2_weights)).dropna() if t2_series_list else pd.Series(dtype=float)

    df_clean = pd.DataFrame(facts_table)
    df_clean["SpreadVsQQQ"] = pd.to_numeric(df_clean["SpreadVsQQQ"], errors="coerce").fillna(0.0)

    return {
        "timestamp_ny": latest_ts_ny.strftime("%Y-%m-%d %H:%M ET"),
        "timestamp_myt": latest_ts_ny.astimezone(tz_myt).strftime("%Y-%m-%d %H:%M MYT"),
        "qqq_curr": qqq_curr,
        "qqq_chg": qqq_chg,
        "above_count": above_qqq_count,
        "total_active": max(total_active, 1),
        "atr_used_pct": atr_used_pct,
        "atr_1d_val": atr_1d_val,
        "t1_wave": t1_wave,
        "t2_wave": t2_wave,
        "df_facts": df_clean
    }


def render_macro_radar_tab():
    st.subheader("📡 13 标的资金轮动与宏观罗盘 (Interactive Visual Hub)")

    if st.button("🔄 刷新最新主力轮动事实", key="btn_refresh_radar_interactive"):
        st.cache_data.clear()
        st.rerun()

    with st.spinner("正在提取 13 标的高频数据与资金轮动坐标..."):
        d_5m, d_1d, d_1w = fetch_radar_data_advanced()

    res = compute_radar_facts_integrated(d_5m, d_1d, d_1w)
    if not res:
        st.warning("行情连接中，请稍后刷新。")
        return

    t1_now = float(res["t1_wave"].iloc[-1]) if not res["t1_wave"].empty else 0.0
    t2_now = float(res["t2_wave"].iloc[-1]) if not res["t2_wave"].empty else 0.0
    atr_used = res["atr_used_pct"]
    above_cnt = res["above_count"]

    # 1. 大白话实操决策卡片（一眼看懂今晚干什么）
    if atr_used >= 100:
        decision_box = ("🚨 严禁追单 (空间已打满)", "#EF4444", "今日波动范围已耗尽 100% 以上，后续以垃圾震荡为主，严格空仓。")
    elif t2_now > 0 and t2_now > t1_now and above_cnt >= 8:
        decision_box = ("🟢 放心做多 (真突破拉升)", "#10B981", "芯片先锋真金白银带头领涨，多头配合度极高，踩战区支撑可开 CALL。")
    elif t2_now < -0.3 and above_cnt <= 4:
        decision_box = ("🚨 坚决不做多 (诱多/掩护出货)", "#EF4444", "芯片正在水下被大单抛售，大盘全靠 1-2 只巨头硬撑，开 CALL 必被套，只找 2B 做空！")
    else:
        decision_box = ("🟡 观望防守 (中性轮动)", "#F59E0B", "多空力量分化，市场处于拉锯中，严格等待战区边界与 2B 扫损确认。")

    st.markdown(f"""
    <div style='background:rgba(15,23,42,0.85); border:2px solid {decision_box[1]}; border-radius:10px; padding:12px 18px; margin-bottom:12px;'>
        <span style='font-size:16px; font-weight:800; color:{decision_box[1]};'>{decision_box[0]}</span>
        <span style='font-size:13px; color:#E2E8F0; margin-left:12px;'>{decision_box[2]}</span>
    </div>
    """, unsafe_allow_html=True)

    # 2. 顶部指标栏
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("🎯 QQQ 现价", f"${res['qqq_curr']:.2f}", f"{res['qqq_chg']:+.2f}%")
    k2.metric("🔋 日内 ATR 能耗", f"{atr_used:.1f}%", "🚨 耗尽" if atr_used >= 100 else "动能充沛")
    k3.metric("🏛️ 巨头防守浪 (加权)", f"{t1_now:+.2f}%", "水上护盘" if t1_now >= 0 else "水下砸盘")
    k4.metric("🚀 芯片先锋浪 (加权)", f"{t2_now:+.2f}%", "🔥 真进攻" if t2_now > 0 else "🚨 资金出逃")

    st.markdown("---")

    # 3. 核心视觉区：资金轮动四象限图 (鼠标悬停即可交互)
    col_chart1, col_chart2 = st.columns([1.5, 1])

    with col_chart1:
        st.markdown("#### 🧭 13 标的资金轮动四象限交互图 (可缩放/悬停穿透)")
        df_plot = res["df_facts"].copy()
        
        # 气泡散点图
        fig_quad = go.Figure()

        # 添加四象限背景底色提示
        fig_quad.add_hline(y=0, line_width=1.5, line_color="#E2E8F0", line_dash="solid")
        fig_quad.add_vline(x=2.0, line_width=1.0, line_color="#475569", line_dash="dash")

        # 区分多空颜色
        for _, row in df_plot.iterrows():
            c_color = "#10B981" if row["SpreadVsQQQ"] >= 0 else "#EF4444"
            fig_quad.add_trace(go.Scatter(
                x=[row["Weight_Num"]],
                y=[row["SpreadVsQQQ"]],
                mode="markers+text",
                name=row["Ticker"],
                text=[f"<b>{row['Ticker']}</b><br>({row['Name']})"],
                textposition="top center",
                textfont=dict(size=10, color="#FFFFFF", family="Consolas"),
                marker=dict(
                    size=[row["BubbleSize"]],
                    color=c_color,
                    opacity=0.85,
                    line=dict(width=1.5, color="#FFFFFF")
                ),
                hovertemplate=f"<b>{row['Ticker']} ({row['Name']})</b><br>" +
                              f"角色: {row['Tier']} (权重: {row['Weight']})<br>" +
                              f"现价: ${row['Price']} ({row['ChangePct']:+.2f}%)<br>" +
                              f"相对大盘差值: <b>{row['SpreadVsQQQ']:+.2f}%</b><br>" +
                              f"成交量比: <b>{row['VolumeRatio']}x</b><br>" +
                              f"实操动作: <b>{row['ActionTag']}</b><extra></extra>"
            ))

        fig_quad.update_layout(
            height=400,
            margin=dict(l=10, r=10, t=10, b=10),
            template="plotly_dark",
            paper_bgcolor="#0B0F19",
            plot_bgcolor="#0B0F19",
            xaxis=dict(
                title="市场权重等级 (1.0x 轻量情绪先锋 ──► 3.0x 核心定海神针)",
                tickvals=[1.0, 2.0, 3.0],
                ticktext=["1.0x (小票先锋)", "2.0x (中枢巨头)", "3.0x (核心巨头)"],
                gridcolor="#1E293B", zeroline=False
            ),
            yaxis=dict(
                title="相对 QQQ 强弱差值 (%) [水上买盘 ──► 水下抛盘]",
                gridcolor="#1E293B", zerolinecolor="#64748B"
            ),
            showlegend=False
        )
        st.plotly_chart(fig_quad, use_container_width=True)

    with col_chart2:
        st.markdown("#### 🏆 强弱力量天平 (即时排布)")
        df_bar = res["df_facts"].sort_values(by="SpreadVsQQQ", ascending=True)
        bar_colors = ["#10B981" if x >= 0 else "#EF4444" for x in df_bar["SpreadVsQQQ"]]

        fig_bar = go.Figure()
        fig_bar.add_trace(go.Bar(
            y=df_bar["Ticker"] + " (" + df_bar["Name"] + ")",
            x=df_bar["SpreadVsQQQ"],
            orientation="h",
            marker=dict(color=bar_colors),
            text=[f"{sp:+.2f}%" for sp in df_bar["SpreadVsQQQ"]],
            textposition="outside",
            hovertemplate="<b>%{y}</b><br>偏离差值: %{x:+.2f}%<extra></extra>"
        ))
        fig_bar.update_layout(
            height=400,
            margin=dict(l=5, r=25, t=10, b=5),
            template="plotly_dark",
            paper_bgcolor="#0B0F19",
            plot_bgcolor="#0B0F19",
            xaxis=dict(title="相对 QQQ 差值 (%)", gridcolor="#1E293B", zerolinecolor="#FFFFFF")
        )
        st.plotly_chart(fig_bar, use_container_width=True)

    st.markdown("---")

    # 4. 13 标的客观状态清单
    st.markdown("#### 📋 13 标的即时清单 (带大白话动作)")
    st.dataframe(
        df_plot[["Ticker", "Name", "Tier", "Weight", "Price", "ChangePct", "SpreadVsQQQ", "VolumeRatio", "ActionTag"]].sort_values(by="SpreadVsQQQ", ascending=False),
        use_container_width=True,
        hide_index=True
    )
