# 文件名: macro_radar_plugin.py
# 作用: QQQ 宏观雷达与 13 标的事实穿透看板 (加权双浪 + 日周大级别点位 + 波动消耗门禁)

import datetime
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import pytz
import streamlit as st
import yfinance as yf

tz_ny = pytz.timezone("America/New_York")
tz_myt = pytz.timezone("Asia/Kuala_Lumpur")

# 13 核心标的配置：包含市值影响力权重与行业角色
TICKERS_CONFIG = {
    # 👑 第一梯队：核心权重定海神针 (Weight: 3.0 - 决定大盘命脉)
    "NVDA": {"name": "NVIDIA", "tier": "巨头", "weight": 3.0, "role": "AI算力总舵手"},
    "AAPL": {"name": "Apple", "tier": "巨头", "weight": 3.0, "role": "消费电子/防守中枢"},
    "MSFT": {"name": "Microsoft", "tier": "巨头", "weight": 3.0, "role": "云端权重底座"},
    # 🏛️ 第二梯队：中枢巨头 (Weight: 2.0 - 影响大盘反弹力度)
    "AMZN": {"name": "Amazon", "tier": "巨头", "weight": 2.0, "role": "电商与云权重"},
    "GOOGL": {"name": "Alphabet", "tier": "巨头", "weight": 2.0, "role": "搜索广告权重"},
    "META": {"name": "Meta", "tier": "巨头", "weight": 2.0, "role": "社交开源生态"},
    "TSLA": {"name": "Tesla", "tier": "巨头", "weight": 2.0, "role": "流动性先锋"},
    "AVGO": {"name": "Broadcom", "tier": "先锋", "weight": 2.0, "role": "网络与芯片核心"},
    # 🚀 第三梯队：情绪进攻先锋 (Weight: 1.0 - 高贝塔风向标)
    "MU": {"name": "Micron", "tier": "先锋", "weight": 1.0, "role": "存储/HBM龙头"},
    "AMD": {"name": "AMD", "tier": "先锋", "weight": 1.0, "role": "算力二当家"},
    "WDC": {"name": "Western Digital", "tier": "先锋", "weight": 1.0, "role": "存储与硬盘"},
    "STX": {"name": "Seagate", "tier": "先锋", "weight": 1.0, "role": "企业级存储"},
    "SNDK": {"name": "SanDisk", "tier": "先锋", "weight": 1.0, "role": "存储情绪标的"},
}

ALL_SYMBOLS = ["QQQ"] + list(TICKERS_CONFIG.keys())


@st.cache_data(ttl=180)
def fetch_radar_data_advanced():
    """抓取 5M 日内分时流与日线/周线大级别历史事实"""
    data_5m = {}
    data_daily = {}
    data_weekly = {}

    for sym in ALL_SYMBOLS:
        try:
            ticker = yf.Ticker(sym)
            df_5m = ticker.history(period="5d", interval="5m", prepost=True)
            if df_5m is not None and not df_5m.empty:
                if isinstance(df_5m.columns, pd.MultiIndex):
                    df_5m.columns = df_5m.columns.get_level_values(0)
                sub_5m = df_5m[["Open", "High", "Low", "Close", "Volume"]].dropna(subset=["Close"]).copy()
                if not sub_5m.empty:
                    sub_5m.index = sub_5m.index.tz_localize("UTC").tz_convert(tz_ny) if sub_5m.index.tz is None else sub_5m.index.tz_convert(tz_ny)
                    data_5m[sym] = sub_5m

            df_1d = ticker.history(period="3mo", interval="1d")
            if df_1d is not None and not df_1d.empty:
                if isinstance(df_1d.columns, pd.MultiIndex):
                    df_1d.columns = df_1d.columns.get_level_values(0)
                sub_1d = df_1d[["Open", "High", "Low", "Close", "Volume"]].dropna(subset=["Close"]).copy()
                if not sub_1d.empty:
                    data_daily[sym] = sub_1d

            df_1w = ticker.history(period="6mo", interval="1wk")
            if df_1w is not None and not df_1w.empty:
                if isinstance(df_1w.columns, pd.MultiIndex):
                    df_1w.columns = df_1w.columns.get_level_values(0)
                sub_1w = df_1w[["Open", "High", "Low", "Close", "Volume"]].dropna(subset=["Close"]).copy()
                if not sub_1w.empty:
                    data_weekly[sym] = sub_1w
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

    # 1. 整合第三点：日内 ATR 波动消耗率 (ATR Range Used %)
    atr_used_pct = 0.0
    atr_1d_val = 4.0
    if "QQQ" in data_daily and len(data_daily["QQQ"]) >= 14:
        d_df = data_daily["QQQ"]
        tr = np.maximum(d_df["High"] - d_df["Low"], np.maximum((d_df["High"] - d_df["Close"].shift(1)).abs(), (d_df["Low"] - d_df["Close"].shift(1)).abs()))
        atr_1d_val = float(tr.rolling(14).mean().iloc[-1])
        if atr_1d_val > 0:
            day_range = qqq_high - qqq_low
            atr_used_pct = (day_range / atr_1d_val) * 100

    # 2. 整合第一点：市值加权双浪计算 (Weighted Waves)
    t1_series_list, t1_weights = [], []
    t2_series_list, t2_weights = [], []
    facts_table = []
    above_qqq_count = 0
    total_active = 0

    for sym, cfg in TICKERS_CONFIG.items():
        w = cfg["weight"]
        if sym in day_slice and len(day_slice[sym]) > 0:
            s_df = day_slice[sym]
            b_p = float(s_df["Open"].iloc[0])
            c_p = float(s_df["Close"].iloc[-1])
            
            if b_p > 0:
                chg = ((c_p - b_p) / b_p) * 100
                s_norm = (s_df["Close"] / b_p) * 100
                spread = (s_norm - qqq_norm).dropna()

                if not spread.empty:
                    latest_sp = float(spread.iloc[-1])
                    
                    # 日线均量倍数
                    vol_ratio = 1.0
                    d_ma50 = c_p
                    if sym in data_daily and len(data_daily[sym]) >= 5:
                        avg_vol = float(data_daily[sym]["Volume"].iloc[-20:].mean())
                        cum_vol = float(s_df["Volume"].sum())
                        vol_ratio = cum_vol / (avg_vol * (len(s_df) / 78)) if avg_vol > 0 else 1.0
                        if len(data_daily[sym]) >= 50:
                            d_ma50 = float(data_daily[sym]["Close"].rolling(50).mean().iloc[-1])

                    # 周线关键低点事实 (PWL)
                    pwl_val = c_p * 0.95
                    if sym in data_weekly and len(data_weekly[sym]) >= 2:
                        pwl_val = float(data_weekly[sym]["Low"].iloc[-2])

                    # 阵营加权归集
                    if cfg["tier"] == "巨头":
                        t1_series_list.append(spread * w)
                        t1_weights.append(w)
                    else:
                        t2_series_list.append(spread * w)
                        t2_weights.append(w)

                    if latest_sp >= 0:
                        above_qqq_count += 1
                    total_active += 1

                    # 3. 整合第二点：严谨客观动作判定 (触及日周支撑 + 2B / 放量验证)
                    is_near_pwl = (c_p <= pwl_val * 1.015)
                    if latest_sp >= 0.2 and vol_ratio >= 1.25:
                        action_tag = "🟢 放量水上 (领跑突破)"
                        structure_pos = "突破拉升区"
                    elif latest_sp <= -0.5 and vol_ratio >= 1.5:
                        action_tag = "🔴 坚决离场 (放量砸盘)"
                        structure_pos = "破位出逃区"
                    elif is_near_pwl and vol_ratio < 0.9:
                        action_tag = "⚠️ 触及周线支撑 (等2B扫损企稳)"
                        structure_pos = f"PWL周线底 (${pwl_val:.2f})"
                    elif c_p <= d_ma50 * 1.01 and c_p >= d_ma50 * 0.99:
                        action_tag = "⚠️ 回踩日线MA50 (观察企稳)"
                        structure_pos = f"日MA50成本区 (${d_ma50:.2f})"
                    else:
                        action_tag = "⚪ 缩量观望 (常态整理)"
                        structure_pos = "中继震荡区"

                    facts_table.append({
                        "Ticker": sym,
                        "Name": cfg["name"],
                        "Tier": cfg["tier"],
                        "Weight": f"{w:.1f}x",
                        "Price": round(c_p, 2),
                        "ChangePct": round(chg, 2),
                        "SpreadVsQQQ": round(latest_sp, 2),
                        "VolumeRatio": round(vol_ratio, 2),
                        "Structure": structure_pos,
                        "ActionTag": action_tag
                    })
                    continue

        # 离线标的安全占位
        facts_table.append({
            "Ticker": sym,
            "Name": cfg["name"],
            "Tier": cfg["tier"],
            "Weight": f"{w:.1f}x",
            "Price": 0.0,
            "ChangePct": 0.0,
            "SpreadVsQQQ": 0.0,
            "VolumeRatio": 0.0,
            "Structure": "待同步",
            "ActionTag": "⚪ 离线观望"
        })

    # 市值加权平均曲线
    t1_wave = (pd.concat(t1_series_list, axis=1).sum(axis=1) / sum(t1_weights)).dropna() if t1_series_list else pd.Series(dtype=float)
    t2_wave = (pd.concat(t2_series_list, axis=1).sum(axis=1) / sum(t2_weights)).dropna() if t2_series_list else pd.Series(dtype=float)

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
        "df_facts": pd.DataFrame(facts_table).fillna(0.0)
    }


def generate_facts_markdown(res):
    df = res["df_facts"]
    t1_latest = float(res["t1_wave"].iloc[-1]) if not res["t1_wave"].empty else 0.0
    t2_latest = float(res["t2_wave"].iloc[-1]) if not res["t2_wave"].empty else 0.0
    atr_used = res["atr_used_pct"]
    pct_above = (res["above_count"] / res["total_active"] * 100)

    # 宏观定调事实推导
    if atr_used >= 110:
        macro_verdict = "🚨 日内波动率已透支 (ATR Used ≥ 110%) | 动能耗尽，严禁追单，建议空仓防守"
    elif t2_latest > t1_latest and t2_latest > 0 and pct_above >= 60:
        macro_verdict = "🟢 芯片先锋加权领涨主导真突破 (Risk-On / 多头配合度极高)"
    elif t2_latest < 0 and t1_latest >= 0:
        macro_verdict = "🔴 权重巨头护盘掩护芯片出货 (Risk-Off / 诱多风险，严禁追多)"
    else:
        macro_verdict = "⚪ 板块轮动与均线纠缠整理 (Neutral / 严格按战区防守)"

    md_text = f"""# 📡 QQQ 宏观雷达与 13 核心标的事实战报 (Integrated Facts)

### 1. 宏观环境与波动能耗事实
- **截面时间**: `{res['timestamp_myt']}` (对应美东 `{res['timestamp_ny']}`)
- **QQQ 指数状态**: 现价 `${res['qqq_curr']:.2f}` ({res['qqq_chg']:+.2f}%) | 日线 ATR: `${res['atr_1d_val']:.2f}`
- **🔋 日内波幅消耗 (ATR Used)**: `{atr_used:.1f}%` ({'🚨 能量耗尽/防垃圾震荡' if atr_used >= 100 else '动能充沛/可执行交易'})
- **全市场共振比**: `{res['above_count']}/{res['total_active']}` 跑赢 QQQ (`{pct_above:.1f}%`)
- **加权双浪偏离事实**:
  - 🏛️ 巨头防守浪 (加权中枢): `{t1_latest:+.2f}%`
  - 🚀 芯片进攻浪 (加权中枢): `{t2_latest:+.2f}%`
  - **大盘定调结论**: **{macro_verdict}**

### 2. 13 核心标的日周结构与实操动作矩阵
| Ticker | 阵营 | 权重 | 现价 ($) | 涨跌幅 (%) | 相对 QQQ 差值 (%) | 均量倍数 | 关键结构位置 | 落地实操动作 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
"""
    for _, r in df.iterrows():
        md_text += f"| **{r['Ticker']}** | {r['Tier']} | {r['Weight']} | {r['Price']} | {r['ChangePct']:+.2f}% | {r['SpreadVsQQQ']:+.2f}% | {r['VolumeRatio']}x | {r['Structure']} | {r['ActionTag']} |\n"

    md_text += """
---
### 💡 给 AI 的诊断提示词 (Prompt):
请根据上述不可争辩的客观事实（加权双浪、ATR 消耗率、13 标的日周结构与动作标签）：
1. 诊断今晚主力资金是真金白银进攻还是拉巨头掩护出逃；
2. 评估今晚 22:00-24:00 (MYT) QQQ 5M 交易环境多空配合评分 (1-10分) 与操作要点。
"""
    return md_text


def render_macro_radar_tab():
    st.subheader("📡 QQQ 宏观雷达 · 13 核心标的事实穿透看板 (加权与大级别版)")

    if st.button("🔄 刷新最新宏观事实", key="btn_refresh_radar_final_v2"):
        st.cache_data.clear()
        st.rerun()

    with st.spinner("正在提取 13 核心标的加权分时与日周结构数据..."):
        d_5m, d_1d, d_1w = fetch_radar_data_advanced()

    res = compute_radar_facts_integrated(d_5m, d_1d, d_1w)
    if not res:
        st.warning("行情连接中，请稍候点击上方刷新。")
        return

    t1_now = float(res["t1_wave"].iloc[-1]) if not res["t1_wave"].empty else 0.0
    t2_now = float(res["t2_wave"].iloc[-1]) if not res["t2_wave"].empty else 0.0
    pct_above = (res["above_count"] / res["total_active"] * 100) if res["total_active"] > 0 else 0
    atr_used = res["atr_used_pct"]

    # 1. 顶部指标卡：新增 ATR 波动消耗事实
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("🎯 QQQ 基准现价", f"${res['qqq_curr']:.2f}", f"{res['qqq_chg']:+.2f}%")
    k2.metric("🔋 日内 ATR 波幅消耗", f"{atr_used:.1f}%", "🚨 空间耗尽/防追单" if atr_used >= 100 else "动能充沛")
    k3.metric("🏛️ 巨头防守浪 (加权)", f"{t1_now:+.2f}%", "水上跑赢" if t1_now >= 0 else "水下跑输")
    k4.metric("🚀 芯片进攻浪 (加权)", f"{t2_now:+.2f}%", "🔥 真突破" if t2_now > t1_now and t2_now > 0 else "🚨 掩护出货")

    st.markdown("---")

    # 2. 视觉双浪 + 横向加权龙虎榜
    col_v1, col_v2 = st.columns([1.2, 1])

    with col_v1:
        st.markdown("#### 🌊 主力阵营加权双浪 (0.0% = QQQ 基准)")
        fig_wave = go.Figure()
        fig_wave.add_hline(y=0, line_width=2.5, line_color="#FFD700", annotation_text="QQQ 基准中枢", annotation_position="top left")

        if not res["t2_wave"].empty:
            fig_wave.add_trace(go.Scatter(
                x=res["t2_wave"].index.tz_convert(tz_myt),
                y=res["t2_wave"].values,
                mode="lines",
                name="🚀 芯片先锋加权浪 (MU/NVDA/AMD等)",
                line=dict(color="#00E5FF", width=3),
                fill='tozeroy',
                fillcolor='rgba(0, 229, 255, 0.08)'
            ))

        if not res["t1_wave"].empty:
            fig_wave.add_trace(go.Scatter(
                x=res["t1_wave"].index.tz_convert(tz_myt),
                y=res["t1_wave"].values,
                mode="lines",
                name="🏛️ 巨头防守加权浪 (AAPL/MSFT等)",
                line=dict(color="#FF9100", width=2.5, dash="dash")
            ))

        fig_wave.update_layout(
            height=360,
            margin=dict(l=5, r=5, t=10, b=5),
            template="plotly_dark",
            hovermode="x unified",
            xaxis_title="大马时间 (MYT)",
            yaxis_title="相对加权偏离 (%)",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5)
        )
        st.plotly_chart(fig_wave, use_container_width=True)

    with col_v2:
        st.markdown("#### 🏆 13 标的强弱龙虎榜 (带量能与权重)")
        df_rank = res["df_facts"].sort_values(by="SpreadVsQQQ", ascending=True)
        bar_colors = ["#00E676" if x >= 0 else "#FF5252" for x in df_rank["SpreadVsQQQ"]]

        fig_bar = go.Figure()
        fig_bar.add_trace(go.Bar(
            y=df_rank["Ticker"] + " (" + df_rank["Weight"] + ")",
            x=df_rank["SpreadVsQQQ"],
            orientation="h",
            marker=dict(color=bar_colors),
            text=[f"{sp:+.2f}% | {vr}x" for sp, vr in zip(df_rank["SpreadVsQQQ"], df_rank["VolumeRatio"])],
            textposition="outside"
        ))

        fig_bar.update_layout(
            height=360,
            margin=dict(l=5, r=25, t=10, b=5),
            template="plotly_dark",
            xaxis=dict(title="相对 QQQ 差值 (%)", zeroline=True, zerolinecolor="#ffffff")
        )
        st.plotly_chart(fig_bar, use_container_width=True)

    st.markdown("---")

    # 3. 13 核心标的落地点位与动作诊断表
    st.markdown("#### 📋 13 核心标的日周结构与实操清单")
    st.dataframe(
        df_rank[["Ticker", "Tier", "Weight", "Price", "ChangePct", "SpreadVsQQQ", "VolumeRatio", "Structure", "ActionTag"]].sort_values(by="SpreadVsQQQ", ascending=False),
        use_container_width=True,
        hide_index=True
    )

    st.markdown("---")

    # 4. 标准 Markdown 导出区 (一键复制给 AI)
    st.markdown("#### 🤖 AI 深度分析数据包 (点击右上角一键复制)")
    ai_md = generate_facts_markdown(res)
    st.code(ai_md, language="markdown")
