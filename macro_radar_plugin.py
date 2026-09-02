# 文件名: macro_radar_plugin.py
# 作用: Tab 1 旗舰级看板 - 13 标的 Watchlist + TradingView 穿透战区图 + 实操持仓管理输入与形态学/资金滚动 AI 罗盘

import datetime
import os
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

PORTFOLIO_FILE = "portfolio_positions.csv"
TIINGO_TOKEN = "bcffe3a5cf7eeef085e405cfa4a3e5691b976217"

# 13 核心标的配置 (严格锁定 7 巨头 + 6 先锋)
TICKERS_CONFIG = {
    "NVDA": {"name": "英伟达", "weight": 3.0, "role": "AI算力总舵手"},
    "AAPL": {"name": "苹果", "weight": 3.0, "role": "消费电子龙头/防守"},
    "MSFT": {"name": "微软", "weight": 3.0, "role": "云端权重定海神针"},
    "AMZN": {"name": "亚马逊", "weight": 2.0, "role": "电商与云权重"},
    "GOOGL": {"name": "谷歌", "weight": 2.0, "role": "搜索广告权重"},
    "META": {"name": "Meta", "weight": 2.0, "role": "社交开源生态"},
    "TSLA": {"name": "特斯拉", "weight": 2.0, "role": "流动性与情绪先锋"},
    "AVGO": {"name": "博通", "weight": 2.0, "role": "网络芯片与ASIC龙头"},
    "MU": {"name": "美光", "weight": 1.0, "role": "存储/HBM龙头"},
    "AMD": {"name": "AMD", "weight": 1.0, "role": "算力二当家"},
    "WDC": {"name": "西部数据", "weight": 1.0, "role": "存储与硬盘核心"},
    "STX": {"name": "希捷", "weight": 1.0, "role": "企业级数据中心存储"},
    "SNDK": {"name": "闪迪", "weight": 1.0, "role": "存储极端情绪标的"},
}

ALL_SYMBOLS = ["QQQ"] + list(TICKERS_CONFIG.keys())

DEFAULT_INIT_POSITIONS = [
    {"Symbol": "NVDA", "Shares": 10.0, "AvgCost": 199.987},
    {"Symbol": "SNDK", "Shares": 1.4281, "AvgCost": 1488.579},
    {"Symbol": "QQQM", "Shares": 7.0, "AvgCost": 294.530},
    {"Symbol": "SKHY", "Shares": 4.0, "AvgCost": 171.930},
    {"Symbol": "DRAM", "Shares": 10.0, "AvgCost": 55.180}
]

# ================= 1. 持仓本地数据管理 =================
def load_portfolio_data():
    if os.path.exists(PORTFOLIO_FILE):
        try:
            df = pd.read_csv(PORTFOLIO_FILE)
            if not df.empty:
                return df
        except Exception:
            pass
    df_init = pd.DataFrame(DEFAULT_INIT_POSITIONS)
    df_init.to_csv(PORTFOLIO_FILE, index=False, encoding="utf-8-sig")
    return df_init

def save_portfolio_data(df):
    df.to_csv(PORTFOLIO_FILE, index=False, encoding="utf-8-sig")

# ================= 2. 行情数据抓取 =================
def fetch_from_tiingo_daily(ticker):
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

# ================= 3. 形态学与量化指标计算 =================
def detect_candlestick_patterns(df_daily):
    if df_daily is None or len(df_daily) < 4:
        return "常规走势", "#9CA3AF"

    o3, h3, l3, c3 = df_daily["Open"].iloc[-3], df_daily["High"].iloc[-3], df_daily["Low"].iloc[-3], df_daily["Close"].iloc[-3]
    o2, h2, l2, c2 = df_daily["Open"].iloc[-2], df_daily["High"].iloc[-2], df_daily["Low"].iloc[-2], df_daily["Close"].iloc[-2]
    o1, h1, l1, c1 = df_daily["Open"].iloc[-1], df_daily["High"].iloc[-1], df_daily["Low"].iloc[-1], df_daily["Close"].iloc[-1]

    # 早晨之星
    is_c3_bear = (c3 < o3) and (abs(c3 - o3) >= 0.4 * (h3 - l3))
    is_c2_star = abs(c2 - o2) <= 0.35 * (h2 - l2) and (h2 < h3)
    is_c1_bull = (c1 > o1) and (c1 >= (o3 + c3) / 2)
    if is_c3_bear and is_c2_star and is_c1_bull:
        return "✨ 早晨之星 (Morning Star 底反)", "#10B981"

    # 黄昏之星
    is_c3_bull = (c3 > o3) and (abs(c3 - o3) >= 0.4 * (h3 - l3))
    is_c2_star_top = abs(c2 - o2) <= 0.35 * (h2 - l2) and (h2 > h3)
    is_c1_bear = (c1 < o1) and (c1 <= (o3 + c3) / 2)
    if is_c3_bull and is_c2_star_top and is_c1_bear:
        return "⚠️ 黄昏之星 (Evening Star 顶滞)", "#EF4444"

    # 看涨吞没
    if (c2 < o2) and (c1 > o1) and (c1 >= o2) and (o1 <= c2):
        return "🔥 看涨吞没 (Bullish Engulfing)", "#10B981"

    # 看跌吞没
    if (c2 > o2) and (c1 < o1) and (c1 <= o2) and (o1 >= c2):
        return "🚨 看跌吞没 (Bearish Engulfing)", "#EF4444"

    # 2B 破底翻
    prev_low_5 = df_daily["Low"].iloc[-6:-1].min() if len(df_daily) >= 6 else l2
    if (l1 < prev_low_5) and (c1 > prev_low_5) and (c1 > o1):
        return "⚓ 2B 破底翻 (2B Bottom 吸筹)", "#3B82F6"

    # 2B 顶
    prev_high_5 = df_daily["High"].iloc[-6:-1].max() if len(df_daily) >= 6 else h2
    if (h1 > prev_high_5) and (c1 < prev_high_5) and (c1 < o1):
        return "🚨 2B 假突破 (2B Top 诱多)", "#F59E0B"

    return "➖ 整理震荡", "#9CA3AF"

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
    price_lookup = {}
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

            pattern_desc, _ = detect_candlestick_patterns(df_s)

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
                "K线形态": pattern_desc,
                "买入建仓区间 (Buy)": buy_range_str,
                "持仓波段区间 (Hold)": hold_range_str,
                "减仓卖出区间 (Sell)": sell_range_str,
                "实操指令 (Action)": action,
                "轮动阶段": phase
            })

            zones_map[sym] = {
                "buy_low": buy_low, "buy_high": buy_high,
                "hold_low": hold_low, "hold_high": hold_high,
                "sell_low": sell_low, "sell_high": sell_high,
                "pwh": pwh, "pwl": pwl, "ma20": ma20, "ma50": ma50
            }

            price_lookup[sym] = {
                "price": c_p, "phase": phase, "action": action,
                "buy_zone": buy_range_str, "sell_zone": sell_range_str,
                "pattern": pattern_desc
            }

        if not found:
            bear_count += 1
            all_rows.append({
                "sym_key": sym,
                "标的": f"{sym} ({cfg['name']})",
                "现价 ($)": 0.0,
                "日涨跌 (%)": 0.0,
                "相对QQQ (%)": 0.0,
                "K线形态": "⚪ 待同步",
                "买入建仓区间 (Buy)": "同步中",
                "持仓波段区间 (Hold)": "同步中",
                "减仓卖出区间 (Sell)": "同步中",
                "实操指令 (Action)": "【暂且观望】",
                "轮动阶段": "⚪ 阶段0: 同步"
            })
            price_lookup[sym] = {
                "price": 0.0, "phase": "同步中", "action": "观望",
                "buy_zone": "-", "sell_zone": "-", "pattern": "无"
            }

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
        price_lookup["QQQ"] = {"price": q_cp, "phase": qqq_trend, "action": "大盘基准", "buy_zone": f"${q_pwl:.2f}", "sell_zone": f"${q_pwh:.2f}", "pattern": "基准"}

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
        "zones_map": zones_map,
        "price_lookup": price_lookup
    }

# ================= 4. TradingView 交互日线战区图 =================
def render_stock_zone_chart(sym, df_daily, zones):
    if df_daily is None or df_daily.empty or len(df_daily) < 10:
        st.warning(f"标的 {sym} 暂无足够日线历史数据。")
        return

    df = df_daily.tail(75).copy()
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
        row_heights=[0.74, 0.26]
    )

    # 1. K 线
    fig.add_trace(go.Candlestick(
        x=df.index.strftime('%Y-%m-%d'),
        open=df['Open'], high=df['High'],
        low=df['Low'], close=df['Close'],
        name="日线 K 线",
        increasing_line_color="#089981", increasing_fillcolor="#089981",
        decreasing_line_color="#F23645", decreasing_fillcolor="#F23645",
        line=dict(width=1.2)
    ), row=1, col=1)

    # 2. 均线
    fig.add_trace(go.Scatter(
        x=df.index.strftime('%Y-%m-%d'), y=df["MA20"],
        line=dict(color="#F59E0B", width=1.6), name="MA20 (动量生命线)"
    ), row=1, col=1)

    fig.add_trace(go.Scatter(
        x=df.index.strftime('%Y-%m-%d'), y=df["MA50"],
        line=dict(color="#38BDF8", width=1.8), name="MA50 (机构成本线)"
    ), row=1, col=1)

    # 3. 趋势通道线
    if len(peak_highs) >= 2:
        last_peaks = peak_highs.tail(3)
        fig.add_trace(go.Scatter(
            x=last_peaks.index.strftime('%Y-%m-%d'), y=last_peaks["High"],
            mode="lines", line=dict(color="rgba(244, 63, 94, 0.6)", width=1.5, dash="dashdot"),
            name="波段阻力线"
        ), row=1, col=1)

    if len(valley_lows) >= 2:
        last_valleys = valley_lows.tail(3)
        fig.add_trace(go.Scatter(
            x=last_valleys.index.strftime('%Y-%m-%d'), y=last_valleys["Low"],
            mode="lines", line=dict(color="rgba(52, 211, 153, 0.6)", width=1.5, dash="dashdot"),
            name="波段支撑线"
        ), row=1, col=1)

    # 4. 实操色带与触点
    annotations = []
    if zones:
        fig.add_hrect(y0=zones["buy_low"], y1=zones["buy_high"], fillcolor="rgba(16, 185, 129, 0.16)", line_width=1, line_color="#10B981", layer="below", row=1, col=1)
        fig.add_hrect(y0=zones["hold_low"], y1=zones["hold_high"], fillcolor="rgba(59, 130, 246, 0.08)", line_width=1, line_dash="dash", line_color="rgba(59, 130, 246, 0.4)", layer="below", row=1, col=1)
        fig.add_hrect(y0=zones["sell_low"], y1=zones["sell_high"], fillcolor="rgba(239, 68, 68, 0.16)", line_width=1, line_color="#EF4444", layer="below", row=1, col=1)

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

        fig.add_hline(y=zones["pwh"], line_dash="dot", line_color="#FCD34D", line_width=1.2, annotation_text=f" 周高: ${zones['pwh']:.2f}", annotation_position="top left", row=1, col=1)
        fig.add_hline(y=zones["pwl"], line_dash="dot", line_color="#93C5FD", line_width=1.2, annotation_text=f" 周低: ${zones['pwl']:.2f}", annotation_position="bottom left", row=1, col=1)

    # 5. 副图成交量
    bar_colors = np.where(df["Close"] >= df["Open"], "#089981", "#F23645")
    fig.add_trace(go.Bar(
        x=df.index.strftime('%Y-%m-%d'), y=df["Volume"],
        name="日成交量", marker=dict(color=bar_colors)
    ), row=2, col=1)

    fig.add_trace(go.Scatter(
        x=df.index.strftime('%Y-%m-%d'), y=df["VMA20"],
        line=dict(color="#E5E7EB", width=1.2), name="20日均量"
    ), row=2, col=1)

    cfg_name = TICKERS_CONFIG.get(sym, {}).get("name", "大盘基准" if sym == "QQQ" else sym)

    fig.update_layout(
        title=dict(
            text=f"<b>{sym} ({cfg_name}) 日线战区穿透分析</b> <span style='font-size:12px; color:#94A3B8;'>[滚轮缩放 / 拖拽平移 / 双击复位]</span>",
            font=dict(family="Consolas, monospace", size=14, color="#F8FAFC"),
            x=0.01, y=0.98
        ),
        height=540,
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

    fig.update_xaxes(type="category", gridcolor="#1E293B", showspikes=True, spikemode="across", spikesnap="cursor", spikecolor="#64748B", spikethickness=1, spikedash="dot", row=1, col=1)
    fig.update_yaxes(gridcolor="#1E293B", showspikes=True, spikemode="across", spikesnap="cursor", spikecolor="#64748B", spikethickness=1, spikedash="dot", row=1, col=1)
    fig.update_yaxes(gridcolor="#1E293B", row=2, col=1)

    st.plotly_chart(fig, use_container_width=True, config={"scrollZoom": True, "displayModeBar": True, "displaylogo": False})

# ================= 5. 实操持仓管理输入框与资金滚动 =================
def render_portfolio_section(price_lookup, data_daily):
    st.markdown("---")
    st.subheader("💼 我的实操持仓与资金滚动罗盘")
    st.caption("支持手动录入与调仓。系统自动结合形态学（晨星/暮星/吞没/2B）与资金轮动输出调仓建议。")

    df_pos = load_portfolio_data()

    # 1. 顶部输入框
    st.markdown("##### 📝 实操资产与调仓输入框")
    col_in1, col_in2, col_in3, col_in4, col_in5 = st.columns([1.5, 1.2, 1.2, 1.5, 1.0])
    with col_in1:
        cash_capital = st.number_input("💵 可用现金 Capital ($)", min_value=0.0, value=float(st.session_state.get("user_cash", 3.95)), step=100.0, key="in_cash_cap")
        st.session_state["user_cash"] = cash_capital
    with col_in2:
        in_sym = st.text_input("股票代码", value="NVDA", key="in_pos_sym").upper().strip()
    with col_in3:
        in_shares = st.number_input("持股数量", min_value=0.0001, value=10.0, step=1.0, key="in_pos_shares")
    with col_in4:
        def_cost = price_lookup.get(in_sym, {}).get("price", 100.0) if in_sym in price_lookup else 100.0
        in_cost = st.number_input("买入成本 ($)", min_value=0.01, value=float(def_cost) if def_cost > 0 else 100.0, step=1.0, key="in_pos_cost")
    with col_in5:
        st.markdown("<div 
