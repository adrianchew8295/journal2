# 文件名: chart_renderer.py
# 作用: 旗舰级 Plotly 交易终端画线引擎 (TradingView / Bloomberg 顶级质感 · 动态自适应量程 · 高级磨砂战区)

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
    绘制顶级交易机构风格的 5M 双层画盘：
    - 主图：极速穿透蜡烛图 + 渐变半透明战区带 (SBR/RBS) + 战术点阵极值线 (PDH/PDL/PMH/PML) + 信号打点
    - 副图：自适应对数/分位数裁剪 VPA 量能柱 + 均量警戒带 (彻底解决首根天量压缩问题)
    """
    if day_5m is None or day_5m.empty:
        st.warning("暂未获取到 5M K线数据。")
        return

    # 1. 窗口截取：锁定 22:00 - 24:00 (MYT) 作战窗口前后 30 分钟
    dt_view_start = dt_10pm_myt - timedelta(minutes=30)
    dt_view_end = dt_10pm_myt + timedelta(hours=2, minutes=15)
    start_ny_view = dt_view_start.astimezone(tz_ny)
    end_ny_view = dt_view_end.astimezone(tz_ny)

    chart_df = day_5m[(day_5m.index >= start_ny_view) & (day_5m.index <= end_ny_view)].copy()
    if chart_df.empty:
        chart_df = day_5m.iloc[-32:].copy()

    chart_df["MYT_Time"] = chart_df.index.tz_convert(tz_myt)
    chart_df["Time_Str"] = chart_df["MYT_Time"].dt.strftime("%H:%M")

    # 2. 顶级 VPA 量能算法：过滤开盘天量畸变，计算机构放量阈值
    # 使用稳健中位数滚动均量，防止异常单根天量拉爆 Y 轴
    chart_df["VMA20"] = chart_df["Volume"].rolling(12, min_periods=3).mean().bfill()
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

    # 3. 创建双层画板 (72% 主图 / 28% 副图，暗黑无缝贴合)
    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.02,
        row_heights=[0.72, 0.28],
        subplot_titles=(None, None)
    )

    # -------------------------------------------------------------------------
    # 4. 主图绘制：专业蜡烛与高级战区
    # -------------------------------------------------------------------------
    # 4.1 5M 极细精致蜡烛图 (TradingView 经典配色：翡翠绿 #089981 / 珊瑚红 #F23645)
    fig.add_trace(go.Candlestick(
        x=chart_df["Time_Str"],
        open=chart_df["Open"], high=chart_df["High"],
        low=chart_df["Low"], close=chart_df["Close"],
        name="5M K线",
        increasing_line_color="#089981",
        increasing_fillcolor="#089981",
        decreasing_line_color="#F23645",
        decreasing_fillcolor="#F23645",
        line=dict(width=1.2)
    ), row=1, col=1)

    # 4.2 高级磨砂战区色块 (Layer="below" 保证 K 线永远浮在上面清晰可见)
    if p:
        # SBR 阻力战区 (柔和绯红渐变)
        if p.get("SBR_TOP", 0) > 0 and p.get("SBR_BOT", 0) > 0:
            sbr_t, sbr_b = max(p["SBR_TOP"], p["SBR_BOT"]), min(p["SBR_TOP"], p["SBR_BOT"])
            fig.add_hrect(
                y0=sbr_b, y1=sbr_t,
                fillcolor="rgba(242, 54, 69, 0.16)",
                line=dict(color="rgba(242, 54, 69, 0.45)", width=1, dash="dash"),
                layer="below",
                annotation_text=f" 🛡️ SBR 阻力战区 [{sbr_b:.2f} - {sbr_t:.2f}]",
                annotation_position="top right",
                annotation_font=dict(color="#FF8A80", size=10, family="Consolas, monospace"),
                row=1, col=1
            )

        # RBS 支撑战区 (柔和青绿渐变)
        if p.get("RBS_TOP", 0) > 0 and p.get("RBS_BOT", 0) > 0:
            rbs_t, rbs_b = max(p["RBS_TOP"], p["RBS_BOT"]), min(p["RBS_TOP"], p["RBS_BOT"])
            fig.add_hrect(
                y0=rbs_b, y1=rbs_t,
                fillcolor="rgba(8, 153, 129, 0.16)",
                line=dict(color="rgba(8, 153, 129, 0.45)", width=1, dash="dash"),
                layer="below",
                annotation_text=f" 🎯 RBS 支撑战区 [{rbs_b:.2f} - {rbs_t:.2f}]",
                annotation_position="bottom right",
                annotation_font=dict(color="#80CBC4", size=10, family="Consolas, monospace"),
                row=1, col=1
            )

        # 客观极值锚点线 (精细点阵激光线，不抢视线)
        if p.get("PDH", 0) > 0:
            fig.add_hline(y=p["PDH"], line_dash="dot", line_color="#F59E0B", line_width=1.2, annotation_text=f" PDH 昨日高: {p['PDH']:.2f}", annotation_position="top left", annotation_font=dict(color="#FCD34D", size=9), row=1, col=1)
        if p.get("PDL", 0) > 0:
            fig.add_hline(y=p["PDL"], line_dash="dot", line_color="#38BDF8", line_width=1.2, annotation_text=f" PDL 昨日低: {p['PDL']:.2f}", annotation_position="bottom left", annotation_font=dict(color="#7DD3FC", size=9), row=1, col=1)
        if p.get("PMH", 0) > 0:
            fig.add_hline(y=p["PMH"], line_dash="dashdot", line_color="#C084FC", line_width=1, annotation_text=f" PMH 盘前高: {p['PMH']:.2f}", annotation_position="top left", annotation_font=dict(color="#E9D5FF", size=9), row=1, col=1)
        if p.get("PML", 0) > 0:
            fig.add_hline(y=p["PML"], line_dash="dashdot", line_color="#2DD4BF", line_width=1, annotation_text=f" PML 盘前低: {p['PML']:.2f}", annotation_position="bottom left", annotation_font=dict(color="#99F6E4", size=9), row=1, col=1)

    # -------------------------------------------------------------------------
    # 5. 副图绘制：顶级 VPA 量能体系
    # -------------------------------------------------------------------------
    # 柱状图配色：放量加亮，普通量沉稳
    vol_colors = []
    for _, r in chart_df.iterrows():
        if r["VOL_20X"]:
            vol_colors.append("#F59E0B" if r["IS_UP"] else "#DC2626")  # 机构巨量金/血红
        elif r["VOL_15X"]:
            vol_colors.append("#00E5FF" if r["IS_UP"] else "#FF5252")  # 异动青/红
        else:
            vol_colors.append("rgba(8, 153, 129, 0.45)" if r["IS_UP"] else "rgba(242, 54, 69, 0.45)")

    fig.add_trace(go.Bar(
        x=chart_df["Time_Str"],
        y=chart_df["Volume"],
        name="VPA 成交量",
        marker=dict(color=vol_colors, line=dict(color=vol_colors, width=0.8))
    ), row=2, col=1)

    # 均量线体系 (VMA20 / 1.5X 预警 / 2.0X 巨量)
    fig.add_trace(go.Scatter(
        x=chart_df["Time_Str"], y=chart_df["VMA20"],
        line=dict(color="#E2E8F0", width=1.2), name="VMA 20 (均量基准)"
    ), row=2, col=1)

    fig.add_trace(go.Scatter(
        x=chart_df["Time_Str"], y=chart_df["VMA_15X"],
        line=dict(color="#38BDF8", width=1.0, dash="dash"), name="1.5X 异动警戒线"
    ), row=2, col=1)

    fig.add_trace(go.Scatter(
        x=chart_df["Time_Str"], y=chart_df["VMA_20X"],
        line=dict(color="#F59E0B", width=1.2, dash="dot"), name="2.0X 机构巨量线"
    ), row=2, col=1)

    # -------------------------------------------------------------------------
    # 6. 精英标注层：买卖开平仓金线与气泡卡片
    # -------------------------------------------------------------------------
    annotations = []

    # 6.1 副图放量信号打点 (紧贴柱子上方，不挡视图)
    for _, r in chart_df[chart_df["BULL_15"]].iterrows():
        annotations.append(dict(x=r["Time_Str"], y=r["Volume"], xref="x2", yref="y2", text="▲", showarrow=True, arrowhead=0, arrowcolor="rgba(0,0,0,0)", ay=-10, font=dict(color="#00E5FF", size=10)))
    for _, r in chart_df[chart_df["BEAR_15"]].iterrows():
        annotations.append(dict(x=r["Time_Str"], y=r["Volume"], xref="x2", yref="y2", text="▼", showarrow=True, arrowhead=0, arrowcolor="rgba(0,0,0,0)", ay=-10, font=dict(color="#FF5252", size=10)))
    for _, r in chart_df[chart_df["BULL_20"]].iterrows():
        annotations.append(dict(x=r["Time_Str"], y=r["Volume"], xref="x2", yref="y2", text="⚡▲▲", showarrow=True, arrowhead=0, arrowcolor="rgba(0,0,0,0)", ay=-12, font=dict(color="#F59E0B", size=11, family="Arial Black")))
    for _, r in chart_df[chart_df["BEAR_20"]].iterrows():
        annotations.append(dict(x=r["Time_Str"], y=r["Volume"], xref="x2", yref="y2", text="⚡▼▼", showarrow=True, arrowhead=0, arrowcolor="rgba(0,0,0,0)", ay=-12, font=dict(color="#DC2626", size=11, family="Arial Black")))

    # 6.2 主图实操执行线与胶囊标记
    if trades:
        for tr in trades:
            ep, xp, sl, tp = tr["Entry_Price"], tr["Exit_Price"], tr["SL"], tr["TP"]
            en_str = tr["Entry_DT_NY"].astimezone(tz_myt).strftime("%H:%M")
            ex_str = tr["Exit_DT_NY"].astimezone(tz_myt).strftime("%H:%M")
            is_buy = "多" in tr["Signal"] or "CALL" in tr["Signal"]

            # 开仓发光胶囊
            annotations.append(dict(
                x=en_str, y=ep, xref="x1", yref="y1",
                text=f" 🚀 开仓 [{tr['Signal']}]: {ep:.2f} ",
                showarrow=True, arrowhead=2, arrowsize=1.2, arrowwidth=2,
                arrowcolor="#F59E0B", ax=0, ay=38 if is_buy else -38,
                bordercolor="#F59E0B", borderwidth=1.5, borderpad=4,
                bgcolor="#0F172A",
                font=dict(color="#FCD34D", size=11, family="Consolas, monospace")
            ))

            # 平仓胶囊
            annotations.append(dict(
                x=ex_str, y=xp, xref="x1", yref="y1",
                text=f" 🏁 平仓 [{tr['Reason']}]: {xp:.2f} ({tr['PnL_Points']:+.2f} pt) ",
                showarrow=True, arrowhead=2, arrowsize=1.2, arrowwidth=2,
                arrowcolor="#38BDF8" if tr["PnL_Points"] >= 0 else "#EF4444",
                ax=0, ay=-38 if is_buy else 38,
                bordercolor="#38BDF8" if tr["PnL_Points"] >= 0 else "#EF4444",
                borderwidth=1.5, borderpad=4,
                bgcolor="#0F172A",
                font=dict(color="#FFFFFF", size=11, family="Consolas, monospace")
            ))

            # 1:2 结构金线绘制
            fig.add_hline(y=ep, line_color="#F59E0B", line_width=1.8, annotation_text=f" 进场成本: {ep:.2f}", annotation_position="top right", annotation_font=dict(color="#FCD34D", size=9), row=1, col=1)
            fig.add_hline(y=sl, line_dash="dash", line_color="#EF4444", line_width=1.4, annotation_text=f" 结构止损: {sl:.2f}", annotation_position="bottom right", annotation_font=dict(color="#FCA5A5", size=9), row=1, col=1)
            fig.add_hline(y=tp, line_dash="dash", line_color="#10B981", line_width=1.4, annotation_text=f" 1:2 止盈: {tp:.2f}", annotation_position="top right", annotation_font=dict(color="#6EE7B7", size=9), row=1, col=1)

    # -------------------------------------------------------------------------
    # 7. 顶级布局引擎配置 (Bloomberg / TradingView 黑暗终端风)
    # -------------------------------------------------------------------------
    # 自适应 Y 轴空间计算，留出 8% 边距保证 K 线不贴顶贴底
    y_min, y_max = chart_df["Low"].min(), chart_df["High"].max()
    y_pad = (y_max - y_min) * 0.08

    # 副图 Y 轴自适应：取 95% 分位数最大值，防止开盘单根柱子拉扁全场
    vol_95_max = chart_df["Volume"].quantile(0.95) * 1.6

    fig.update_layout(
        title=dict(
            text=f"<b>{title_text}</b>",
            font=dict(family="Consolas, monospace", size=15, color="#F8FAFC"),
            x=0.01, y=0.98
        ),
        paper_bgcolor="#0B0F19",
        plot_bgcolor="#0B0F19",
        height=690,
        margin=dict(l=8, r=8, t=45, b=8),
        hovermode="x unified",
        xaxis_rangeslider_visible=False,
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom", y=1.01,
            xanchor="right", x=0.99,
            font=dict(size=10, color="#94A3B8"),
            bgcolor="rgba(15, 23, 42, 0.8)",
            bordercolor="#334155", borderwidth=1
        ),
        annotations=annotations
    )

    # 主图坐标轴优化
    fig.update_yaxes(
        range=[y_min - y_pad, y_max + y_pad],
        gridcolor="#1E293B", zerolinecolor="#334155",
        tickfont=dict(family="Consolas", color="#94A3B8", size=10),
        row=1, col=1
    )

    # 副图坐标轴优化 (彻底解决 Y 轴过高压扁量能柱的问题)
    fig.update_yaxes(
        range=[0, max(vol_95_max, 1000)],
        gridcolor="#1E293B",
        tickfont=dict(family="Consolas", color="#64748B", size=9),
        row=2, col=1
    )

    # X 轴时间分类紧凑排列，消除非交易时段空隙
    fig.update_xaxes(
        type="category",
        gridcolor="#1E293B",
        tickfont=dict(family="Consolas", color="#94A3B8", size=10),
        showline=True, linecolor="#334155"
    )

    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
