# 文件名: macro_radar_plugin.py
# 作用: QQQ 宏观雷达与 13 核心标的 0 轴相对强弱波形图插件 (开盘 1 秒看清真突破与掩护出货)

import datetime
from datetime import timedelta
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import pytz
import streamlit as st
import yfinance as yf

tz_ny = pytz.timezone("America/New_York")
tz_myt = pytz.timezone("Asia/Kuala_Lumpur")

# 严格锁定原版 13 核心标的
TICKERS_CONFIG = {
    # 第一梯队：大盘中枢巨头
    "NVDA": {"name": "NVIDIA", "tier": "巨头", "role": "AI/算力总舵手，指数核心推动力"},
    "AAPL": {"name": "Apple", "tier": "巨头", "role": "消费电子龙头，防守型资金指标"},
    "MSFT": {"name": "Microsoft", "tier": "巨头", "role": "云端与企业端定海神针"},
    "AMZN": {"name": "Amazon", "tier": "巨头", "role": "电商与云计算权重"},
    "GOOGL": {"name": "Alphabet", "tier": "巨头", "role": "搜索与数字广告权重"},
    "TSLA": {"name": "Tesla", "tier": "巨头", "role": "高波动情绪与流动性先锋"},
    "META": {"name": "Meta", "tier": "巨头", "role": "社交与开源生态权重"},
    # 第二梯队：存储与半导体先锋
    "MU": {"name": "Micron", "tier": "先锋", "role": "内存/HBM 龙头，存储板块绝对代表"},
    "AMD": {"name": "AMD", "tier": "先锋", "role": "算力二当家，风险偏好指标"},
    "AVGO": {"name": "Broadcom", "tier": "先锋", "role": "网络晶片与 ASIC 龙头"},
    "WDC": {"name": "Western Digital", "tier": "先锋", "role": "存储与硬盘核心"},
    "STX": {"name": "Seagate", "tier": "先锋", "role": "存储与大容量数据中心指标"},
    "SNDK": {"name": "SanDisk", "tier": "先锋", "role": "存储极端情绪先锋"},
}

ALL_SYMBOLS = ["QQQ"] + list(TICKERS_CONFIG.keys())


@st.cache_data(ttl=300)
def fetch_macro_radar_data():
    """批量抓取 QQQ 与 13 标的 5M 日内走势与日线均量 (支持 SNDK 安全容错)"""
    data_5m = {}
    data_daily = {}

    for sym in ALL_SYMBOLS:
        try:
            # 抓取 5M 分时
            df_5m = yf.download(sym, period="5d", interval="5m", prepost=True, progress=False)
            if df_5m is not None and not df_5m.empty:
                if isinstance(df_5m.columns, pd.MultiIndex):
                    df_5m.columns = df_5m.columns.get_level_values(0)
                sub_5m = df_5m[["Open", "High", "Low", "Close", "Volume"]].dropna(subset=["Close"]).copy()
                if sub_5m.index.tz is None:
                    sub_5m.index = sub_5m.index.tz_localize("UTC").tz_convert(tz_ny)
                else:
                    sub_5m.index = sub_5m.index.tz_convert(tz_ny)
                data_5m[sym] = sub_5m

            # 抓取 1D 日线用于计算 20 日均量
            df_1d = yf.download(sym, period="1mo", interval="1d", progress=False)
            if df_1d is not None and not df_1d.empty:
                if isinstance(df_1d.columns, pd.MultiIndex):
                    df_1d.columns = df_1d.columns.get_level_values(0)
                data_daily[sym] = df_1d[["Open", "High", "Low", "Close", "Volume"]].dropna(subset=["Close"]).copy()
        except Exception:
            pass

    return data_5m, data_daily


def compute_radar_metrics(data_5m, data_daily):
    """计算 0 轴强弱差值 (Spread) 与 Volume Ratio"""
    if "QQQ" not in data_5m or data_5m["QQQ"].empty:
        return None

    qqq_5m = data_5m["QQQ"]
    latest_date_ny = qqq_5m.index[-1].date()

    day_slice = {sym: df[df.index.date == latest_date_ny].copy() for sym, df in data_5m.items() if not df.empty}
    if "QQQ" not in day_slice or day_slice["QQQ"].empty:
        return None

    qqq_today = day_slice["QQQ"]
    qqq_base_p = float(qqq_today["Open"].iloc[0])
    qqq_curr_p = float(qqq_today["Close"].iloc[-1])
    qqq_chg = ((qqq_curr_p - qqq_base_p) / qqq_base_p) * 100
    qqq_norm = (qqq_today["Close"] / qqq_base_p) * 100

    spread_series = {}
    metrics_table = []
    above_count = 0
    total_valid = 0

    for sym, cfg in TICKERS_CONFIG.items():
        if sym in day_slice and not day_slice[sym].empty:
            sym_df = day_slice[sym]
            base_p = float(sym_df["Open"].iloc[0])
            curr_p = float(sym_df["Close"].iloc[-1])
            chg_pct = ((curr_p - base_p) / base_p) * 100

            # 归一化后与 QQQ 算差值 (Spread): 水上为正，水下为负
            sym_norm = (sym_df["Close"] / base_p) * 100
            spread = sym_norm - qqq_norm
            spread_series[sym] = spread.dropna()
            latest_spread = float(spread.iloc[-1]) if not spread.empty else 0.0

            # Volume Ratio
            vol_ratio = 1.0
            if sym in data_daily and len(data_daily[sym]) >= 5:
                avg_vol_20 = float(data_daily[sym]["Volume"].iloc[-20:].mean())
                cum_vol = float(sym_df["Volume"].sum())
                vol_ratio = cum_vol / (avg_vol_20 * (len(sym_df) / 78)) if avg_vol_20 > 0 else 1.0

            is_above = latest_spread >= 0
            if is_above:
                above_count += 1
            total_valid += 1

            if chg_pct > 0.3 and vol_ratio >= 1.25:
                signal = "🔥 量价齐扬"
            elif chg_pct > 0.3 and vol_ratio < 0.8:
                signal = "⚠️ 缩量假冲"
            elif chg_pct <= 0.0 and vol_ratio >= 1.5:
                signal = "🚨 爆量滞涨"
            elif chg_pct < 0:
                signal = "❄️ 弱势回调"
            else:
                signal = "➖ 常规震荡"

            metrics_table.append({
                "Ticker": sym,
                "梯队": cfg["tier"],
                "角色定位": cfg["role"],
                "现价 ($)": round(curr_p, 2),
                "当日涨跌 (%)": round(chg_pct, 2),
                "相对 QQQ 差值 (%)": round(latest_spread, 2),
                "强弱状态": "🟩 水上跑赢" if is_above else "🟥 水下跑输",
                "Volume Ratio": round(vol_ratio, 2),
                "异动信号": signal,
            })
        else:
            # SNDK 等离线标的安全占位
            metrics_table.append({
                "Ticker": sym,
                "梯队": cfg["tier"],
                "角色定位": cfg["role"],
                "现价 ($)": 0.0,
                "当日涨跌 (%)": 0.0,
                "相对 QQQ 差值 (%)": 0.0,
                "强弱状态": "⚪ 历史离线",
                "Volume Ratio": 0.0,
                "异动信号": "🔒 待同步",
            })

    return {
        "qqq_curr_p": qqq_curr_p,
        "qqq_chg": qqq_chg,
        "above_count": above_count,
        "total_valid": total_valid,
        "spread_series": spread_series,
        "metrics_table": pd.DataFrame(metrics_table),
    }


def render_macro_radar_tab():
    """渲染 Tab 1 宏观雷达看板"""
    st.subheader("📡 QQQ 宏观雷达 (13 核心标的 0 轴相对强弱波形图)")
    st.caption("💡 每天 22:00 开盘看一眼：芯片先锋（NVDA/MU 等）在水上为真突破，在水下多为拉权重掩护出货。仅作背景参考。")

    if st.button("🔄 刷新宏观雷达数据", key="btn_radar_refresh"):
        st.cache_data.clear()
        st.rerun()

    with st.spinner("正在拉取 13 核心标的走势..."):
        d_5m, d_1d = fetch_macro_radar_data()

    res = compute_radar_metrics(d_5m, d_1d)
    if not res:
        st.warning("暂无足够的分时数据生成雷达波形图。")
        return

    # 1. 顶部指标栏
    r1, r2, r3, r4 = st.columns(4)
    r1.metric("🎯 QQQ 现价", f"${res['qqq_curr_p']:.2f}", f"{res['qqq_chg']:+.2f}%")
    
    pct_above = (res["above_count"] / res["total_valid"] * 100) if res["total_valid"] > 0 else 0
    state_desc = "🔥 强势真突破" if pct_above >= 65 else ("🚨 掩护出货警惕" if pct_above <= 35 else "⚖️ 板块健康轮动")
    r2.metric("🚦 标的共振比", f"{res['above_count']}/{res['total_valid']} ({pct_above:.0f}%)", state_desc)

    df_tb = res["metrics_table"]
    t1_df = df_tb[(df_tb["梯队"] == "巨头") & (df_tb["Volume Ratio"] > 0)]
    t2_df = df_tb[(df_tb["梯队"] == "先锋") & (df_tb["Volume Ratio"] > 0)]
    t1_avg = t1_df["当日涨跌 (%)"].mean() if not t1_df.empty else 0.0
    t2_avg = t2_df["当日涨跌 (%)"].mean() if not t2_df.empty else 0.0
    r3.metric("🏛️ 7 大巨头均幅", f"{t1_avg:+.2f}%")
    r4.metric("🚀 6 大先锋均幅", f"{t2_avg:+.2f}%", f"先锋差值: {t2_avg - t1_avg:+.2f}%")

    st.markdown("---")

    # 2. 0 轴相对强弱波形图 (散户最直观：看谁在水上，谁在水下)
    st.markdown("#### 🌊 13 核心标的相对 QQQ 强弱波形图 (0.0% 轴 = QQQ)")
    fig = go.Figure()

    # 0 轴 QQQ 水平面
    fig.add_hline(y=0, line_width=3, line_color="#FFD700", annotation_text="<b>QQQ 基准线 (0.0%)</b>", annotation_position="top left")

    colors_map = {
        "NVDA": "#00E5FF", "AAPL": "#76FF03", "MSFT": "#FFD600", "AMZN": "#FF9100",
        "GOOGL": "#D500F9", "TSLA": "#FF1744", "META": "#00B0FF", "MU": "#00E676",
        "AMD": "#FF5252", "AVGO": "#E040FB", "WDC": "#40C4FF", "STX": "#B2FF59", "SNDK": "#B0BEC5"
    }

    for sym, s_series in res["spread_series"].items():
        tier = TICKERS_CONFIG[sym]["tier"]
        c = colors_map.get(sym, "#ffffff")
        dash_style = "solid" if tier == "巨头" else "dash"
        
        fig.add_trace(go.Scatter(
            x=s_series.index.tz_convert(tz_myt),
            y=s_series.values,
            mode="lines",
            name=f"{sym} ({tier})",
            line=dict(color=c, width=2 if tier == "巨头" else 1.5, dash=dash_style),
            hovertemplate=f"<b>{sym}</b>: %{{y:+.2f}}%<extra></extra>"
        ))

    fig.update_layout(
        height=480,
        margin=dict(l=10, r=10, t=30, b=10),
        template="plotly_dark",
        hovermode="x unified",
        xaxis_title="大马时间 (MYT)",
        yaxis_title="相对 QQQ 强弱差值 (%)",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")

    # 3. 极简强弱排位表
    st.markdown("#### 📋 13 标的强弱座次与异动热力表")
    st.dataframe(df_tb.sort_values(by="相对 QQQ 差值 (%)", ascending=False), use_container_width=True, hide_index=True)