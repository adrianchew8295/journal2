# 文件名: macro_radar_plugin.py
# 作用: 13 核心标的 TradingView 旗舰级交互日线战区穿透与触点罗盘 (主副图严格像素对齐)

import datetime
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pytz
import requests
import streamlit as st
import yfinance as yf

tz_ny = pytz.timezone("America/New_York")
tz_myt = pytz.timezone("Asia/Kuala_Lumpur")

TIINGO_TOKEN = "bcffe3a5cf7eeef085e405cfa4a3e5691b976217"

# 13 核心标的配置
TICKERS_CONFIG = {
    "NVDA": {"name": "英伟达", "weight": 3.0},
    "AAPL": {"name": "苹果", "weight": 3.0},
    "MSFT": {"name": "微软", "weight": 3.0},
    "AMZN": {"name": "亚马逊", "weight": 2.0},
    "GOOGL": {"name": "谷歌", "weight": 2.0},
    "META": {"name": "Meta", "weight": 2.0},
    "TSLA": {"name": "特斯拉", "weight": 2.0},
    "AVGO": {"name": "博通", "weight": 2.0},
    "MU": {"name": "美光", "weight": 1.0},
    "AMD": {"name": "AMD", "weight": 1.0},
    "WDC": {"name": "西部数据", "weight": 1.0},
    "STX": {"name": "希捷", "weight": 1.0},
    "SNDK": {"name": "闪迪", "weight": 1.0},
}

ALL_SYMBOLS = ["QQQ"] + list(TICKERS_CONFIG.keys())


def fetch_from_tiingo_daily(ticker):
    """Tiingo 备用日线抓取"""
    try:
        start_date = (datetime.datetime.now(tz_ny) - datetime.timedelta(days=180)).strftime("%Y-%m-%d")
        url = f"https://api.tiingo.com/tiingo/daily/{ticker}/prices?startDate={start_date}&token={TIINGO_TOKEN}"
        resp = requests.get(url, headers={"Content-Type": "application/json"}, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            if data and isinstance(data, list) and len(data) > 0:
                df = pd.DataFrame(data)
                df["date"] = pd.to_datetime(df["date"])
                df.set_index("date", inplace=True)
                df.rename(columns={"open": "Open", "high": "High", "low": "Low", "close": "Close", "volume": "Volume"}, inplace=True)
                return df[["Open", "High", "Low", "Close", "Volume"]].dropna().sort_index()
    except Exception:
        pass
    return None


@st.cache_data(ttl=300)
def fetch_watchlist_data():
    """抓取日线 D1 (6个月) 与周线 W1 (1年) 周期大级别数据"""
    data_daily = {}
    data_weekly = {}

    for sym in ALL_SYMBOLS:
        df_d = fetch_from_tiingo_daily(sym) if sym == "SNDK" else None
        if df_d is None or df_d.empty:
            try:
                ticker = yf.Ticker(sym)
                df_yf = ticker.history(period="6mo", interval="1d")
                if df_yf is not None and not df_yf.empty:
                    if isinstance(df_yf.columns, pd.MultiIndex):
                        df_yf.columns = df_yf.columns.get_level_values(0)
                    df_d = df_yf[["Open", "High", "Low", "Close", "Volume"]].dropna(subset=["Close"]).copy()
            except Exception:
                pass
        if df_d is not None and not df_d.empty:
            data_daily[sym] = df_d

        try:
            ticker = yf.Ticker(sym)
            df_1w = ticker.history(period="1y", interval="1wk")
            if df_1w is not None and not df_1w.empty:
                if isinstance(df_1w.columns, pd.MultiIndex):
                    df_1w.columns = df_1w.columns.get_level_values(0)
                data_weekly[sym] = df_1w[["Open", "High", "Low", "Close", "Volume"]].dropna(subset=["Close"]).copy()
        except Exception:
            pass

    return data_daily, data_weekly


def analyze_watchlist_rotation(data_daily, data_weekly):
    if "QQQ" not in data_daily or data_daily["QQQ"].empty:
        return None

    qqq_d = data_daily["QQQ"]
    qqq_curr = float(qqq_d["Close"].iloc[-1])
    qqq_prev = float(qqq_d["Close"].iloc[-2]) if len(qqq_d) >= 2 else qqq_curr
    qqq_chg_d = ((qqq_curr - qqq_prev) / qqq_prev) * 100

    qqq_ma20 = float(qqq_d["Close"].rolling(20).mean().iloc[-1]) if len(qqq_d) >= 20 else qqq_curr
    qqq_ma50 = float(qqq_d["Close"].rolling(50).mean().iloc[-1]) if len(qqq_d) >= 50 else qqq_curr
    qqq_trend = "🟢 多头主升 (MA20上方)" if qqq_curr >= qqq_ma20 else ("🟡 震荡中继" if qqq_curr >= qqq_ma50 else "🔴 空头承压 (破位下行)")

    all_rows = []
    zones_map = {}
    bull_count, bear_count = 0, 0

    for sym, cfg in TICKERS_CONFIG.items():
        found = False
        if sym in data_daily and len(data_daily[sym]) >= 20:
            df_s = data_daily[sym]
            c_p = float(df_s["Close"].iloc[-1])
            p_p = float(df_s["Close"].iloc[-2])
            chg_d = ((c_p - p_p) / p_p) * 100
            spread_vs_qqq = chg_d - qqq_chg_d

            ma20 = float(df_s["Close"].rolling(20).mean().iloc[-1])
            ma50 = float(df_s["Close"].rolling(50).mean().iloc[-1]) if len(df_s) >= 50 else ma20
            avg_vol20 = float(df_s["Volume"].iloc[-20:].mean())
            cur_vol = float(df_s["Volume"].iloc[-1])
            vol_ratio = cur_vol / avg_vol20 if avg_vol20 > 0 else 1.0

            pwh = c_p * 1.05
            pwl = c_p * 0.95
            if sym in data_weekly and len(data_weekly[sym]) >= 3:
                pwh = float(data_weekly[sym]["High"].iloc[-2])
                pwl = float(data_weekly[sym]["Low"].iloc[-2])

            buy_low = min(pwl * 0.98, ma50 * 0.98)
            buy_high = max(pwl * 1.02, ma50 * 1.01)

            hold_low = ma50 * 1.01
            hold_high = pwh * 0.98
            if hold_high <= hold_low:
                hold_high = hold_low * 1.08

            sell_low = pwh * 0.98
            sell_high = pwh * 1.05

            buy_range_str = f"${buy_low:.2f} - ${buy_high:.2f}"
            hold_range_str = f"${hold_low:.2f} - ${hold_high:.2f}"
            sell_range_str = f"${sell_low:.2f} - ${sell_high:.2f}"

            if spread_vs_qqq >= 0: bull_count += 1
            else: bear_count += 1

            dist_ma50_pct = ((c_p - ma50) / ma50) * 100
            dist_pwl_pct = ((c_p - pwl) / pwl) * 100

            if c_p >= ma20 and spread_vs_qqq >= 0 and vol_ratio >= 1.0:
                phase = "🚀 阶段2: 主升"
                action = "【加仓/持有】"
            elif (abs(dist_pwl_pct) <= 2.5 or abs(dist_ma50_pct) <= 2.0) and vol_ratio <= 1.2:
                phase = "🟢 阶段1: 筑底"
                action = "【分批买入】"
            elif c_p >= ma20 and vol_ratio >= 1.8 and spread_vs_qqq < 0:
                phase = "⚠️ 阶段3: 滞涨"
                action = "【止盈卖出】"
            else:
                phase = "🔴 阶段4: 破位"
                action = "【坚决观望】"

            found = True
            all_rows.append({
                "sym_key": sym,
                "标的": f"{sym} ({cfg['name']})",
                "现价 ($)": round(c_p, 2),
                "日涨跌 (%)": round(chg_d, 2),
                "相对QQQ (%)": round(spread_vs_qqq, 2),
                "买入建仓区间 (Buy)": buy_range_str,
                "持仓波段区间 (Hold)": hold_range_str,
                "减仓卖出区间 (Sell)": sell_range_str,
                "实操指令 (Action)": action,
                "轮动阶段": phase,
                "vol_ratio": vol_ratio
            })

            zones_map[sym] = {
                "buy_low": buy_low, "buy_high": buy_high,
                "hold_low": hold_low, "hold_high": hold_high,
                "sell_low": sell_low, "sell_high": sell_high,
                "pwh": pwh, "pwl": pwl, "ma20": ma20, "ma50": ma50
            }

        if not found:
            bear_count += 1
            all_rows.append({
                "sym_key": sym,
                "标的": f"{sym} ({cfg['name']})",
                "现价 ($)": 0.0,
                "日涨跌 (%)": 0.0,
                "相对QQQ (%)": 0.0,
                "买入建仓区间 (Buy)": "同步中",
                "持仓波段区间 (Hold)": "同步中",
                "减仓卖出区间 (Sell)": "同步中",
                "实操指令 (Action)": "【暂且观望】",
                "轮动阶段": "⚪ 阶段0: 同步",
                "vol_ratio": 0.0
            })

    if "QQQ" in data_daily and len(data_daily["QQQ"]) >= 20:
        q_df = data_daily["QQQ"]
        q_cp = float(q_df["Close"].iloc[-1])
        q_pwh = float(data_weekly["QQQ"]["High"].iloc[-2]) if "QQQ" in data_weekly and len(data_weekly["QQQ"]) >= 3 else q_cp * 1.03
        q_pwl = float(data_weekly["QQQ"]["Low"].iloc[-2]) if "QQQ" in data_weekly and len(data_weekly["QQQ"]) >= 3 else q_cp * 0.97
        zones_map["QQQ"] = {
            "buy_low": q_pwl * 0.985, "buy_high": q_pwl * 1.015,
            "hold_low": qqq_ma50, "hold_high": q_pwh * 0.985,
            "sell_low": q_pwh * 0.985, "sell_high": q_pwh * 1.03,
            "pwh": q_pwh, "pwl": q_pwl, "ma20": qqq_ma20, "ma50": qqq_ma50
        }

    df_result = pd.DataFrame(all_rows).sort_values(by="相对QQQ (%)", ascending=False)

    return {
        "timestamp_myt": datetime.datetime.now(tz_myt).strftime("%Y-%m-%d %H:%M MYT"),
        "timestamp_ny": datetime.datetime.now(tz_ny).strftime("%Y-%m-%d %H:%M ET"),
        "qqq_curr": qqq_curr,
        "qqq_chg_d": qqq_chg_d,
        "qqq_trend": qqq_trend,
        "bull_count": bull_count,
        "bear_count": bear_count,
        "df_result": df_result,
        "zones_map": zones_map
    }


def render_stock_zone_chart(sym, df_daily, zones):
    """绘制 TradingView 旗舰级 K 线图：主副图严丝合缝垂直对齐"""
    if df_daily is None or df_daily.empty or len(df_daily) < 10:
        st.warning(f"标的 {sym} 暂无足够日线历史数据。")
        return

    df = df_daily.tail(75).copy()
    time_series = df.index.strftime('%Y-%m-%d').tolist()

    df["MA20"] = df["Close"].rolling(20).mean()
    df["MA50"] = df["Close"].rolling(50).mean()
    df["VMA20"] = df["Volume"].rolling(20).mean()

    df["High_Roll"] = df["High"].rolling(7, center=True).max()
    df["Low_Roll"] = df["Low"].rolling(7, center=True).min()
    peak_highs = df[df["High"] == df["High_Roll"]]
    valley_lows = df[df["Low"] == df["Low_Roll"]]

    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.74, 0.26],
        subplot_titles=(None, None)
    )

    # 1. TradingView 质感 K 线
    fig.add_trace(go.Candlestick(
        x=time_series,
        open=df['Open'], high=df['High'],
        low=df['Low'], close=df['Close'],
        name="日线 K 线",
        increasing_line_color="#089981", increasing_fillcolor="#089981",
        decreasing_line_color="#F23645", decreasing_fillcolor="#F23645",
        line=dict(width=1.2)
    ), row=1, col=1)

    # 2. 均线与机构生命线
    fig.add_trace(go.Scatter(
        x=time_series, y=df["MA20"],
        line=dict(color="#F59E0B", width=1.6), name="MA20 (动量生命线)"
    ), row=1, col=1)

    fig.add_trace(go.Scatter(
        x=time_series, y=df["MA50"],
        line=dict(color="#38BDF8", width=1.8), name="MA50 (机构中枢成本线)"
    ), row=1, col=1)

    # 3. 趋势通道线
    if len(peak_highs) >= 2:
        last_peaks = peak_highs.tail(3)
        fig.add_trace(go.Scatter(
            x=last_peaks.index.strftime('%Y-%m-%d'), y=last_peaks["High"],
            mode="lines", line=dict(color="rgba(244, 63, 94, 0.6)", width=1.5, dash="dashdot"),
            name="波段高点阻力趋势线"
        ), row=1, col=1)

    if len(valley_lows) >= 2:
        last_valleys = valley_lows.tail(3)
        fig.add_trace(go.Scatter(
            x=last_valleys.index.strftime('%Y-%m-%d'), y=last_valleys["Low"],
            mode="lines", line=dict(color="rgba(52, 211, 153, 0.6)", width=1.5, dash="dashdot"),
            name="波段低点支撑趋势线"
        ), row=1, col=1)

    # 4. 战区色带与触点扫描
    annotations = []
    if zones:
        fig.add_hrect(
            y0=zones["buy_low"], y1=zones["buy_high"],
            fillcolor="rgba(16, 185, 129, 0.16)", line_width=1, line_color="#10B981",
            layer="below", row=1, col=1
        )
        fig.add_hrect(
            y0=zones["hold_low"], y1=zones["hold_high"],
            fillcolor="rgba(59, 130, 246, 0.08)", line_width=1, line_dash="dash", line_color="rgba(59, 130, 246, 0.4)",
            layer="below", row=1, col=1
        )
        fig.add_hrect(
            y0=zones["sell_low"], y1=zones["sell_high"],
            fillcolor="rgba(239, 68, 68, 0.16)", line_width=1, line_color="#EF4444",
            layer="below", row=1, col=1
        )

        recent_scan = df.tail(15)
        for d_str, row_k in recent_scan.iterrows():
            d_fmt = d_str.strftime('%Y-%m-%d')
            if row_k["Low"] <= zones["buy_high"] and row_k["High"] >= zones["buy_low"]:
                annotations.append(dict(
                    x=d_fmt, y=row_k["Low"], xref="x1", yref="y1",
                    text="🟢 买区触碰", showarrow=True, arrowhead=2, arrowsize=1, arrowwidth=1.5,
                    arrowcolor="#10B981", ax=0, ay=32,
                    bgcolor="#064E3B", bordercolor="#10B981", borderwidth=1,
                    font=dict(color="#6EE7B7", size=9, family="Consolas")
                ))
            elif row_k["High"] >= zones["sell_low"] and row_k["Low"] <= zones["sell_high"]:
                annotations.append(dict(
                    x=d_fmt, y=row_k["High"], xref="x1", yref="y1",
                    text="⚠️ 卖区触碰", showarrow=True, arrowhead=2, arrowsize=1, arrowwidth=1.5,
                    arrowcolor="#EF4444", ax=0, ay=-32,
                    bgcolor="#7F1D1D", bordercolor="#EF4444", borderwidth=1,
                    font=dict(color="#FCA5A5", size=9, family="Consolas")
                ))

        fig.add_hline(y=zones["pwh"], line_dash="dot", line_color="#FCD34D", line_width=1.2, annotation_text=f" 周高 PWH: ${zones['pwh']:.2f}", annotation_position="top left", row=1, col=1)
        fig.add_hline(y=zones["pwl"], line_dash="dot", line_color="#93C5FD", line_width=1.2, annotation_text=f" 周低 PWL: ${zones['pwl']:.2f}", annotation_position="bottom left", row=1, col=1)

    # 5. 副图成交量与均量线 (严格绑定相同的分类 X 轴与固定柱体宽度)
    bar_colors = np.where(df["Close"] >= df["Open"], "#089981", "#F23645")
    fig.add_trace(go.Bar(
        x=time_series, y=df["Volume"],
        name="日成交量", marker=dict(color=bar_colors),
        width=0.65  # 统一柱体宽度
    ), row=2, col=1)

    fig.add_trace(go.Scatter(
        x=time_series, y=df["VMA20"],
        line=dict(color="#E5E7EB", width=1.2), name="20日均量"
    ), row=2, col=1)

    cfg_name = TICKERS_CONFIG.get(sym, {}).get("name", "大盘基准" if sym == "QQQ" else sym)
    
    fig.update_layout(
        title=dict(
            text=f"<b>{sym} ({cfg_name}) 旗舰日线战区走势</b> <span style='font-size:12px; color:#94A3B8;'>[滚轮缩放 / 拖拽平移 / 双击复位]</span>",
            font=dict(family="Consolas, monospace", size=14, color="#F8FAFC"),
            x=0.01, y=0.98
        ),
        height=580,
        margin=dict(l=10, r=10, t=45, b=10),
        template="plotly_dark",
        paper_bgcolor="#0B0F19",
        plot_bgcolor="#0B0F19",
        hovermode="x unified",
        xaxis_rangeslider_visible=False,
        dragmode="pan",
        legend=dict(
            orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=0.99,
            font=dict(size=10, color="#94A3B8"), bgcolor="rgba(15, 23, 42, 0.8)", bordercolor="#334155", borderwidth=1
        ),
        annotations=annotations
    )

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

    st.plotly_chart(
        fig,
        use_container_width=True,
        config={
            "scrollZoom": True,
            "displayModeBar": True,
            "modeBarButtonsToRemove": ["lasso2d", "select2d"],
            "displaylogo": False,
            "toImageButtonOptions": {"format": "png", "filename": f"{sym}_daily_chart"}
        }
    )


def generate_facts_markdown(res):
    """构建给 AI 诊断的纯客观事实数据"""
    df = res["df_result"]
    md = f"""# 📡 QQQ 宏观与 13 核心标的客观买卖点事实战报 (Facts Only)

### 1. QQQ 宏观风向中枢
- **截面时间**: `{res['timestamp_myt']}` (美东 `{res['timestamp_ny']}`)
- **QQQ 指数基准**: 现价 `${res['qqq_curr']:.2f}` ({res['qqq_chg_d']:+.2f}%) | 日线大趋势: `{res['qqq_trend']}`
- **全场多空分布**: 共 `{res['bull_count']}/13` 只跑赢大盘 (跑输 `{res['bear_count']}/13` 只)

### 2. 13 核心标的买入/持仓/卖出区间与实操指令表
| 标的 | 现价 ($) | 日涨跌 (%) | 相对QQQ (%) | 买入建仓区间 (Buy) | 持仓波段区间 (Hold) | 减仓卖出区间 (Sell) | 实操指令 (Action) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
"""
    for _, r in df.iterrows():
        md += f"| **{r['标的']}** | {r['现价 ($)']:.2f} | {r['日涨跌 (%)']:+.2f}% | {r['相对QQQ (%)']:+.2f}% | {r['买入建仓区间 (Buy)']} | {r['持仓波段区间 (Hold)']} | {r['减仓卖出区间 (Sell)']} | {r['实操指令 (Action)']} |\n"

    md += """
---
### 🤖 给 AI 的诊断 Prompt:
请依据上述 13 核心标的的现价所处区间（Buy / Hold / Sell Area）与相对 QQQ 强弱：
1. 诊断哪些标的已回踩进入【买入建仓区域】且量能缩量企稳，适合挂单分批买入；
2. 诊断哪些标的已逼近【减仓卖出区域】需要止盈落袋；
3. 结合 13 标的结构判定今晚 QQQ 大盘走向与防守策略。
"""
    return md


def render_macro_radar_tab():
    st.subheader("📋 13 核心标的宏观 Watchlist (买卖点位罗盘 & 日线战区图)")

    c1, c2 = st.columns([4, 1])
    with c1:
        st.caption("基于日线 D1 均线与周线 W1 极值量化买入/持仓/卖出价格区间。点击下方标的按钮即可穿透查看单股日线图、三大战区色带与触点分析。")
    with c2:
        if st.button("🔄 刷新 Watchlist", key="btn_refresh_watchlist_v9"):
            st.cache_data.clear()
            st.rerun()

    with st.spinner("正在提取日周线行情并计算买卖点位区间..."):
        d_daily, d_weekly = fetch_watchlist_data()

    res = analyze_watchlist_rotation(d_daily, d_weekly)
    if not res:
        st.warning("行情连接中，请稍后点击上方刷新。")
        return

    bull_cnt = res["bull_count"]
    bear_cnt = res["bear_count"]

    # 1. 顶层：QQQ 大盘宏观指标条
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("🎯 QQQ 现价", f"${res['qqq_curr']:.2f}", f"{res['qqq_chg_d']:+.2f}%")
    m2.metric("📈 QQQ 日线大趋势", res["qqq_trend"])
    m3.metric("🟢 水上跑赢大盘", f"{bull_cnt} 只", f"占比 {(bull_cnt/13)*100:.0f}%")
    m4.metric("🔴 水下跑输大盘", f"{bear_cnt} 只", f"占比 {(bear_cnt/13)*100:.0f}%")

    st.markdown("---")

    # 2. 中部：包含精准价格区间的专业 Watchlist 表格
    st.markdown("#### 📊 13 核心标的精准点位 Watchlist (从强到弱)")
    
    df_show = res["df_result"][["标的", "现价 ($)", "日涨跌 (%)", "相对QQQ (%)", "买入建仓区间 (Buy)", "持仓波段区间 (Hold)", "减仓卖出区间 (Sell)", "实操指令 (Action)"]]

    def style_watchlist(row):
        styles = [""] * len(row)
        chg_idx = df_show.columns.get_loc("日涨跌 (%)")
        sp_idx = df_show.columns.get_loc("相对QQQ (%)")
        act_idx = df_show.columns.get_loc("实操指令 (Action)")
        buy_idx = df_show.columns.get_loc("买入建仓区间 (Buy)")
        sell_idx = df_show.columns.get_loc("减仓卖出区间 (Sell)")

        chg_val = row["日涨跌 (%)"]
        sp_val = row["相对QQQ (%)"]
        act_val = row["实操指令 (Action)"]

        if chg_val > 0:
            styles[chg_idx] = "color: #10B981; font-weight: bold;"
        elif chg_val < 0:
            styles[chg_idx] = "color: #EF4444; font-weight: bold;"

        if sp_val >= 0:
            styles[sp_idx] = "color: #10B981; font-weight: bold;"
        else:
            styles[sp_idx] = "color: #EF4444; font-weight: bold;"

        styles[buy_idx] = "color: #93C5FD;"
        styles[sell_idx] = "color: #FCD34D;"

        if "分批买入" in act_val:
            styles[act_idx] = "background-color: #1E3A8A; color: #93C5FD; font-weight: bold;"
        elif "加仓" in act_val:
            styles[act_idx] = "background-color: #064E3B; color: #6EE7B7; font-weight: bold;"
        elif "止盈" in act_val:
            styles[act_idx] = "background-color: #78350F; color: #FCD34D; font-weight: bold;"
        elif "坚决观望" in act_val:
            styles[act_idx] = "background-color: #7F1D1D; color: #FCA5A5; font-weight: bold;"

        return styles

    styled_df = df_show.style.apply(style_watchlist, axis=1)
    st.dataframe(styled_df, use_container_width=True, height=380, hide_index=True)

    st.markdown("---")

    # 3. 核心交互层：TradingView 旗舰穿透日线图表
    st.markdown("#### 🎯 单股日线战区穿透分析与触点扫描 (点击切换标的)")

    chip_options = ["QQQ"] + list(TICKERS_CONFIG.keys())
    if "selected_chart_sym" not in st.session_state:
        st.session_state["selected_chart_sym"] = "NVDA"

    chip_cols = st.columns(len(chip_options))
    for idx, sym_opt in enumerate(chip_options):
        with chip_cols[idx]:
            is_active = (st.session_state["selected_chart_sym"] == sym_opt)
            btn_label = f"👉 {sym_opt}" if is_active else sym_opt
            if st.button(btn_label, key=f"chip_btn_{sym_opt}"):
                st.session_state["selected_chart_sym"] = sym_opt
                st.rerun()

    active_sym = st.session_state["selected_chart_sym"]
    sym_zones = res["zones_map"].get(active_sym)
    df_active = d_daily.get(active_sym)

    render_stock_zone_chart(active_sym, df_active, sym_zones)

    st.markdown("---")

    # 4. 底部：纯净 Markdown 事实数据包一键复制
    st.markdown("#### 🤖 AI 深度分析数据包 (点击右上角一键复制)")
    ai_md = generate_facts_markdown(res)
    st.code(ai_md, language="markdown")
