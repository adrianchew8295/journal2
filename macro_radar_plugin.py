# 文件名: macro_radar_plugin.py
# 作用: 13 核心正股宏观 Watchlist 极简看板 (标的合并/纯净 6 列 · 日周轮动 · AI Facts 导出)

import datetime
import numpy as np
import pandas as pd
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
        start_date = (datetime.datetime.now(tz_ny) - datetime.timedelta(days=120)).strftime("%Y-%m-%d")
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
    """抓取日线 D1 与周线 W1 周期大级别数据"""
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

            pwl = c_p * 0.95
            if sym in data_weekly and len(data_weekly[sym]) >= 3:
                pwl = float(data_weekly[sym]["Low"].iloc[-2])

            dist_ma50_pct = ((c_p - ma50) / ma50) * 100
            dist_pwl_pct = ((c_p - pwl) / pwl) * 100

            if spread_vs_qqq >= 0:
                bull_count += 1
            else:
                bear_count += 1

            # 4 阶段判定策略
            if c_p >= ma20 and spread_vs_qqq >= 0 and vol_ratio >= 1.0:
                phase = "🚀 阶段2: 轮动主升"
                action = "【加仓 / 顺势持有】"
            elif (abs(dist_pwl_pct) <= 2.5 or abs(dist_ma50_pct) <= 2.0) and vol_ratio <= 1.2:
                phase = "🟢 阶段1: 筑底到位"
                action = "【可分批买入】"
            elif c_p >= ma20 and vol_ratio >= 1.8 and spread_vs_qqq < 0:
                phase = "⚠️ 阶段3: 滞涨轮出"
                action = "【分批止盈卖出】"
            else:
                phase = "🔴 阶段4: 弱势破位"
                action = "【坚决不买 / 观望】"

            found = True
            all_rows.append({
                "标的": f"{sym} ({cfg['name']})",
                "现价 ($)": round(c_p, 2),
                "日涨跌 (%)": round(chg_d, 2),
                "相对QQQ (%)": round(spread_vs_qqq, 2),
                "轮动阶段": phase,
                "实操指令 (Action)": action
            })

        if not found:
            bear_count += 1
            all_rows.append({
                "标的": f"{sym} ({cfg['name']})",
                "现价 ($)": 0.0,
                "日涨跌 (%)": 0.0,
                "相对QQQ (%)": 0.0,
                "轮动阶段": "⚪ 阶段0: 同步中",
                "实操指令 (Action)": "【暂且观望】"
            })

    df_result = pd.DataFrame(all_rows).sort_values(by="相对QQQ (%)", ascending=False)

    return {
        "timestamp_myt": datetime.datetime.now(tz_myt).strftime("%Y-%m-%d %H:%M MYT"),
        "timestamp_ny": datetime.datetime.now(tz_ny).strftime("%Y-%m-%d %H:%M ET"),
        "qqq_curr": qqq_curr,
        "qqq_chg_d": qqq_chg_d,
        "qqq_trend": qqq_trend,
        "bull_count": bull_count,
        "bear_count": bear_count,
        "df_result": df_result
    }


def generate_facts_markdown(res):
    """构建给 AI 诊断的纯客观事实数据"""
    df = res["df_result"]
    md = f"""# 📡 QQQ 宏观与 13 核心标的轮动事实战报 (Facts Only)

### 1. QQQ 宏观风向中枢
- **截面时间**: `{res['timestamp_myt']}` (美东 `{res['timestamp_ny']}`)
- **QQQ 指数基准**: 现价 `${res['qqq_curr']:.2f}` ({res['qqq_chg_d']:+.2f}%) | 日线大趋势: `{res['qqq_trend']}`
- **全场多空分布**: 共 `{res['bull_count']}/13` 只跑赢大盘 (跑输 `{res['bear_count']}/13` 只)

### 2. 13 核心标的日周 Watchlist
| 标的 | 现价 ($) | 日涨跌 (%) | 相对QQQ (%) | 轮动阶段 | 实操指令 |
| :--- | :--- | :--- | :--- | :--- | :--- |
"""
    for _, r in df.iterrows():
        md += f"| **{r['标的']}** | {r['现价 ($)']:.2f} | {r['日涨跌 (%)']:+.2f}% | {r['相对QQQ (%)']:+.2f}% | {r['轮动阶段']} | {r['实操指令 (Action)']} |\n"

    md += """
---
### 🤖 给 AI 的诊断 Prompt:
请依据上述 13 核心标的日周轮动数据与相对 QQQ 强弱：
1. 评估当前科技股资金是整体流入还是分化抽逃；
2. 选出目前最适合分批建仓与顺势持有的标的；
3. 判定今晚 QQQ 整体走势倾向。
"""
    return md


def render_macro_radar_tab():
    st.subheader("📋 13 核心标的宏观 Watchlist (极简大级别罗盘)")

    c1, c2 = st.columns([4, 1])
    with c1:
        st.caption("基于日线 D1 与周线 W1 识别主力轮动阶段，明确买入/卖出/观望节点。")
    with c2:
        if st.button("🔄 刷新 Watchlist", key="btn_refresh_watchlist_v5"):
            st.cache_data.clear()
            st.rerun()

    with st.spinner("正在提取日周线行情与轮动数据..."):
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

    # 2. 中部：极简 6 列专业 Watchlist 表格
    st.markdown("#### 📊 13 核心标的极简 Watchlist (从强到弱)")
    
    df_show = res["df_result"]

    def style_watchlist(row):
        styles = [""] * len(row)
        chg_idx = df_show.columns.get_loc("日涨跌 (%)")
        sp_idx = df_show.columns.get_loc("相对QQQ (%)")
        act_idx = df_show.columns.get_loc("实操指令 (Action)")

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

        if "可分批买入" in act_val:
            styles[act_idx] = "background-color: #1E3A8A; color: #93C5FD; font-weight: bold;"
        elif "加仓" in act_val:
            styles[act_idx] = "background-color: #064E3B; color: #6EE7B7; font-weight: bold;"
        elif "止盈" in act_val:
            styles[act_idx] = "background-color: #78350F; color: #FCD34D; font-weight: bold;"
        elif "坚决不买" in act_val:
            styles[act_idx] = "background-color: #7F1D1D; color: #FCA5A5; font-weight: bold;"

        return styles

    styled_df = df_show.style.apply(style_watchlist, axis=1)
    st.dataframe(styled_df, use_container_width=True, height=480, hide_index=True)

    st.markdown("---")

    # 3. 底部：纯净 Markdown 事实数据包一键复制
    st.markdown("#### 🤖 AI 深度分析数据包 (点击右上角一键复制)")
    ai_md = generate_facts_markdown(res)
    st.code(ai_md, language="markdown")
