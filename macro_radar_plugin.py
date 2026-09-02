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

# 13 核心标的配置
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

    # 2B 假突破
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

    fig.add_trace(go.Candlestick(
        x=df.index.strftime('%Y-%m-%d'),
        open=df['Open'], high=df['High'],
        low=df['Low'], close=df['Close'],
        name="日线 K 线",
        increasing_line_color="#089981", increasing_fillcolor="#089981",
        decreasing_line_color="#F23645", decreasing_fillcolor="#F23645",
        line=dict(width=1.2)
    ), row=1, col=1)

    fig.add_trace(go.Scatter(
        x=df.index.strftime('%Y-%m-%d'), y=df["MA20"],
        line=dict(color="#F59E0B", width=1.6), name="MA20"
    ), row=1, col=1)

    fig.add_trace(go.Scatter(
        x=df.index.strftime('%Y-%m-%d'), y=df["MA50"],
        line=dict(color="#38BDF8", width=1.8), name="MA50"
    ), row=1, col=1)

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
            text=f"<b>{sym} ({cfg_name}) 日线战区穿透分析</b>",
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
        st.markdown("<div style='height:28px;'></div>", unsafe_allow_html=True)
        if st.button("💾 存入/更新", key="btn_save_pos_manual"):
            if in_sym:
                if not df_pos.empty and in_sym in df_pos["Symbol"].values:
                    df_pos.loc[df_pos["Symbol"] == in_sym, ["Shares", "AvgCost"]] = [in_shares, in_cost]
                else:
                    new_row = pd.DataFrame([{"Symbol": in_sym, "Shares": in_shares, "AvgCost": in_cost}])
                    df_pos = pd.concat([df_pos, new_row], ignore_index=True)
                save_portfolio_data(df_pos)
                st.success(f"已成功更新 {in_sym} 持仓！")
                st.rerun()

    rows_summary = []
    total_market_val = 0.0
    total_unrealized_pnl = 0.0

    if not df_pos.empty:
        for idx, r in df_pos.iterrows():
            sym = str(r["Symbol"]).upper().strip()
            shares = float(r["Shares"])
            cost = float(r["AvgCost"])
            cost_total = shares * cost

            curr_info = price_lookup.get(sym, None)
            df_s = data_daily.get(sym, None)
            pattern_txt, _ = detect_candlestick_patterns(df_s)

            if curr_info and curr_info.get("price", 0) > 0:
                curr_p = float(curr_info["price"])
                buy_zone = curr_info.get("buy_zone", "-")
                sell_zone = curr_info.get("sell_zone", "-")
                phase = curr_info.get("phase", "阶段2")
            else:
                curr_p = cost
                buy_zone = "-"
                sell_zone = "-"
                phase = "同步中"

            market_val = shares * curr_p
            pnl_dollar = market_val - cost_total
            pnl_pct = (pnl_dollar / cost_total) * 100 if cost_total > 0 else 0.0

            if "黄昏之星" in pattern_txt or "看跌吞没" in pattern_txt or "2B Top" in pattern_txt or "滞涨" in phase:
                action_advice = "🚨 建议减仓/卖出 (锁定利润，释放资金)"
            elif "早晨之星" in pattern_txt or "看涨吞没" in pattern_txt or "2B Bottom" in pattern_txt:
                action_advice = "🟢 强力买入/补仓 (经典反转形态确立)"
            elif "主升" in phase:
                action_advice = "🚀 顺势持有 (主升浪奔跑，保本止损)"
            elif "破位" in phase:
                action_advice = "⚠️ 设防支撑 (跌破止损，严禁盲目加仓)"
            else:
                action_advice = "⚪ 防守持有/观望"

            total_market_val += market_val
            total_unrealized_pnl += pnl_dollar

            rows_summary.append({
                "代码": sym,
                "持股数": round(shares, 4) if shares % 1 != 0 else int(shares),
                "成本 ($)": round(cost, 2),
                "现价 ($)": round(curr_p, 2),
                "市值 ($)": round(market_val, 2),
                "浮动盈亏 ($)": round(pnl_dollar, 2),
                "盈亏率 (%)": round(pnl_pct, 2),
                "K线形态": pattern_txt,
                "减仓卖出区": sell_zone,
                "实操指令": action_advice
            })

    total_account_nav = total_market_val + cash_capital
    total_cost_basis = total_market_val - total_unrealized_pnl
    total_pnl_pct = (total_unrealized_pnl / total_cost_basis * 100) if total_cost_basis > 0 else 0.0

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("💰 账户总资产 (NAV)", f"${total_account_nav:,.2f}", f"整体盈亏: {total_pnl_pct:+.2f}%")
    m2.metric("📊 持仓总市值", f"${total_market_val:,.2f}", f"仓位: {(total_market_val/total_account_nav*100):.1f}%" if total_account_nav > 0 else "0%")
    m3.metric("💵 可用现金 Capital", f"${cash_capital:,.2f}", "机动流动性")
    m4.metric("📈 浮动总盈亏", f"{total_unrealized_pnl:+,.2f} USD", f"{total_pnl_pct:+.2f}%")

    st.markdown("---")

    if rows_summary:
        st.markdown("##### 📋 持仓资产与形态诊断明细")
        df_display = pd.DataFrame(rows_summary)
        st.dataframe(df_display, use_container_width=True, hide_index=True)

        with st.expander("🗑️ 平仓 / 移除某只持仓代码"):
            del_sym = st.selectbox("选择平仓标的", options=df_pos["Symbol"].tolist(), key="del_pos_picker_tab1")
            if st.button(f"确认清仓移除 {del_sym}", key="btn_confirm_del_tab1"):
                df_pos = df_pos[df_pos["Symbol"] != del_sym]
                save_portfolio_data(df_pos)
                st.success(f"已成功平仓移除 {del_sym}！")
                st.rerun()

    st.markdown("---")
    st.markdown("##### 🎯 闲置现金滚动买入推荐池")
    held_syms = df_pos["Symbol"].tolist() if not df_pos.empty else []

    buy_candidates = []
    if isinstance(price_lookup, dict):
        for s, v in price_lookup.items():
            if s not in held_syms and ("筑底" in v.get("phase", "") or "分批买入" in v.get("action", "") or "早晨之星" in v.get("pattern", "")):
                buy_candidates.append({"sym": s, "price": v.get("price", 0.0), "action": v.get("action", ""), "buy_zone": v.get("buy_zone", "-")})

    c_rec1, c_rec2 = st.columns(2)
    with c_rec1:
        st.markdown("🟢 **推荐逢低建仓池 (阶段1 / 反转形态)**")
        if buy_candidates:
            for b in buy_candidates:
                p = b["price"]
                max_s = int(cash_capital // p) if p > 0 else 0
                st.success(f"**{b['sym']}** | 现价: `${p:.2f}` | 建仓区: `{b['buy_zone']}` | 可买: `{max_s} 股`\n\n*建议*: `{b['action']}`")
        else:
            st.info("当前 13 监控池中暂无可逢低建仓的未持仓标的。")

    with c_rec2:
        st.markdown("💡 **资金滚动调仓法则**")
        st.write("1. 持仓股进入 **⚠️ 阶段3 (滞涨)** 或出现 **黄昏之星/看跌吞没** 时，逢高部分减仓换回现金；")
        st.write("2. 将收回的现金滚动买入左侧 **🟢 阶段1 (筑底)** 或出现 **早晨之星** 的新龙头。")

    st.markdown("---")
    st.markdown("#### 🤖 AI 形态与资产滚动诊断数据包 (点击右上角复制)")
    md_report = f"""# 💼 交易员实操持仓与形态学精准买卖点 AI 战报

### 1. 账户资产全景
- **总资产 (NAV)**: `${total_account_nav:,.2f}` | **持仓总市值**: `${total_market_val:,.2f}` | **可用现金**: `${cash_capital:,.2f}`
- **浮动总盈亏**: `${total_unrealized_pnl:+,.2f}` ({total_pnl_pct:+.2f}%)

### 2. 持仓形态学与买卖点分析
| 代码 | 股数 | 成本 ($) | 现价 ($) | 盈亏 ($ / %) | K线形态分析 | 减仓目标区 | 实操指令 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
"""
    for r in rows_summary:
        md_report += f"| **{r['代码']}** | {r['持股数']} | {r['成本 ($)']:.2f} | {r['现价 ($)']:.2f} | {r['浮动盈亏 ($)']:+.2f} ({r['盈亏率 (%)']:+.2f}%) | {r['K线形态']} | {r['减仓卖出区']} | {r['实操指令']} |\n"

    md_report += f"""
---
### 💡 给 AI 的诊断 Prompt:
请依据以上持仓的 K 线形态学（Morning Star / Evening Star / Engulfing / 2B）、买卖点区间与可用现金 `${cash_capital:,.2f}`：
1. 评估是否有标的出现见顶形态（如黄昏之星/看跌吞没）需要立即减仓；
2. 结合 13 核心标的，指出哪些未持仓标的出现了早晨之星或看涨吞没反转，建议如何分批建仓；
3. 给出精准的进场价、止损价与 1:2 止盈目标位。
"""
    st.code(md_report, language="markdown")

def render_macro_radar_tab():
    st.subheader("📋 13 核心标的宏观 Watchlist (买卖点位罗盘 & 日线战区图)")

    c1, c2 = st.columns([4, 1])
    with c1:
        st.caption("基于日线 D1 均线与周线 W1 极值量化买入/持仓/卖出价格区间与形态学。点击下方标的按钮可穿透查看单股日线图。")
    with c2:
        if st.button("🔄 刷新全景数据", key="btn_refresh_macro_full_v9"):
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

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("🎯 QQQ 现价", f"${res['qqq_curr']:.2f}", f"{res['qqq_chg_d']:+.2f}%")
    m2.metric("📈 QQQ 日线大趋势", res["qqq_trend"])
    m3.metric("🟢 水上跑赢大盘", f"{bull_cnt} 只", f"占比 {(bull_cnt/13)*100:.0f}%")
    m4.metric("🔴 水下跑输大盘", f"{bear_cnt} 只", f"占比 {(bear_cnt/13)*100:.0f}%")

    st.markdown("---")
    st.markdown("#### 📊 13 核心标的精准点位与形态 Watchlist (从强到弱)")
    
    df_show = res["df_result"][["标的", "现价 ($)", "日涨跌 (%)", "相对QQQ (%)", "K线形态", "买入建仓区间 (Buy)", "持仓波段区间 (Hold)", "减仓卖出区间 (Sell)", "实操指令 (Action)"]]

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

        if chg_val > 0: styles[chg_idx] = "color: #10B981; font-weight: bold;"
        elif chg_val < 0: styles[chg_idx] = "color: #EF4444; font-weight: bold;"

        if sp_val >= 0: styles[sp_idx] = "color: #10B981; font-weight: bold;"
        else: styles[sp_idx] = "color: #EF4444; font-weight: bold;"

        styles[buy_idx] = "color: #93C5FD;"
        styles[sell_idx] = "color: #FCD34D;"

        if "分批买入" in act_val: styles[act_idx] = "background-color: #1E3A8A; color: #93C5FD; font-weight: bold;"
        elif "加仓" in act_val: styles[act_idx] = "background-color: #064E3B; color: #6EE7B7; font-weight: bold;"
        elif "止盈" in act_val: styles[act_idx] = "background-color: #78350F; color: #FCD34D; font-weight: bold;"
        elif "坚决观望" in act_val: styles[act_idx] = "background-color: #7F1D1D; color: #FCA5A5; font-weight: bold;"

        return styles

    styled_df = df_show.style.apply(style_watchlist, axis=1)
    st.dataframe(styled_df, use_container_width=True, height=380, hide_index=True)

    st.markdown("---")
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
    render_portfolio_section(res["price_lookup"], d_daily)
