# 文件名：chart_renderer.py
# 作用：100% 完整繪製主圖 5M 走勢與副圖 VPA 量能異動指標（修復均量線斷頭問題）
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

def calculate_vpa_signals(df):
    """
    計算副圖 VPA 量能異動指標（在完整數據集上計算，確保均量線全覆蓋）
    """
    try:
        df_calc = df.copy()
        df_calc["VMA20"] = df_calc["Volume"].rolling(20, min_periods=1).mean()
        df_calc["VMA_15X"] = df_calc["VMA20"] * 1.5
        df_calc["VMA_20X"] = df_calc["VMA20"] * 2.0

        df_calc["IS_UP"] = df_calc["Close"] >= df_calc["Open"]
        df_calc["IS_DN"] = df_calc["Close"] < df_calc["Open"]

        df_calc["VOL_15X"] = (df_calc["Volume"] >= df_calc["VMA_15X"]) & (df_calc["Volume"] < df_calc["VMA_20X"])
        df_calc["VOL_20X"] = df_calc["Volume"] >= df_calc["VMA_20X"]

        df_calc["BULL_15"] = df_calc["IS_UP"] & df_calc["VOL_15X"]
        df_calc["BEAR_15"] = df_calc["IS_DN"] & df_calc["VOL_15X"]
        df_calc["BULL_20"] = df_calc["IS_UP"] & df_calc["VOL_20X"]
        df_calc["BEAR_20"] = df_calc["IS_DN"] & df_calc["VOL_20X"]
        return df_calc
    except Exception as e:
        print(f"計算 VPA 發生異常: {str(e)}")
        return df

def render_dual_chart(day_5m, p, trades, dt_10pm_myt, title_text="5M 戰場與 VPA 量能回放"):
    """
    繪製上下雙層聯動畫布：上方 5M K線走勢，下方富途 VPA 量能副圖
    """
    try:
        if day_5m is None or day_5m.empty:
            st.warning("暫無可用的 5M 行情數據。")
            return

        # 1. 先在全局數據集上完整計算 VPA 指標（徹底消除前20根柱子斷線問題）
        full_df = calculate_vpa_signals(day_5m)

        # 2. 再精準切出窗口期視圖
        dt_view_start = dt_10pm_myt - timedelta(minutes=30)
        dt_view_end = dt_10pm_myt + timedelta(hours=2, minutes=15)
        start_ny_view = dt_view_start.astimezone(tz_ny)
        end_ny_view = dt_view_end.astimezone(tz_ny)

        chart_df = full_df[(full_df.index >= start_ny_view) & (full_df.index <= end_ny_view)].copy()
        if chart_df.empty:
            st.warning("暫未獲取到選定窗口期的 5M K線數據。")
            return

        chart_df["MYT_Time"] = chart_df.index.tz_convert(tz_myt)

        fig = make_subplots(
            rows=2, cols=1,
            shared_xaxes=True,
            vertical_spacing=0.03,
            row_heights=[0.7, 0.3],
            subplot_titles=(None, None)
        )

        # 主圖 1：5M K線
        fig.add_trace(go.Candlestick(
            x=chart_df["MYT_Time"],
            open=chart_df['Open'], high=chart_df['High'],
            low=chart_df['Low'], close=chart_df['Close'],
            name="5M K線"
        ), row=1, col=1)

        # 主圖 2：LWMA20 均線
        if "LWMA20" in chart_df.columns:
            fig.add_trace(go.Scatter(
                x=chart_df["MYT_Time"], y=chart_df["LWMA20"],
                line=dict(color="orange", width=1.2),
                name="LWMA 20"
            ), row=1, col=1)

        # 副圖 1：量能柱 (陽綠陰紅)
        bar_colors = np.where(chart_df["IS_UP"], '#26a69a', '#ef5350')
        fig.add_trace(go.Bar(
            x=chart_df["MYT_Time"], y=chart_df["Volume"],
            name="成交量 (VOL)",
            marker=dict(color=bar_colors)
        ), row=2, col=1)

        # 副圖 2：VPA 均量線與警戒線 (全區間完整覆蓋)
        fig.add_trace(go.Scatter(
            x=chart_df["MYT_Time"], y=chart_df["VMA20"],
            line=dict(color="white", width=1.2), name="VMA 20"
        ), row=2, col=1)

        fig.add_trace(go.Scatter(
            x=chart_df["MYT_Time"], y=chart_df["VMA_15X"],
            line=dict(color="gray", width=1, dash="dot"), name="1.5X 異動警戒"
        ), row=2, col=1)

        fig.add_trace(go.Scatter(
            x=chart_df["MYT_Time"], y=chart_df["VMA_20X"],
            line=dict(color="yellow", width=1.2, dash="dot"), name="2.0X 機構巨量"
        ), row=2, col=1)

        annotations = []

        # 主圖信號標記
        b2b_df = chart_df[chart_df.get("BUY_2B_SIG", False) == True]
        for _, row in b2b_df.iterrows():
            annotations.append(dict(
                x=row["MYT_Time"], y=row["Low"], xref="x1", yref="y1",
                text="▲▲ 2B 多", showarrow=True, arrowhead=2, arrowsize=1.2, arrowwidth=2,
                arrowcolor="#00e676", ax=0, ay=35, font=dict(color="#00e676", size=11, family="Arial Black")
            ))

        bstd_df = chart_df[chart_df.get("BUY_STD_SIG", False) == True]
        for _, row in bstd_df.iterrows():
            annotations.append(dict(
                x=row["MYT_Time"], y=row["Low"], xref="x1", yref="y1",
                text="▲ CALL 多", showarrow=True, arrowhead=2, arrowsize=1, arrowwidth=1.5,
                arrowcolor="#69f0ae", ax=0, ay=30, font=dict(color="#69f0ae", size=10)
            ))

        s2b_df = chart_df[chart_df.get("SELL_2B_SIG", False) == True]
        for _, row in s2b_df.iterrows():
            annotations.append(dict(
                x=row["MYT_Time"], y=row["High"], xref="x1", yref="y1",
                text="▼▼ 2B 空", showarrow=True, arrowhead=2, arrowsize=1.2, arrowwidth=2,
                arrowcolor="#ff5252", ax=0, ay=-35, font=dict(color="#ff5252", size=11, family="Arial Black")
            ))

        sstd_df = chart_df[chart_df.get("SELL_STD_SIG", False) == True]
        for _, row in sstd_df.iterrows():
            annotations.append(dict(
                x=row["MYT_Time"], y=row["High"], xref="x1", yref="y1",
                text="▼ PUT 空", showarrow=True, arrowhead=2, arrowsize=1, arrowwidth=1.5,
                arrowcolor="#ff8a80", ax=0, ay=-30, font=dict(color="#ff8a80", size=10)
            ))

        # 副圖 VPA 異動箭頭打點
        b15_df = chart_df[chart_df["BULL_15"] == True]
        for _, row in b15_df.iterrows():
            annotations.append(dict(
                x=row["MYT_Time"], y=row["Volume"] * 1.05, xref="x2", yref="y2",
                text="▲", showarrow=False, font=dict(color="cyan", size=12)
            ))

        s15_df = chart_df[chart_df["BEAR_15"] == True]
        for _, row in s15_df.iterrows():
            annotations.append(dict(
                x=row["MYT_Time"], y=row["Volume"] * 1.05, xref="x2", yref="y2",
                text="▼", showarrow=False, font=dict(color="red", size=12)
            ))

        b20_df = chart_df[chart_df["BULL_20"] == True]
        for _, row in b20_df.iterrows():
            annotations.append(dict(
                x=row["MYT_Time"], y=row["Volume"] * 1.08, xref="x2", yref="y2",
                text="▲▲", showarrow=False, font=dict(color="#00e676", size=13, family="Arial Black")
            ))

        s20_df = chart_df[chart_df["BEAR_20"] == True]
        for _, row in s20_df.iterrows():
            annotations.append(dict(
                x=row["MYT_Time"], y=row["Volume"] * 1.08, xref="x2", yref="y2",
                text="▼▼", showarrow=False, font=dict(color="red", size=13, family="Arial Black")
            ))

        # 主圖實際成交標記
        if trades:
            tr = trades[0]
            ep, xp, sl, tp = tr["Entry_Price"], tr["Exit_Price"], tr["SL"], tr["TP"]
            en_myt = tr["Entry_DT_NY"].astimezone(tz_myt)
            ex_myt = tr["Exit_DT_NY"].astimezone(tz_myt)
            is_buy = "多" in tr["Signal"] or "CALL" in tr["Signal"]

            annotations.append(dict(
                x=en_myt, y=ep, xref="x1", yref="y1",
                text=f"🚀 開倉: {ep}", showarrow=True, arrowhead=3, arrowsize=1.5, arrowwidth=2.5,
                arrowcolor="#ffd700", ax=0, ay=45 if is_buy else -45,
                bordercolor="#ffd700", borderwidth=1.5, borderpad=3, bgcolor="#1a202c",
                font=dict(color="#ffd700", size=11, family="Arial Black")
            ))

            annotations.append(dict(
                x=ex_myt, y=xp, xref="x1", yref="y1",
                text=f"🏁 平倉 ({tr['Reason']}): {xp}", showarrow=True, arrowhead=3, arrowsize=1.5, arrowwidth=2.5,
                arrowcolor="#ffffff", ax=0, ay=-45 if is_buy else 45,
                bordercolor="#ffffff", borderwidth=1.5, borderpad=3, bgcolor="#1a202c",
                font=dict(color="#ffffff", size=11, family="Arial Black")
            ))

            fig.add_hline(y=ep, line_color="#ffd700", line_width=2, annotation_text=f"進場金線: {ep}", row=1, col=1)
            fig.add_hline(y=sl, line_dash="dash", line_color="#ff5252", annotation_text=f"結構止損: {sl}", row=1, col=1)
            fig.add_hline(y=tp, line_dash="dash", line_color="#00e676", annotation_text=f"1:2 止盈: {tp}", row=1, col=1)

        # 主圖戰區線
        if p:
            if p.get("SBR_BOT", 0) > 0: fig.add_hline(y=p["SBR_BOT"], line_dash="dash", line_color="#f56565", annotation_text=f"SBR 阻力底: {p['SBR_BOT']:.2f}", row=1, col=1)
            if p.get("RBS_TOP", 0) > 0: fig.add_hline(y=p["RBS_TOP"], line_dash="dash", line_color="#48bb78", annotation_text=f"RBS 支撐頂: {p['RBS_TOP']:.2f}", row=1, col=1)
            if p.get("PDH", 0) > 0: fig.add_hline(y=p["PDH"], line_dash="dot", line_color="#ed8936", annotation_text=f"昨日高 PDH: {p['PDH']:.2f}", row=1, col=1)
            if p.get("PDL", 0) > 0: fig.add_hline(y=p["PDL"], line_dash="dot", line_color="#4299e1", annotation_text=f"昨日低 PDL: {p['PDL']:.2f}", row=1, col=1)

        fig.update_layout(
            title=title_text,
            xaxis_rangeslider_visible=False,
            height=680,
            margin=dict(l=10, r=10, t=40, b=10),
            template="plotly_dark",
            annotations=annotations
        )
        st.plotly_chart(fig, use_container_width=True)
    except Exception as e:
        st.error(f"渲染圖表時發生異常: {str(e)}")
