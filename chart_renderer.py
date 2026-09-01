# 文件名: chart_renderer.py
# 作用: 旗舰级 QQQ 5M 战场与 VPA 量能双层画布 (100% 像素级严丝合缝对齐 · 滚轮缩放 · 十字准星联动)

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
    绘制与富途/TradingView 100% 垂直像素级对齐的主图 K 线与副图 VPA 量能指标
    """
    if day_5m is None or day_5m.empty:
        st.warning("暂未获取到 5M K线数据。")
        return

    # 1. 精确裁切窗口期 (21:15 - 00:30 MYT)
    dt_view_start = dt_10pm_myt - timedelta(minutes=45)
    dt_view_end = dt_10pm_myt + timedelta(hours=2, minutes=30)
    start_ny_view = dt_view_start.astimezone(tz_ny)
    end_ny_view = dt_view_end.astimezone(tz_ny)

    chart_df = day_5m[(day_5m.index >= start_ny_view) & (day_5m.index <= end_ny_view)].copy()
    if chart_df.empty:
        chart_df = day_5m.iloc[-35:].copy()

    # 统一标准化 X 轴分类序列 (确保主副图 X 轴数组 100% 严丝合缝)
    chart_df["MYT_Time"] = chart_df.index.tz_convert(tz_myt)
    chart_df["Time_Str"] = chart_df["MYT_Time"].dt.strftime("%H:%M")
    time_series = chart_df["Time_Str"].tolist()

    # 2. 计算副图 VPA 量能指标
    chart_df["VMA20"] = chart_df["Volume"].rolling(15, min_periods=3).mean().bfill()
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

    # 3. 构建上下严格联动的双层画布
    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.72, 0.28],
        subplot_titles=(None, None)
    )

    # 3.1 主图 5M K线蜡烛图 (TradingView 质感翡翠绿 / 珊瑚红)
    fig.add_trace(go.Candlestick(
        x=time_series,
        open=chart_df["Open"], high=chart_df["High"],
        low=chart_df["Low"], close=chart_df["Close"],
        name="5M K线",
        increasing_line_color="#089981", increasing_fillcolor="#089981",
        decreasing_line_color="#F23645", decreasing_fillcolor="#F23645",
        line=dict(width=1.2)
    ), row=1, col=1)

    # 3.2 富途半透明战区色块
    if p:
        if p.get("SBR_TOP", 0) > 0 and p.get("SBR_BOT", 0) > 0:
            sbr_t, sbr_b = max(p["SBR_TOP"], p["SBR_BOT"]), min(p["SBR_TOP"], p["SBR_BOT"])
            fig.add_hrect(
                y0=sbr_b, y1=sbr_t, fillcolor="rgba(242, 54, 69, 0.18)",
                line=dict(color="rgba(242, 54, 69, 0.6)", width=1, dash="dash"),
                layer="below", annotation_text=f"SBR 阻力战区 [{sbr_b:.2f} - {sbr_t:.2f}]",
                annotation_position="top right", annotation_font=dict(color="#FCA5A5", size=10),
                row=1, col=1
            )
        if p.get("RBS_TOP", 0) > 0 and p.get("RBS_BOT", 0) > 0:
            rbs_t, rbs_b = max(p["RBS_TOP"], p["RBS_BOT"]), min(p["RBS_TOP"], p["RBS_BOT"])
            fig.add_hrect(
                y0=rbs_b, y1=rbs_t, fillcolor="rgba(8, 153, 129, 0.18)",
                line=dict(color="rgba(8, 153, 129, 0.6)", width=1, dash="dash"),
                layer="below", annotation_text=f"RBS 支撑战区 [{rbs_b:.2f} - {rbs_t:.2f}]",
                annotation_position="bottom right", annotation_font=dict(color="#6EE7B7", size=10),
                row=1, col=1
            )
        if p.get("PDH", 0) > 0:
            fig.add_hline(y=p["PDH"], line_dash="dot", line_color="#FCD34D", line_width=1.2, annotation_text=f"PDH 昨日高: {p['PDH']:.2f}", annotation_position="top left", row=1, col=1)
        if p.get("PDL", 0) > 0:
            fig.add_hline(y=p["PDL"], line_dash="dot", line_color="#93C5FD", line_width=1.2, annotation_text=f"PDL 昨日低: {p['PDL']:.2f}", annotation_position="bottom left", row=1, col=1)

    # 3.3 副图：与主图 100% 对齐的量能柱 (使用相同分类 X 轴 + 明确对齐锚点)
    bar_colors = np.where(chart_df["IS_UP"], "#089981", "#F23645")
    fig.add_trace(go.Bar(
        x=time_series, y=chart_df["Volume"],
        name="成交量 (VOL)",
        marker=dict(color=bar_colors),
        width=0.65  # 统一柱体宽度，消除居中偏差
    ), row=2, col=1)

    fig.add_trace(go.Scatter(
        x=time_series, y=chart_df["VMA20"],
        line=dict(color="#FFFFFF", width=1.2), name="VMA 20 (均量)"
    ), row=2, col=1)

    fig.add_trace(go.Scatter(
        x=time_series, y=chart_df["VMA_15X"],
        line=dict(color="#94A3B8", width=1, dash="dot"), name="1.5X 异动警戒"
    ), row=2, col=1)

    fig.add_trace(go.Scatter(
        x=time_series, y=chart_df["VMA_20X"],
        line=dict(color="#FCD34D", width=1.2, dash="dot"), name="2.0X 机构巨量"
    ), row=2, col=1)

    # 4. 标注：开平仓动作与 VPA 异动箭头
    annotations = []

    # 4.1 副图放量打点
    for _, r in chart_df[chart_df["BULL_15"]].iterrows():
        annotations.append(dict(x=r["Time_Str"], y=r["Volume"] * 1.05, xref="x2", yref="y2", text="▲", showarrow=False, font=dict(color="#38BDF8", size=11)))
    for _, r in chart_df[chart_df["BEAR_15"]].iterrows():
        annotations.append(dict(x=r["Time_Str"], y=r["Volume"] * 1.05, xref="x2", yref="y2", text="▼", showarrow=False, font=dict(color="#F87171", size=11)))
    for _, r in chart_df[chart_df["BULL_20"]].iterrows():
        annotations.append(dict(x=r["Time_Str"], y=r["Volume"] * 1.08, xref="x2", yref="y2", text="▲▲", showarrow=False, font=dict(color="#34D399", size=13)))
    for _, r in chart_df[chart_df["BEAR_20"]].iterrows():
        annotations.append(dict(x=r["Time_Str"], y=r["Volume"] * 1.08, xref="x2", yref="y2", text="▼▼", showarrow=False, font=dict(color="#EF4444", size=13)))

    # 4.2 主图实际买卖开平仓连线与标记
    if trades:
        for tr in trades:
            ep, xp, sl, tp = tr["Entry_Price"], tr["Exit_Price"], tr["SL"], tr["TP"]
            en_str = tr["Entry_DT_NY"].astimezone(tz_myt).strftime("%H:%M")
            ex_str = tr["Exit_DT_NY"].astimezone(tz_myt).strftime("%H:%M")
            is_buy = "多" in tr["Signal"] or "CALL" in tr["Signal"]

            if en_str in time_series:
                annotations.append(dict(
                    x=en_str, y=ep, xref="x1", yref="y1",
                    text=f"🚀 开仓 ({tr['Signal']}): {ep}",
                    showarrow=True, arrowhead=2, arrowsize=1.2, arrowwidth=2,
                    arrowcolor="#FCD34D", ax=0, ay=35 if is_buy else -35,
                    bordercolor="#FCD34D", borderwidth=1.5, borderpad=3, bgcolor="#1E293B",
                    font=dict(color="#FCD34D", size=11, family="Consolas")
                ))

            if ex_str in time_series:
                annotations.append(dict(
                    x=ex_str, y=xp, xref="x1", yref="y1",
                    text=f"🏁 平仓 ({tr['Reason']}): {xp}",
                    showarrow=True, arrowhead=2, arrowsize=1.2, arrowwidth=2,
                    arrowcolor="#FFFFFF", ax=0, ay=-35 if is_buy else 35,
                    bordercolor="#FFFFFF", borderwidth=1.5, borderpad=3, bgcolor="#1E293B",
                    font=dict(color="#FFFFFF", size=11, family="Consolas")
                ))

            fig.add_hline(y=ep, line_color="#FCD34D", line_width=2, annotation_text=f"进场金线: {ep}", annotation_position="top right", row=1, col=1)
            fig.add_hline(y=sl, line_dash="dash", line_color="#EF4444", line_width=1.5, annotation_text=f"结构止损: {sl}", annotation_position="bottom right", row=1, col=1)
            fig.add_hline(y=tp, line_dash="dash", line_color="#10B981", line_width=1.5, annotation_text=f"1:2 止盈: {tp}", annotation_position="top right", row=1, col=1)

    # 5. TradingView 旗舰布局配置 (开启滚轮缩放、拖拽与十字准星对齐联动)
    fig.update_layout(
        title=dict(
            text=f"<b>{title_text}</b> <span style='font-size:12px; color:#94A3B8;'>[滚轮缩放 / 拖拽平移 / 双击复位]</span>",
            font=dict(family="Consolas, monospace", size=14, color="#F8FAFC"),
            x=0.01, y=0.98
        ),
        height=660,
        margin=dict(l=10, r=10, t=45, b=10),
        template="plotly_dark",
        paper_bgcolor="#0B0F19",
        plot_bgcolor="#0B0F19",
        hovermode="x unified",
        xaxis_rangeslider_visible=False,
        dragmode="pan",
        annotations=annotations,
        legend=dict(
            orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=0.99,
            font=dict(size=10, color="#94A3B8"), bgcolor="rgba(15, 23, 42, 0.8)", bordercolor="#334155", borderwidth=1
        )
    )

    # 6. 强制主副图 X 轴分类对齐与十字准星穿透联动
    fig.update_xaxes(
        type="category", gridcolor="#1E293B", tickfont=dict(family="Consolas", color="#94A3B8", size=10),
        showspikes=True, spikemode="across", spikesnap="cursor", spikecolor="#64748B", spikethickness=1, spikedash="dot",
        row=1, col=1
    )
    fig.update_xaxes(
        type="category", gridcolor="#1E293B", tickfont=dict(family="Consolas", color="#94A3B8", size=10),
        showspikes=True, spikemode="across", spikesnap="cursor", spikecolor="#64748B", spikethickness=1, spikedash="dot",
        row=2, col=1
    )
    fig.update_yaxes(
        gridcolor="#1E293B", tickfont=dict(family="Consolas", color="#94A3B8", size=10),
        showspikes=True, spikemode="across", spikesnap="cursor", spikecolor="#64748B", spikethickness=1, spikedash="dot",
        row=1, col=1
    )
    fig.update_yaxes(
        gridcolor="#1E293B", tickfont=dict(family="Consolas", color="#64748B", size=9),
        row=2, col=1
    )

    # 开启滚轮缩放配置
    st.plotly_chart(
        fig,
        use_container_width=True,
        config={
            "scrollZoom": True,
            "displayModeBar": True,
            "modeBarButtonsToRemove": ["lasso2d", "select2d"],
            "displaylogo": False,
            "toImageButtonOptions": {"format": "png", "filename": "qqq_5m_dual_chart"}
        }
    )
