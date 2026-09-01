# 文件名: macro_radar_plugin.py
# 作用: 13 核心正股四阶段轮动 Watchlist Dashboard (日线 D1 + 周线 W1 大级别决策流)

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

# 13 核心标的配置 (严格锁定 7 巨头 + 6 先锋)
TICKERS_CONFIG = {
    # 🏛️ 7 大权重巨头
    "NVDA": {"name": "英伟达", "camp": "巨头", "weight_desc": "👑 3.0x 核心", "weight": 3.0, "role": "AI/算力总舵手"},
    "AAPL": {"name": "苹果", "camp": "巨头", "weight_desc": "👑 3.0x 核心", "weight": 3.0, "role": "消费电子/防守中枢"},
    "MSFT": {"name": "微软", "camp": "巨头", "weight_desc": "👑 3.0x 核心", "weight": 3.0, "role": "云端权重底座"},
    "AMZN": {"name": "亚马逊", "camp": "巨头", "weight_desc": "🏛️ 2.0x 中枢", "weight": 2.0, "role": "电商与云权重"},
    "GOOGL": {"name": "谷歌", "camp": "巨头", "weight_desc": "🏛️ 2.0x 中枢", "weight": 2.0, "role": "搜索广告权重"},
    "META": {"name": "Meta", "camp": "巨头", "weight_desc": "🏛️ 2.0x 中枢", "weight": 2.0, "role": "社交开源生态"},
    "TSLA": {"name": "特斯拉", "camp": "巨头", "weight_desc": "🏛️ 2.0x 中枢", "weight": 2.0, "role": "流动性与情绪先锋"},
    # 🚀 6 大芯片与存储先锋
    "AVGO": {"name": "博通", "camp": "先锋", "weight_desc": "🏛️ 2.0x 中枢", "weight": 2.0, "role": "网络芯片与ASIC龙头"},
    "MU": {"name": "美光", "camp": "先锋", "weight_desc": "🚀 1.0x 先锋", "weight": 1.0, "role": "存储/HBM龙头"},
    "AMD": {"name": "AMD", "camp": "先锋", "weight_desc": "🚀 1.0x 先锋", "weight": 1.0, "role": "算力二当家"},
    "WDC": {"name": "西部数据", "camp": "先锋", "weight_desc": "🚀 1.0x 先锋", "weight": 1.0, "role": "存储与硬盘核心"},
    "STX": {"name": "希捷", "camp": "先锋", "weight_desc": "🚀 1.0x 先锋", "weight": 1.0, "role": "企业级存储"},
    "SNDK": {"name": "闪迪", "camp": "先锋", "weight_desc": "🚀 1.0x 先锋", "weight": 1.0, "role": "存储情绪标的"},
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
    """抓取日线 D1 (6个月) 与 周线 W1 (1年) 周期大级别数据"""
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

    # 13 标的四阶段轮动分析
    pool_accum = []   # 阶段 1：逢低建仓池
    pool_lead = []    # 阶段 2：主升领跑池
    pool_dist = []    # 阶段 3：高位减仓池
    pool_lag = []     # 阶段 4：弱势观望池
    all_cards = []

    for sym, cfg in TICKERS_CONFIG.items():
        found = False
        if sym in data_daily and len(data_daily[sym]) >= 20:
            df_s = data_daily[sym]
            c_p = float(df_s["Close"].iloc[-1])
            p_p = float(df_s["Close"].iloc[-2])
            chg_d = ((c_p - p_p) / p_p) * 100
            spread_vs_qqq = chg_d - qqq_chg_d

            # 技术指标计算
            ma20 = float(df_s["Close"].rolling(20).mean().iloc[-1])
            ma50 = float(df_s["Close"].rolling(50).mean().iloc[-1]) if len(df_s) >= 50 else ma20
            avg_vol20 = float(df_s["Volume"].iloc[-20:].mean())
            cur_vol = float(df_s["Volume"].iloc[-1])
            vol_ratio = cur_vol / avg_vol20 if avg_vol20 > 0 else 1.0

            # 周线支撑计算
            pwl = c_p * 0.95
            if sym in data_weekly and len(data_weekly[sym]) >= 3:
                pwl = float(data_weekly[sym]["Low"].iloc[-2])

            dist_ma50_pct = ((c_p - ma50) / ma50) * 100
            dist_pwl_pct = ((c_p - pwl) / pwl) * 100

            # 严格按照 4 阶段进行归类判定
            if c_p >= ma20 and spread_vs_qqq >= 0 and vol_ratio >= 1.0:
                phase = "🚀 阶段 2: 轮动主升"
                action = "【加仓 / 顺势持有】"
                reason = "日线站稳 MA20，跑赢大盘，温和放量突破。"
                badge_color = "#10B981"
                pool_lead.append(sym)
            elif (abs(dist_pwl_pct) <= 2.5 or abs(dist_ma50_pct) <= 2.0) and vol_ratio <= 1.2:
                phase = "🟢 阶段 1: 筑底到位"
                action = "【可以分批买入】"
                reason = f"回踩周线支撑 (${pwl:.2f}) / 日MA50 企稳，缩量洗盘到位。"
                badge_color = "#3B82F6"
                pool_accum.append(sym)
            elif c_p >= ma20 and vol_ratio >= 1.8 and spread_vs_qqq < 0:
                phase = "⚠️ 阶段 3: 滞涨轮出"
                action = "【分批止盈减仓】"
                reason = "高位放巨量滞涨，资金开始流出转入其他板块。"
                badge_color = "#F59E0B"
                pool_dist.append(sym)
            else:
                phase = "🔴 阶段 4: 弱势破位"
                action = "【坚决不买 / 观望】"
                reason = "跌破均线支撑，跑输大盘，处于空头回调周期。"
                badge_color = "#EF4444"
                pool_lag.append(sym)

            found = True
            all_cards.append({
                "sym": sym,
                "name": cfg["name"],
                "camp": cfg["camp"],
                "role": cfg["role"],
                "price": c_p,
                "chg_d": chg_d,
                "spread": spread_vs_qqq,
                "vol_ratio": vol_ratio,
                "pwl": pwl,
                "ma50": ma50,
                "phase": phase,
                "action": action,
                "reason": reason,
                "color": badge_color
            })

        # SNDK 及网络容错保底
        if not found:
            pool_lag.append(sym)
            all_cards.append({
                "sym": sym,
                "name": cfg["name"],
                "camp": cfg["camp"],
                "role": cfg["role"],
                "price": 0.0,
                "chg_d": 0.0,
                "spread": 0.0,
                "vol_ratio": 0.0,
                "pwl": 0.0,
                "ma50": 0.0,
                "phase": "⚪ 阶段 0: 数据同步",
                "action": "【暂且观望】",
                "reason": "历史数据同步中，暂无大级别破位买点。",
                "color": "#6B7280"
            })

    return {
        "qqq_curr": qqq_curr,
        "qqq_chg_d": qqq_chg_d,
        "qqq_trend": qqq_trend,
        "pool_accum": pool_accum,
        "pool_lead": pool_lead,
        "pool_dist": pool_dist,
        "pool_lag": pool_lag,
        "all_cards": all_cards
    }


def render_macro_radar_tab():
    st.subheader("📋 13 核心标的轮动 Watchlist 与买卖罗盘 (日线 / 周线大级别)")

    if st.button("🔄 刷新最新日周轮动数据", key="btn_refresh_watchlist"):
        st.cache_data.clear()
        st.rerun()

    with st.spinner("正在提取 13 标的日线/周线历史结构与资金轮动数据..."):
        d_daily, d_weekly = fetch_watchlist_data()

    res = analyze_watchlist_rotation(d_daily, d_weekly)
    if not res:
        st.warning("行情连接中，请稍后点击上方刷新。")
        return

    # 1. 顶层：QQQ 大盘风向总闸门
    accum_cnt = len(res["pool_accum"])
    lead_cnt = len(res["pool_lead"])
    dist_cnt = len(res["pool_dist"])
    lag_cnt = len(res["pool_lag"])

    if lead_cnt + accum_cnt >= 8:
        macro_title = "🟢 大盘共振偏多：科技股主力轮动向上 (可积极选股买入)"
        macro_color = "#10B981"
        macro_desc = f"全场有 {lead_cnt} 只股票处于主升浪，{accum_cnt} 只跌到位企稳，市场风险偏好极高。"
    elif lag_cnt >= 7:
        macro_title = "🔴 大盘全面承压：多数个股破位回调 (严格防守 / 严禁盲目抄底)"
        macro_color = "#EF4444"
        macro_desc = f"全场有 {lag_cnt}/13 只股票处于弱势破位阶段，大盘有拖拽下杀风险，管住手不接飞刀！"
    else:
        macro_title = "🟡 大盘结构性分化：板块轮动拉锯 (仅做主升龙头，拒绝弱势股)"
        macro_color = "#F59E0B"
        macro_desc = f"主升 {lead_cnt} 只 vs 破位 {lag_cnt} 只，主力资金在板块内部做腾挪切换。"

    st.markdown(f"""
    <div style='background-color:#111827; border:2.5px solid {macro_color}; border-radius:10px; padding:16px 20px; margin-bottom:16px;'>
        <div style='font-size:19px; font-weight:800; color:{macro_color};'>{macro_title}</div>
        <div style='font-size:13px; color:#E5E7EB; margin-top:6px;'><b>资金真相</b>: {macro_desc}</div>
        <div style='font-size:12px; color:#9CA3AF; margin-top:4px;'>🎯 <b>QQQ 现价</b>: ${res['qqq_curr']:.2f} ({res['qqq_chg_d']:+.2f}%) | <b>日线大趋势</b>: {res['qqq_trend']}</div>
    </div>
    """, unsafe_allow_html=True)

    # 2. 四大轮动阶段统计卡
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("🟢 逢低建仓池", f"{accum_cnt} 只", "跌到位 / 支撑企稳")
    m2.metric("🚀 主升领跑池", f"{lead_cnt} 只", "资金买入 / 龙头突破")
    m3.metric("⚠️ 高位减仓池", f"{dist_cnt} 只", "滞涨 / 资金轮出")
    m4.metric("🔴 弱势观望池", f"{lag_cnt} 只", "破位 / 坚决不买")

    st.markdown("---")

    # 3. 四大阶段分类卡片展示
    st.markdown("#### 🧭 13 标的四阶段实操分桶清单 (告诉你该买谁、该卖谁)")
    tab_lead, tab_accum, tab_dist, tab_lag = st.tabs([
        f"🚀 主升领跑 ({lead_cnt})",
        f"🟢 逢低建仓 ({accum_cnt})",
        f"⚠️ 高位减仓 ({dist_cnt})",
        f"🔴 弱势观望 ({lag_cnt})"
    ])

    def render_cards_group(target_syms):
        if not target_syms:
            st.info("当前阶段暂无标的。")
            return
        cards = [c for c in res["all_cards"] if c["sym"] in target_syms]
        cols = st.columns(2)
        for idx, c in enumerate(cards):
            with cols[idx % 2]:
                st.markdown(f"""
                <div style='background:rgba(22, 27, 34, 0.9); border-left:4px solid {c["color"]}; border-radius:8px; padding:12px 16px; margin-bottom:12px; border-top:1px solid #30363d; border-right:1px solid #30363d; border-bottom:1px solid #30363d;'>
                    <div style='display:flex; justify-content:space-between; align-items:center;'>
                        <span style='font-size:16px; font-weight:800; color:#F9FAFB;'>{c["sym"]} <span style='font-size:13px; color:#9CA3AF;'>({c["name"]})</span></span>
                        <span style='font-size:12px; font-weight:700; color:{c["color"]};'>{c["phase"]}</span>
                    </div>
                    <div style='margin-top:6px; display:flex; justify-content:space-between; font-size:13px;'>
                        <span style='color:#9CA3AF;'>现价: <b style='color:#F3F4F6;'>${c["price"]:.2f}</b> ({c["chg_d"]:+.2f}%)</span>
                        <span style='color:#9CA3AF;'>均量比: <b style='color:#F3F4F6;'>{c["vol_ratio"]:.1f}x</b></span>
                        <span style='color:#9CA3AF;'>相对大盘: <b style='color:{c["color"]};'>{c["spread"]:+.2f}%</b></span>
                    </div>
                    <div style='margin-top:6px; font-size:12px; color:#D1D5DB;'>
                        <b>逻辑解析</b>: {c["reason"]}
                    </div>
                    <div style='margin-top:6px; padding-top:6px; border-top:1px dashed #374151; font-size:13px; font-weight:700; color:{c["color"]};'>
                        👉 建议动作: {c["action"]}
                    </div>
                </div>
                """, unsafe_allow_html=True)

    with tab_lead:
        render_cards_group(res["pool_lead"])
    with tab_accum:
        render_cards_group(res["pool_accum"])
    with tab_dist:
        render_cards_group(res["pool_dist"])
    with tab_lag:
        render_cards_group(res["pool_lag"])

    st.markdown("---")

    # 4. 纯净 Markdown 事实数据包一键复制
    st.markdown("#### 🤖 AI 深度分析数据包 (点击右上角复制，直接发给 AI)")
    md_out = f"""# 📋 13 核心正股轮动 Watchlist 客观事实战报

### 1. QQQ 宏观风向中枢
- **QQQ 现价/日涨跌**: `${res['qqq_curr']:.2f}` ({res['qqq_chg_d']:+.2f}%) | **日线趋势**: {res['qqq_trend']}
- **全场轮动结构**: 🚀主升 {lead_cnt} 只 | 🟢建仓 {accum_cnt} 只 | ⚠️减仓 {dist_cnt} 只 | 🔴破位 {lag_cnt} 只
- **大盘定调**: **{macro_title}**

### 2. 13 标的大级别轮动矩阵
| 代码 | 名称 | 阵营 | 现价 ($) | 日涨跌 (%) | 相对QQQ (%) | 均量比 | 轮动阶段 | 实操指令 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
"""
    for c in res["all_cards"]:
        md_out += f"| **{c['sym']}** | {c['name']} | {c['camp']} | {c['price']:.2f} | {c['chg_d']:+.2f}% | {c['spread']:+.2f}% | {c['vol_ratio']:.1f}x | {c['phase']} | {c['action']} |\n"

    md_out += """
---
### 💡 给 AI 的诊断 Prompt:
请依据上述 13 核心正股在日线与周线级别的轮动阶段分布：
1. 评估当前科技板块的资金流入主要集中在哪几只股票；
2. 筛选出 1-2 只目前最适合逢低分批建仓（阶段1）与 1 只适合追随主升（阶段2）的标的并给出入场逻辑。
"""
    st.code(md_out, language="markdown")
