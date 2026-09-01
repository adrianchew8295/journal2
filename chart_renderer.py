# 文件名: chart_renderer.py
# 作用: 绘制 100% 对齐富途牛牛视觉的 5M 双层画布 (半透明红绿战区色块 + K线穿透 + VPA 量能异动)

import datetime
from datetime import timedelta
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pytz
import streamlit as st

tz_myt = pytz.timezone("Asia/Kuala_Lumpur")
tz_ny = pytz.timezone("America/New_York")


def render_dual_chart(day_5m, p, trades, dt_10pm_myt, title_text="5M 战场与 VPA 量能回放"):
    """
    绘制与富途牛牛 100% 一致的半透明红蓝战区色块与副图 VPA 量能异动指标
    """
    if day_5m is None or day_5m.empty:
        st.warning("暂未获取到 5M K线数据。")
        return

    dt_view_start = dt_10pm_myt - timedelta(minutes=45)
    dt_view_end = dt_10pm_myt + timedelta(hours=2, minutes=30)
    start_ny_view = dt_view_start.astimezone(tz_ny)
    end_ny_view = dt_view_end.astimezone(tz_ny)

    chart_df = day_5m[(day_5m.index >= start_ny_view) & (day_5m.index <= end_ny_view)].copy()
    if chart_df.empty:
        chart_df = day_5m.iloc[-35:].copy()

    chart_df["MYT_Time"] = chart_df.index.tz_convert(tz_myt)

    # 1. 计算副图 VPA 量能指标
    chart_df["VMA20"] = chart_df["Volume"].rolling(20).mean()
    chart_df["VMA_15X"] = chart_df["VMA20"] * 1.5
    chart_df["VMA_20X"] = chart_df["VMA20"] * 2.0

    chart_df["IS_UP"] = chart_df["Close"] >= chart_df["Open"]
    chart_df["IS_DN"] = chart_df["Close"] < chart_df["Open"]

    chart_df["VOL_15X"] = (chart_df["Volume"] >= chart_df["VMA_15X"]) & (chart_df["Volume"] < chart_df["VMA_20X"])
    chart_df["VOL_20X"] = chart_df["Volume"] >= chart_df["VMA_20X"]

    chart_df["BULL_15"] = chart_df["IS_UP"] & chart_df["VOL_15X"]
    chart_df["BEAR_15"] = chart_df["IS_DN"] & chart_df["VOL_15X"]
    chart_df["BULL_20"] = chart_df["IS_UP"] & chart_df["VOL_20X"]
    chart_df["BEAR_20"] = chart_df["IS_DN"] & chart_df["VOL_20X"]

    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.72, 0.28],
        subplot_titles=(None, None)
    )

    # 2. 主图 5M K线蜡烛图
    fig.add_trace(go.Candlestick(
        x=chart_df["MYT_Time"],
        open=chart_df["Open"], high=chart_df["High"],
        low=chart_df["Low"], close=chart_df["Close"],
        name="5M K线",
        increasing_line_color="#26a69a",
        increasing_fillcolor="#26a69a",
        decreasing_line_color="#ef5350",
        decreasing_fillcolor="#ef5350",
    ), row=1, col=1)

    # 3. 富途同款：半透明物理战区色块 (透明度 0.18，底层渲染，不遮挡 K 线)
    if p:
        # 3.1 主阻力战区 (SBR - 红色半透明框)
        if p.get("SBR_TOP", 0) > 0 and p.get("SBR_BOT", 0) > 0:
            sbr_t, sbr_b = max(p["SBR_TOP"], p["SBR_BOT"]), min(p["SBR_TOP"], p["SBR_BOT"])
            fig.add_hrect(
                y0=sbr_b, y1=sbr_t,
                fillcolor="rgba(239, 83, 80, 0.22)",
                line=dict(color="rgba(239, 83, 80, 0.6)", width=1, dash="dash"),
                layer="below",
                annotation_text=f"SBR 阻力战区 [{sbr_b:.2f} - {sbr_t:.2f}]",
                annotation_position="top right",
                annotation_font=dict(color="#ff8a80", size=10),
                row=1, col=1
            )

        # 3.2 拓展更高阻力战区 (SBR2 - 深红/洋红色半透明框)
        if p.get("SBR2_TOP", 0) > 0 and p.get("SBR2_BOT", 0) > 0:
            sbr2_t, sbr2_b = max(p["SBR2_TOP"], p["SBR2_BOT"]), min(p["SBR2_TOP"], p["SBR2_BOT"])
            fig.add_hrect(
                y0=sbr2_b, y1=sbr2_t,
                fillcolor="rgba(255, 64, 129, 0.15)",
                line=dict(color="rgba(255, 64, 129, 0.5)", width=1, dash="dot"),
                layer="below",
                annotation_text=f"SBR2 极高阻力 [{sbr2_b:.2f} - {sbr2_t:.2f}]",
                annotation_position="top right",
                annotation_font=dict(color="#ff4081", size=9),
                row=1, col=1
            )

        # 3.3 主支撑战区 (RBS - 蓝色/青绿半透明框)
        if p.get("RBS_TOP", 0) > 0 and p.get("RBS_BOT", 0) > 0:
            rbs_t, rbs_b = max(p["RBS_TOP"], p["RBS_BOT"]), min(p["RBS_TOP"], p["RBS_BOT"])
            fig.add_hrect(
                y0=rbs_b, y1=rbs_t,
                fillcolor="rgba(38, 166, 154, 0.22)",
                line=dict(color="rgba(38, 166, 154, 0.6)", width=1, dash="dash"),
                layer="below",
                annotation_text=f"RBS 支撑战区 [{rbs_b:.2f} - {rbs_t:.2f}]",
                annotation_position="bottom right",
                annotation_font=dict(color="#80cbc4", size=10),
                row=1, col=1
            )

        # 3.4 拓展更低支撑战区 (RBS2 - 深蓝半透明框)
        if p.get("RBS2_TOP", 0) > 0 and p.get("RBS2_BOT", 0) > 0:
            rbs2_t, rbs2_b = max(p["RBS2_TOP"], p["RBS2_BOT"]), min(p["RBS2_TOP"], p["RBS2_BOT"])
            fig.add_hrect(
                y0=rbs2_b, y1=rbs2_t,
                fillcolor="rgba(41, 121, 255, 0.15)",
                line=dict(color="rgba(41, 121, 255, 0.5)", width=1, dash="dot"),
                layer="below",
                annotation_text=f"RBS2 极深支撑 [{rbs2_b:.2f} - {rbs2_t:.2f}]",
                annotation_position="bottom right",
                annotation_font=dict(color="#82b1ff", size=9),
                row=1, col=1
            )

        # 3.5 客观极值细线 (PDH/PDL/PMH/PML)
        if p.get("PDH", 0) > 0:
            fig.add_hline(y=p["PDH"], line_dash="dot", line_color="#ffd700", line_width=1.2, annotation_text=f"PDH 昨日高: {p['PDH']:.2f}", annotation_position="top left", row=1, col=1)
        if p.get("PDL", 0) > 0:
            fig.add_hline(y=p["PDL"], line_dash="dot", line_color="#40c4ff", line_width=1.2, annotation_text=f"PDL 昨日低: {p['PDL']:.2f}", annotation_position="bottom left", row=1, col=1)
        if p.get("PMH", 0) > 0:
            fig.add_hline(y=p["PMH"], line_dash="dashdot", line_color="#b388ff", line_width=1, annotation_text=f"PMH 盘前高: {p['PMH']:.2f}", annotation_position="top left", row=1, col=1)
        if p.get("PML", 0) > 0:
            fig.add_hline(y=p["PML"], line_dash="dashdot", line_color="#18ffff", line_width=1, annotation_text=f"PML 盘前低: {p['PML']:.2f}", annotation_position="bottom left", row=1, col=1)

    # 4. 副图 VPA 量能柱与均量线
    bar_colors = np.where(chart_df["IS_UP"], "#26a69a", "#ef5350")
    fig.add_trace(go.Bar(
        x=chart_df["MYT_Time"], y=chart_df["Volume"],
        name="成交量 (VOL)",
        marker=dict(color=bar_colors)
    ), row=2, col=1)

    fig.add_trace(go.Scatter(
        x=chart_df["MYT_Time"], y=chart_df["VMA20"],
        line=dict(color="#ffffff", width=1.2), name="VMA 20"
    ), row=2, col=1)

    fig.add_trace(go.Scatter(
        x=chart_df["MYT_Time"], y=chart_df["VMA_15X"],
        line=dict(color="#a0aec0", width=1, dash="dot"), name="1.5X 异动警戒"
    ), row=2, col=1)

    fig.add_trace(go.Scatter(
        x=chart_df["MYT_Time"], y=chart_df["VMA_20X"],
        line=dict(color="#ffd700", width=1.2, dash="dot"), name="2.0X 机构巨量"
    ), row=2, col=1)

    annotations = []

    # 5. 副图 VPA 量能放量打点
    for _, r in chart_df[chart_df["BULL_15"]].iterrows():
        annotations.append(dict(x=r["MYT_Time"], y=r["Volume"] * 1.05, xref="x2", yref="y2", text="▲", showarrow=False, font=dict(color="#00e5ff", size=12)))
    for _, r in chart_df[chart_df["BEAR_15"]].iterrows():
        annotations.append(dict(x=r["MYT_Time"], y=r["Volume"] * 1.05, xref="x2", yref="y2", text="▼", showarrow=False, font=dict(color="#ff5252", size=12)))
    for _, r in chart_df[chart_df["BULL_20"]].iterrows():
        annotations.append(dict(x=r["MYT_Time"], y=r["Volume"] * 1.08, xref="x2", yref="y2", text="▲▲", showarrow=False, font=dict(color="#00e676", size=13)))
    for _, r in chart_df[chart_df["BEAR_20"]].iterrows():
        annotations.append(dict(x=r["MYT_Time"], y=r["Volume"] * 1.08, xref="x2", yref="y2", text="▼▼", showarrow=False, font=dict(color="#ff1744", size=13)))

    # 6. 主图实际开仓/止盈止损标注
    if trades:
        for tr in trades:
            ep, xp, sl, tp = tr["Entry_Price"], tr["Exit_Price"], tr["SL"], tr["TP"]
            en_myt = tr["Entry_DT_NY"].astimezone(tz_myt)
            ex_myt = tr["Exit_DT_NY"].astimezone(tz_myt)
            is_buy = "多" in tr["Signal"] or "CALL" in tr["Signal"]

            annotations.append(dict(
                x=en_myt, y=ep, xref="x1", yref="y1",
                text=f"🚀 开仓 ({tr['Signal']}): {ep}",
                showarrow=True, arrowhead=3, arrowsize=1.5, arrowwidth=2.5,
                arrowcolor="#ffd700", ax=0, ay=45 if is_buy else -45,
                bordercolor="#ffd700", borderwidth=1.5, borderpad=3, bgcolor="#1a202c",
                font=dict(color="#ffd700", size=11, family="Arial Black")
            ))

            annotations.append(dict(
                x=ex_myt, y=xp, xref="x1", yref="y1",
                text=f"🏁 平仓 ({tr['Reason']}): {xp}",
                showarrow=True, arrowhead=3, arrowsize=1.5, arrowwidth=2.5,
                arrowcolor="#ffffff", ax=0, ay=-45 if is_buy else 45,
                bordercolor="#ffffff", borderwidth=1.5, borderpad=3, bgcolor="#1a202c",
                font=dict(color="#ffffff", size=11, family="Arial Black")
            ))

            fig.add_hline(y=ep, line_color="#ffd700", line_width=2, annotation_text=f"进场金线: {ep}", annotation_position="top right", row=1, col=1)
            fig.add_hline(y=sl, line_dash="dash", line_color="#ff5252", line_width=1.5, annotation_text=f"结构止损: {sl}", annotation_position="bottom right", row=1, col=1)
            fig.add_hline(y=tp, line_dash="dash", line_color="#00e676", line_width=1.5, annotation_text=f"1:2 止盈: {tp}", annotation_position="top right", row=1, col=1)

    fig.update_layout(
        title=title_text,
        xaxis_rangeslider_visible=False,
        height=680,
        margin=dict(l=10, r=10, t=40, b=10),
        template="plotly_dark",
        hovermode="x unified",
        annotations=annotations,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5)
    )

    st.plotly_chart(fig, use_container_width=True)
