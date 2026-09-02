# 文件名: macro_radar_plugin.py
# 作用: Tab 1 专精看板 - 13 核心标的彩色战术 Watchlist + TradingView 交互日线穿透图

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

TIINGO_TOKEN = "bcffe3a5cf7eeef085e405cfa4a3e5691b976217"

TICKERS_CONFIG = {
    "NVDA": {"name": "英伟达", "weight": 3.0, "role": "AI算力总舵手"},
    "AAPL": {"name": "苹果", "weight": 3.0, "role": "消费电子/防守中枢"},
    "MSFT": {"name": "微软", "weight": 3.0, "role": "云端权重定海神针"},
    "AMZN": {"name": "亚马逊", "weight": 2.0, "role": "电商与云权重"},
    "GOOGL": {"name": "谷歌", "weight": 2.0, "role": "搜索广告权重"},
    "META": {"name": "Meta", "weight": 2.0, "role": "社交开源生态"},
    "TSLA": {"name": "特斯拉", "weight": 2.0, "role": "流动性先锋"},
    "AVGO": {"name": "博通", "weight": 2.0, "role": "网络芯片龙头"},
    "MU": {"name": "美光", "weight": 1.0, "role": "存储/HBM龙头"},
    "AMD": {"name": "AMD", "weight": 1.0, "role": "算力二当家"},
    "WDC": {"name": "西部数据", "weight": 1.0, "role": "存储与硬盘核心"},
    "STX": {"name": "希捷", "weight": 1.0, "role": "企业级存储"},
    "SNDK": {"name": "闪迪", "weight": 1.0, "role": "存储情绪标的"},
}

ALL_SYMBOLS = ["QQQ"] + list(TICKERS_CONFIG.keys())

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
    data_daily, data_weekly = {}, {}
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

    all_rows, zones_map, price_lookup = [], {}, {}
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
            if hold_high <= hold_low: hold_high = hold_low * 1.08
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
                "标的": f"{sym} ({cfg['name']})",
                "现价 ($)": round(c_p, 2),
                "日涨跌 (%)": round(chg_d, 2),
                "相对QQQ (%)": round(spread_vs_qqq, 2),
                "K线形态": "➖ 常规走势",
                "买入建仓区间 (Buy)": buy_range_str,
                "持仓波段区间 (Hold)": hold_range_str,
                "减仓卖出区间 (Sell)": sell_range_str,
                "实操指令 (Action)": action
            })

            zones_map[sym] = {
                "buy_low": buy_low, "buy_high": buy_high,
                "hold_low": hold_low, "hold_high": hold_high,
                "sell_low": sell_low, "sell_high": sell_high,
                "pwh": pwh, "pwl": pwl, "ma20": ma20, "ma50": ma50
            }

            price_lookup[sym] = {
                "price": c_p, "phase": phase, "action": action,
                "buy_zone": buy_range_str, "sell_zone": sell_range_str, "pattern": "➖"
            }

        if not found:
            bear_count += 1
            all_rows.append({
                "标的": f"{sym} ({cfg['name']})",
                "现价 ($)": 0.0,
                "日涨跌 (%)": 0.0,
                "相对QQQ (%)": 0.0,
                "K线形态": "⚪ 同步中",
                "买入建仓区间 (Buy)": "-",
                "持仓波段区间 (Hold)": "-",
                "减仓卖出区间 (Sell)": "-",
                "实操指令 (Action)": "【暂且观望】"
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

    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.74, 0.26])

    fig.add_trace(go.Candlestick(
        x=df.index.strftime('%Y-%m-%d'), open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'],
        name="日线 K 线", increasing_line_color="#00E676", decreasing_line_color="#FF5252", line=dict(width=1.2)
    ), row=1, col=1)

    fig.add_trace(go.Scatter(x=df.index.strftime('%Y-%m-%d'), y=df["MA20"], line=dict(color="#F59E0B", width=1.6), name="MA20 (动量生命线)"), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index.strftime('%Y-%m-%d'), y=df["MA50"], line=dict(color="#38BDF8", width=1.8), name="MA50 (机构成本线)"), row=1, col=1)

    if zones:
        fig.add_hrect(y0=zones["buy_low"], y1=zones["buy_high"], fillcolor="rgba(0, 230, 118, 0.16)", line_width=1, line_color="#00E676", layer="below", row=1, col=1)
        fig.add_hrect(y0=zones["sell_low"], y1=zones["sell_high"], fillcolor="rgba(255, 82, 82, 0.16)", line_width=1, line_color="#FF5252", layer="below", row=1, col=1)

    bar_colors = np.where(df["Close"] >= df["Open"], "#00E676", "#FF5252")
    fig.add_trace(go.Bar(x=df.index.strftime('%Y-%m-%d'), y=df["Volume"], name="日成交量", marker=dict(color=bar_colors)), row=2, col=1)

    fig.update_layout(
        height=520, margin=dict(l=10, r=10, t=35, b=10), template="plotly_dark",
        paper_bgcolor="#06090E", plot_bgcolor="#06090E", hovermode="x unified",
        xaxis_rangeslider_visible=False, dragmode="pan"
    )
    st.plotly_chart(fig, use_container_width=True, config={"scrollZoom": True, "displayModeBar": True, "displaylogo": False})

def render_macro_radar_tab():
    st.subheader("📋 13 核心标的宏观 Watchlist (买卖点位罗盘 & 日线战区图)")
    
    with st.spinner("正在提取日周线行情并计算买卖点位区间..."):
        d_daily, d_weekly = fetch_watchlist_data()

    res = analyze_watchlist_rotation(d_daily, d_weekly)
    if not res:
        st.warning("行情连接中，请稍后刷新。")
        return

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("🎯 QQQ 现价", f"${res['qqq_curr']:.2f}", f"{res['qqq_chg_d']:+.2f}%")
    m2.metric("📈 QQQ 日线大趋势", res["qqq_trend"])
    m3.metric("🟢 水上跑赢大盘", f"{res['bull_count']} 只", f"占比 {(res['bull_count']/13)*100:.0f}%")
    m4.metric("🔴 水下跑输大盘", f"{res['bear_count']} 只", f"占比 {(res['bear_count']/13)*100:.0f}%")

    st.markdown("---")
    st.markdown("#### 📊 13 核心标的精准点位与形态 Watchlist (从强到弱)")

    # ---------------- 战术高亮着色核心函数 ----------------
    df_raw = res["df_result"].copy()

    def apply_watchlist_theme(row):
        styles = [""] * len(row)
        sym_idx = df_raw.columns.get_loc("标的")
        price_idx = df_raw.columns.get_loc("现价 ($)")
        chg_idx = df_raw.columns.get_loc("日涨跌 (%)")
        sp_idx = df_raw.columns.get_loc("相对QQQ (%)")
        buy_idx = df_raw.columns.get_loc("买入建仓区间 (Buy)")
        hold_idx = df_raw.columns.get_loc("持仓波段区间 (Hold)")
        sell_idx = df_raw.columns.get_loc("减仓卖出区间 (Sell)")
        act_idx = df_raw.columns.get_loc("实操指令 (Action)")

        chg_v = row["日涨跌 (%)"]
        sp_v = row["相对QQQ (%)"]
        act_v = row["实操指令 (Action)"]

        styles[sym_idx] = "color: #FFFFFF; font-weight: 800; font-size: 14px;"
        styles[price_idx] = "color: #FFFFFF; font-weight: 700; font-family: 'JetBrains Mono';"

        # 涨跌与相对强度
        if chg_v > 0: styles[chg_idx] = "color: #00E676; font-weight: 800; font-family: 'JetBrains Mono';"
        elif chg_v < 0: styles[chg_idx] = "color: #FF5252; font-weight: 800; font-family: 'JetBrains Mono';"

        if sp_v >= 0: styles[sp_idx] = "color: #00E676; font-weight: 800; font-family: 'JetBrains Mono';"
        else: styles[sp_idx] = "color: #FF5252; font-weight: 800; font-family: 'JetBrains Mono';"

        # 买区、持仓区、卖区三色分明
        styles[buy_idx] = "color: #38BDF8; font-weight: 800; font-family: 'JetBrains Mono';"
        styles[hold_idx] = "color: #94A3B8; font-family: 'JetBrains Mono';"
        styles[sell_idx] = "color: #FCD34D; font-weight: 800; font-family: 'JetBrains Mono';"

        # 实操指令胶囊高亮
        if "买入" in act_v or "加仓" in act_v:
            styles[act_idx] = "background-color: #064E3B; color: #34D399; font-weight: 800; border-radius: 4px;"
        elif "止盈" in act_v or "减仓" in act_v:
            styles[act_idx] = "background-color: #78350F; color: #FCD34D; font-weight: 800; border-radius: 4px;"
        elif "观望" in act_v or "破位" in act_v:
            styles[act_idx] = "background-color: #7F1D1D; color: #FCA5A5; font-weight: 800; border-radius: 4px;"

        return styles

    styled_watchlist = df_raw.style.apply(apply_watchlist_theme, axis=1)
    st.dataframe(styled_watchlist, use_container_width=True, height=420, hide_index=True)

    st.markdown("---")
    st.markdown("#### 🎯 单股日线战区穿透分析 (点击切换标的)")

    chip_options = ["QQQ"] + list(TICKERS_CONFIG.keys())
    if "selected_chart_sym" not in st.session_state:
        st.session_state["selected_chart_sym"] = "NVDA"

    chip_cols = st.columns(len(chip_options))
    for idx, sym_opt in enumerate(chip_options):
        with chip_cols[idx]:
            is_active = (st.session_state["selected_chart_sym"] == sym_opt)
            btn_label = f"👉 {sym_opt}" if is_active else sym_opt
            if st.button(btn_label, key=f"chip_btn_tab1_{sym_opt}"):
                st.session_state["selected_chart_sym"] = sym_opt
                st.rerun()

    active_sym = st.session_state["selected_chart_sym"]
    sym_zones = res["zones_map"].get(active_sym)
    df_active = d_daily.get(active_sym)
    render_stock_zone_chart(active_sym, df_active, sym_zones)
