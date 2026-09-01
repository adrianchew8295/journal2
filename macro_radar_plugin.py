# 文件名: macro_radar_plugin.py
# 作用: 彭博终端级 QQQ 宏观雷达看板 (周期双浪 + 资金流向榜 + 月度轮动 + AI分析Markdown导出)

import datetime
from datetime import timedelta
import json
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
    # 第一梯队：大盘中枢巨头 (防守/指数定海神针)
    "NVDA": {"name": "NVIDIA", "tier": "巨头", "role": "AI算力总舵手"},
    "AAPL": {"name": "Apple", "tier": "巨头", "role": "消费电子/防守指标"},
    "MSFT": {"name": "Microsoft", "tier": "巨头", "role": "云端定海神针"},
    "AMZN": {"name": "Amazon", "tier": "巨头", "role": "电商与云权重"},
    "GOOGL": {"name": "Alphabet", "tier": "巨头", "role": "搜索广告权重"},
    "TSLA": {"name": "Tesla", "tier": "巨头", "role": "流动性与情绪先锋"},
    "META": {"name": "Meta", "tier": "巨头", "role": "社交开源生态"},
    # 第二梯队：存储与半导体先锋 (高贝塔进攻先锋)
    "MU": {"name": "Micron", "tier": "先锋", "role": "存储/HBM龙头"},
    "AMD": {"name": "AMD", "tier": "先锋", "role": "算力二当家"},
    "AVGO": {"name": "Broadcom", "tier": "先锋", "role": "ASIC与网络龙头"},
    "WDC": {"name": "Western Digital", "tier": "先锋", "role": "存储与硬盘"},
    "STX": {"name": "Seagate", "tier": "先锋", "role": "数据中心存储"},
    "SNDK": {"name": "SanDisk", "tier": "先锋", "role": "存储极端情绪"},
}

ALL_SYMBOLS = ["QQQ"] + list(TICKERS_CONFIG.keys())


@st.cache_data(ttl=300)
def fetch_radar_data():
    """抓取 5M 日内走势及 1M 日线历史数据"""
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

            df_1d = yf.download(sym, period="3mo", interval="1d", progress=False)
            if df_1d is not None and not df_1d.empty:
                if isinstance(df_1d.columns, pd.MultiIndex):
                    df_1d.columns = df_1d.columns.get_level_values(0)
                data_daily[sym] = df_1d[["Open", "High", "Low", "Close", "Volume"]].dropna(subset=["Close"]).copy()
        except Exception:
            pass
    return data_5m, data_daily


def compute_radar_data(data_5m, data_daily):
    if "QQQ" not in data_5m or data_5m["QQQ"].empty:
        return None

    qqq_5m = data_5m["QQQ"]
    latest_date_ny = qqq_5m.index[-1].date()
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
    summary_rows = []
    above_qqq_count = 0
    total_active = 0

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

            if latest_sp >= 0:
                above_qqq_count += 1
            total_active += 1

            # 资金动向判定
            if latest_sp >= 0.2 and vol_ratio >= 1.5:
                flow_status = "🔥 机构暴力抢筹 (Inflow)"
            elif latest_sp >= 0.0 and vol_ratio >= 1.0:
                flow_status = "🟩 稳步资金流入"
            elif latest_sp < 0.0 and vol_ratio >= 1.5:
                flow_status = "🚨 主力放量出逃 (Outflow)"
            elif latest_sp < 0.0 and vol_ratio < 0.8:
                flow_status = "❄️ 缩量洗盘回调"
            else:
                flow_status = "⚠️ 缩量假意脉冲"

            summary_rows.append({
                "Ticker": sym,
                "Name": cfg["name"],
                "Tier": cfg["tier"],
                "Role": cfg["role"],
                "Price": round(c_p, 2),
                "ChangePct": round(chg, 2),
                "SpreadVsQQQ": round(latest_sp, 2),
                "VolumeRatio": round(vol_ratio, 2),
                "FlowStatus": flow_status
            })
        else:
            summary_rows.append({
                "Ticker": sym,
                "Name": cfg["name"],
                "Tier": cfg["tier"],
                "Role": cfg["role"],
                "Price": 0.0,
                "ChangePct": 0.0,
                "SpreadVsQQQ": 0.0,
                "VolumeRatio": 0.0,
                "FlowStatus": "⚪ 离线待同步"
            })

    t1_wave = pd.concat(tier1_spreads, axis=1).mean(axis=1) if tier1_spreads else pd.Series()
    t2_wave = pd.concat(tier2_spreads, axis=1).mean(axis=1) if tier2_spreads else pd.Series()

    return {
        "date_str": latest_date_ny.strftime("%Y-%m-%d"),
        "qqq_curr": qqq_curr,
        "qqq_chg": qqq_chg,
        "above_count": above_qqq_count,
        "total_active": total_active,
        "t1_wave": t1_wave,
        "t2_wave": t2_wave,
        "df_summary": pd.DataFrame(summary_rows)
    }


def generate_ai_markdown_report(res):
    """生成标准化 Markdown 数据块，可直接投喂给 AI"""
    df = res["df_summary"]
    t1_latest = res["t1_wave"].iloc[-1] if not res["t1_wave"].empty else 0.0
    t2_latest = res["t2_wave"].iloc[-1] if not res["t2_wave"].empty else 0.0
    
    inflow_leaders = df[df["FlowStatus"].str.contains("Inflow|抢筹|稳步")]["Ticker"].tolist()
    outflow_laggards = df[df["FlowStatus"].str.contains("Outflow|出逃")]["Ticker"].tolist()
    
    md_text = f"""# 📡 QQQ 宏观雷达与 13 核心标的轮动分析数据包 (AI Input Ready)

- **分析时间 (ET)**: {res['date_str']}
- **QQQ 现价/日内变动**: ${res['qqq_curr']:.2f} ({res['qqq_chg']:+.2f}%)
- **全市场共振比**: {res['above_count']}/{res['total_active']} 标的跑赢 QQQ ({(res['above_count']/res['total_active']*100):.1f}%)
- **阵营强弱状态**: 
  - 🏛️ 7 大巨头中枢偏离: `{t1_latest:+.2f}%`
  - 🚀 6 大芯片先锋偏离: `{t2_latest:+.2f}%`
  - 轮动判定: `{"🔥 先锋主导真突破 (Risk-On)" if t2_latest > t1_latest and t2_latest > 0 else "🚨 权重拉升掩护出货 (Risk-Off)"}`
- **主力抢筹先锋 (Inflow)**: {', '.join(inflow_leaders) if inflow_leaders else '无明显放量领涨'}
- **主力出逃标的 (Outflow)**: {', '.join(outflow_laggards) if outflow_laggards else '无严重放量砸盘'}

## 📋 13 核心标的量价与资金明细表
| Ticker | 梯队 | 现价 ($) | 涨跌幅 (%) | 相对 QQQ 差值 (%) | Volume Ratio | 资金动向 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
"""
    for _, r in df.iterrows():
        md_text += f"| {r['Ticker']} | {r['Tier']} | {r['Price']} | {r['ChangePct']:+.2f}% | {r['SpreadVsQQQ']:+.2f}% | {r['VolumeRatio']}x | {r['FlowStatus']} |\n"

    md_text += """
---
### 💡 提示词指引 (Prompt Guideline for AI):
请根据上述 QQQ 内部 13 只核心标的的相对强弱与 Volume Ratio 量能数据：
1. 评估当前大盘是「真金白银突破」还是「拉巨头掩护出货」；
2. 指出主力资金当前最青睐的进攻龙头与正在抛弃的弱势资产；
3. 为今晚 22:00-24:00 (MYT) 5M 交易系统提供多空环境配合度评级 (1-10分)。
"""
    return md_text


def render_macro_radar_tab():
    st.subheader("📡 QQQ 宏观雷达 · 资金轮动与量能全景看板")
    st.caption("💡 10:00 开盘参考：周期双浪判定大势，资金龙虎榜指明钱从哪里走、往哪里冲。")

    c_btn1, c_btn2 = st.columns([3, 1])
    with c_btn2:
        if st.button("🔄 刷新全景雷达", key="btn_refresh_full_radar"):
            st.cache_data.clear()
            st.rerun()

    with st.spinner("正在抓取 QQQ 与 13 核心标的多维量价数据..."):
        d_5m, d_1d = fetch_radar_data()

    res = compute_radar_data(d_5m, d_1d)
    if not res:
        st.warning("暂无足够数据生成全景雷达看板。")
        return

    # ---------------- 1. 顶部宏观核心体温卡 ----------------
    t1_now = res["t1_wave"].iloc[-1] if not res["t1_wave"].empty else 0.0
    t2_now = res["t2_wave"].iloc[-1] if not res["t2_wave"].empty else 0.0
    res_pct = (res["above_count"] / res["total_active"] * 100) if res["total_active"] > 0 else 0

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("🎯 QQQ 现价", f"${res['qqq_curr']:.2f}", f"{res['qqq_chg']:+.2f}%")
    k2.metric("🚦 标的共振比", f"{res['above_count']}/{res['total_active']} ({res_pct:.0f}%)", "🔥 强共振" if res_pct >= 60 else "🚨 弱分化")
    k3.metric("🏛️ 7大巨头防守浪", f"{t1_now:+.2f}%", "水上" if t1_now >= 0 else "水下")
    k4.metric("🚀 6大先锋进攻浪", f"{t2_now:+.2f}%", "🔥 真突破" if t2_now > t1_now and t2_now > 0 else "🚨 掩护出货")

    st.markdown("---")

    # ---------------- 2. 图表矩阵 (图 1: 周期双浪 | 图 2: 资金龙虎榜) ----------------
    col_g1, col_g2 = st.columns([1.2, 1])

    with col_g1:
        st.markdown("#### 🌊 宏观周期双浪模型 (进攻浪 vs 防守浪)")
        fig_wave = go.Figure()
        fig_wave.add_hline(y=0, line_width=2.5, line_color="#FFD700", annotation_text="QQQ 基准线 (0.0%)", annotation_position="top left")

        if not res["t2_wave"].empty:
            fig_wave.add_trace(go.Scatter(
                x=res["t2_wave"].index.tz_convert(tz_myt),
                y=res["t2_wave"].values,
                mode="lines",
                name="🚀 6大芯片先锋浪 (MU/NVDA/AMD)",
                line=dict(color="#00E5FF", width=3),
                fill='tozeroy',
                fillcolor='rgba(0, 229, 255, 0.08)'
            ))

        if not res["t1_wave"].empty:
            fig_wave.add_trace(go.Scatter(
                x=res["t1_wave"].index.tz_convert(tz_myt),
                y=res["t1_wave"].values,
                mode="lines",
                name="🏛️ 7大巨头防守浪 (AAPL/MSFT)",
                line=dict(color="#FF9100", width=2.5, dash="dash")
            ))

        fig_wave.update_layout(
            height=380,
            margin=dict(l=5, r=5, t=10, b=5),
            template="plotly_dark",
            hovermode="x unified",
            xaxis_title="大马时间 (MYT)",
            yaxis_title="相对强弱差值 (%)",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5)
        )
        st.plotly_chart(fig_wave, use_container_width=True)

    with col_g2:
        st.markdown("#### 🏆 13 标的资金净流向龙虎榜 (带量能倍数)")
        df_rank = res["df_summary"].sort_values(by="SpreadVsQQQ", ascending=True)
        bar_colors = ["#00E676" if x >= 0 else "#FF5252" for x in df_rank["SpreadVsQQQ"]]

        fig_bar = go.Figure()
        fig_bar.add_trace(go.Bar(
            y=df_rank["Ticker"] + " (" + df_rank["Tier"] + ")",
            x=df_rank["SpreadVsQQQ"],
            orientation="h",
            marker=dict(color=bar_colors),
            text=[f"{sp:+.2f}% | {vr}x量" for sp, vr in zip(df_rank["SpreadVsQQQ"], df_rank["VolumeRatio"])],
            textposition="outside"
        ))

        fig_bar.update_layout(
            height=380,
            margin=dict(l=5, r=25, t=10, b=5),
            template="plotly_dark",
            xaxis=dict(title="相对 QQQ 强弱差值 (%)", zeroline=True, zerolinecolor="#ffffff")
        )
        st.plotly_chart(fig_bar, use_container_width=True)

    st.markdown("---")

    # ---------------- 3. AI 分析数据输出中心 (Markdown / JSON) ----------------
    st.markdown("#### 🤖 AI 宏观分析数据中心 (一键复制或对接 API)")
    ai_md = generate_ai_markdown_report(res)

    tab_md, tab_raw = st.tabs(["📋 Markdown 格式 (直接粘贴给 AI)", "🔌 JSON 格式 (API 对接)"])
    
    with tab_md:
        st.caption("您可以直接复制下方 Markdown 文本投喂给 ChatGPT / Claude / Gemini 进行深度宏观诊断：")
        st.code(ai_md, language="markdown")
        
    with tab_raw:
        st.caption("标准化 JSON 数据包，便于 Python 脚本或自动化 Webhook 接入：")
        json_data = res["df_summary"].to_json(orient="records", indent=2)
        st.code(json_data, language="json")