# 文件名: macro_radar_plugin.py
# 作用: 彭博终端级 13 核心标的强弱雷达 (聚合双轨 + 横向龙虎榜 + 手机自适应)

import datetime
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pytz
import streamlit as st
import yfinance as yf

tz_ny = pytz.timezone("America/New_York")
tz_myt = pytz.timezone("Asia/Kuala_Lumpur")

TICKERS_CONFIG = {
    "NVDA": {"name": "NVIDIA", "tier": "巨头", "role": "AI算力总舵手"},
    "AAPL": {"name": "Apple", "tier": "巨头", "role": "消费电子/防守指标"},
    "MSFT": {"name": "Microsoft", "tier": "巨头", "role": "云端定海神针"},
    "AMZN": {"name": "Amazon", "tier": "巨头", "role": "电商与云权重"},
    "GOOGL": {"name": "Alphabet", "tier": "巨头", "role": "搜索广告权重"},
    "TSLA": {"name": "Tesla", "tier": "巨头", "role": "流动性与情绪先锋"},
    "META": {"name": "Meta", "tier": "巨头", "role": "社交开源生态"},
    "MU": {"name": "Micron", "tier": "先锋", "role": "存储/HBM龙头"},
    "AMD": {"name": "AMD", "tier": "先锋", "role": "算力二当家"},
    "AVGO": {"name": "Broadcom", "tier": "先锋", "role": "ASIC与网络龙头"},
    "WDC": {"name": "Western Digital", "tier": "先锋", "role": "存储与硬盘"},
    "STX": {"name": "Seagate", "tier": "先锋", "role": "数据中心存储"},
    "SNDK": {"name": "SanDisk", "tier": "先锋", "role": "存储情绪标的"},
}

ALL_SYMBOLS = ["QQQ"] + list(TICKERS_CONFIG.keys())


@st.cache_data(ttl=300)
def fetch_radar_clean_data():
    data_5m = {}
    data_daily = {}
    for sym in ALL_SYMBOLS:
        try:
            df_5m = yf.download(sym, period="5d", interval="5m", prepost=True, progress=False)
            if df_5m is not None and not df_5m.empty:
                if isinstance(df_5m.columns, pd.MultiIndex):
                    df_5m.columns = df_5m.columns.get_level_values(0)
                sub_5m = df_5m[["Open", "High", "Low", "Close", "Volume"]].dropna(subset=["Close"]).copy()
                sub_5m.index = sub_5m.index.tz_localize("UTC").tz_convert(tz_ny) if sub_5m.index.tz is None else sub_5m.index.tz_convert(tz_ny)
                data_5m[sym] = sub_5m

            df_1d = yf.download(sym, period="1mo", interval="1d", progress=False)
            if df_1d is not None and not df_1d.empty:
                if isinstance(df_1d.columns, pd.MultiIndex):
                    df_1d.columns = df_1d.columns.get_level_values(0)
                data_daily[sym] = df_1d[["Open", "High", "Low", "Close", "Volume"]].dropna(subset=["Close"]).copy()
        except Exception:
            pass
    return data_5m, data_daily


def compute_radar_advanced(data_5m, data_daily):
    if "QQQ" not in data_5m or data_5m["QQQ"].empty:
        return None

    latest_date_ny = data_5m["QQQ"].index[-1].date()
    day_slice = {sym: df[df.index.date == latest_date_ny].copy() for sym, df in data_5m.items() if not df.empty}
    if "QQQ" not in day_slice or day_slice["QQQ"].empty:
        return None

    qqq_df = day_slice["QQQ"]
    qqq_base = float(qqq_df["Open"].iloc[0])
    qqq_curr = float(qqq_df["Close"].iloc[-1])
    qqq_chg = ((qqq_curr - qqq_base) / qqq_base) * 100
    qqq_norm = (qqq_df["Close"] / qqq_base) * 100

    tier1_spreads = []
    tier2_spreads = []
    bar_rank_data = []

    for sym, cfg in TICKERS_CONFIG.items():
        if sym in day_slice and not day_slice[sym].empty:
            s_df = day_slice[sym]
            b_p = float(s_df["Open"].iloc[0])
            c_p = float(s_df["Close"].iloc[-1])
            chg = ((c_p - b_p) / b_p) * 100
            s_norm = (s_df["Close"] / b_p) * 100
            spread = s_norm - qqq_norm
            latest_sp = float(spread.iloc[-1]) if not spread.empty else 0.0

            vol_ratio = 1.0
            if sym in data_daily and len(data_daily[sym]) >= 5:
                avg_vol = float(data_daily[sym]["Volume"].iloc[-20:].mean())
                cum_vol = float(s_df["Volume"].sum())
                vol_ratio = cum_vol / (avg_vol * (len(s_df) / 78)) if avg_vol > 0 else 1.0

            if cfg["tier"] == "巨头":
                tier1_spreads.append(spread)
            else:
                tier2_spreads.append(spread)

            bar_rank_data.append({
                "Ticker": sym,
                "梯队": cfg["tier"],
                "差值": latest_sp,
                "涨跌": chg,
                "VolumeRatio": vol_ratio,
                "角色": cfg["role"],
            })
        else:
            bar_rank_data.append({
                "Ticker": sym,
                "梯队": cfg["tier"],
                "差值": 0.0,
                "涨跌": 0.0,
                "VolumeRatio": 0.0,
                "角色": cfg["role"],
            })

    # 合成两大梯队指数线
    t1_avg_series = pd.concat(tier1_spreads, axis=1).mean(axis=1) if tier1_spreads else pd.Series()
    t2_avg_series = pd.concat(tier2_spreads, axis=1).mean(axis=1) if tier2_spreads else pd.Series()

    return {
        "qqq_curr": qqq_curr,
        "qqq_chg": qqq_chg,
        "t1_series": t1_avg_series,
        "t2_series": t2_avg_series,
        "rank_df": pd.DataFrame(bar_rank_data).sort_values(by="差值", ascending=True),
    }


def render_macro_radar_tab():
    st.subheader("📡 QQQ 宏观雷达 · 机构级强弱看板")
    st.caption("💡 10:00 开盘看一眼：芯片先锋（蓝线）是否在水上领跑；若只有巨头（橙线）在水上，谨防拉权重出货。")

    c_r1, c_r2 = st.columns([3, 1])
    with c_r2:
        if st.button("🔄 刷新雷达", key="btn_radar_refresh_pro"):
            st.cache_data.clear()
            st.rerun()

    with st.spinner("正在加载机构级聚合雷达..."):
        d_5m, d_1d = fetch_radar_clean_data()

    res = compute_radar_advanced(d_5m, d_1d)
    if not res:
        st.warning("暂无足够数据渲染雷达。")
        return

    # 1. 顶部极简指标
    t1_now = res["t1_series"].iloc[-1] if not res["t1_series"].empty else 0.0
    t2_now = res["t2_series"].iloc[-1] if not res["t2_series"].empty else 0.0

    k1, k2, k3 = st.columns(3)
    k1.metric("🎯 QQQ 现价", f"${res['qqq_curr']:.2f}", f"{res['qqq_chg']:+.2f}%")
    k2.metric("🏛️ 7 大巨头中枢", f"{t1_now:+.2f}% 相对", "水上" if t1_now >= 0 else "水下")
    k3.metric("🚀 6 大芯片先锋", f"{t2_now:+.2f}% 相对", "🔥 真突破" if t2_now > t1_now and t2_now > 0 else "🚨 分化出货")

    st.markdown("---")

    # 2. 核心图表 1：聚合阵营双轨强弱图（彻底告别蜘蛛网，只留 3 根主线）
    st.markdown("#### 🌊 主力阵营宏观波形 (0.0% 轴 = QQQ)")

    fig_macro = go.Figure()
    fig_macro.add_hline(y=0, line_width=2.5, line_color="#FFD700", annotation_text="QQQ (基准中枢)", annotation_position="top left")

    if not res["t1_series"].empty:
        fig_macro.add_trace(go.Scatter(
            x=res["t1_series"].index.tz_convert(tz_myt),
            y=res["t1_series"].values,
            mode="lines",
            name="7 大权重巨头 (NVDA/AAPL/MSFT等)",
            line=dict(color="#FF9100", width=2.5),
        ))

    if not res["t2_series"].empty:
        fig_macro.add_trace(go.Scatter(
            x=res["t2_series"].index.tz_convert(tz_myt),
            y=res["t2_series"].values,
            mode="lines",
            name="6 大芯片先锋 (MU/AMD/AVGO等)",
            line=dict(color="#00E5FF", width=3),
        ))

    fig_macro.update_layout(
        height=320,
        margin=dict(l=5, r=5, t=10, b=5),
        template="plotly_dark",
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5),
        yaxis_title="相对强弱差 (%)",
    )
    st.plotly_chart(fig_macro, use_container_width=True)

    # 3. 核心图表 2：横向龙虎榜（手机上看极度舒适）
    st.markdown("#### 🏆 13 核心标的当前相对强弱榜 (水上跑赢 / 水下跑输)")

    df_rank = res["rank_df"]
    bar_colors = ["#00E676" if x >= 0 else "#FF5252" for x in df_rank["差值"]]

    fig_bar = go.Figure()
    fig_bar.add_trace(go.Bar(
        y=df_rank["Ticker"] + " (" + df_rank["梯队"] + ")",
        x=df_rank["差值"],
        orientation="h",
        marker=dict(color=bar_colors),
        text=[f"{x:+.2f}%" for x in df_rank["差值"]],
        textposition="outside",
    ))

    fig_bar.update_layout(
        height=450,
        margin=dict(l=5, r=25, t=10, b=5),
        template="plotly_dark",
        xaxis=dict(title="相对 QQQ 强弱差值 (%)", zeroline=True, zerolinecolor="#ffffff"),
    )
    st.plotly_chart(fig_bar, use_container_width=True)