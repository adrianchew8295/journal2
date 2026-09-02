# 文件名: portfolio_manager_plugin.py
# 作用: 包含手动输入框、K线经典形态(晨星/暮星/吞没/2B)与精准买卖点的实操持仓罗盘

import os
import datetime
import numpy as np
import pandas as pd
import streamlit as st
import pytz

PORTFOLIO_FILE = "portfolio_positions.csv"
tz_myt = pytz.timezone("Asia/Kuala_Lumpur")

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

def detect_candlestick_patterns(df_daily):
    """
    客观量化识别经典K线形态: Morning Star, Evening Star, Engulfing, 2B
    """
    if df_daily is None or len(df_daily) < 4:
        return "常规走势", "#9CA3AF"

    # 获取最近 3 根日线 K 线
    o3, h3, l3, c3 = df_daily["Open"].iloc[-3], df_daily["High"].iloc[-3], df_daily["Low"].iloc[-3], df_daily["Close"].iloc[-3]
    o2, h2, l2, c2 = df_daily["Open"].iloc[-2], df_daily["High"].iloc[-2], df_daily["Low"].iloc[-2], df_daily["Close"].iloc[-2]
    o1, h1, l1, c1 = df_daily["Open"].iloc[-1], df_daily["High"].iloc[-1], df_daily["Low"].iloc[-1], df_daily["Close"].iloc[-1]

    # 1. 晨星 (Morning Star) 判定
    is_c3_bear = (c3 < o3) and (abs(c3 - o3) >= 0.4 * (h3 - l3))
    is_c2_star = abs(c2 - o2) <= 0.35 * (h2 - l2) and (h2 < h3)
    is_c1_bull = (c1 > o1) and (c1 >= (o3 + c3) / 2)
    if is_c3_bear and is_c2_star and is_c1_bull:
        return "✨ 早晨之星 (Morning Star 底部反转)", "#10B981"

    # 2. 暮星 (Evening Star) 判定
    is_c3_bull = (c3 > o3) and (abs(c3 - o3) >= 0.4 * (h3 - l3))
    is_c2_star_top = abs(c2 - o2) <= 0.35 * (h2 - l2) and (h2 > h3)
    is_c1_bear = (c1 < o1) and (c1 <= (o3 + c3) / 2)
    if is_c3_bull and is_c2_star_top and is_c1_bear:
        return "⚠️ 黄昏之星 (Evening Star 高位滞涨)", "#EF4444"

    # 3. 看涨吞没 (Bullish Engulfing)
    if (c2 < o2) and (c1 > o1) and (c1 >= o2) and (o1 <= c2):
        return "🔥 看涨吞没 (Bullish Engulfing 强力反包)", "#10B981"

    # 4. 看跌吞没 (Bearish Engulfing)
    if (c2 > o2) and (c1 < o1) and (c1 <= o2) and (o1 >= c2):
        return "🚨 看跌吞没 (Bearish Engulfing 顶部包覆)", "#EF4444"

    # 5. 2B 假突破破底翻判定
    prev_low_5 = df_daily["Low"].iloc[-6:-1].min() if len(df_daily) >= 6 else l2
    if (l1 < prev_low_5) and (c1 > prev_low_5) and (c1 > o1):
        return "⚓ 2B 破底翻 (2B Bottom 吸筹)", "#3B82F6"

    prev_high_5 = df_daily["High"].iloc[-6:-1].max() if len(df_daily) >= 6 else h2
    if (h1 > prev_high_5) and (c1 < prev_high_5) and (c1 < o1):
        return "🚨 2B 假突破 (2B Top 诱多)", "#F59E0B"

    return "➖ 整理震荡", "#9CA3AF"

def render_portfolio_expansion(df_watchlist_summary, price_dict, data_daily_all):
    """
    渲染持仓管理与技术形态/买卖点面板
    """
    st.markdown("---")
    st.subheader("💼 我的实操持仓管理与精准买卖点罗盘")
    st.caption("支持手动录入/更新持仓。系统自动穿透形态学（早晨之星/吞没/2B）与量化战区，输出精准买卖点。")

    df_pos = load_portfolio_data()

    # 1. 顶部输入框：资金设置与快速录入表单
    st.markdown("##### 📝 持仓与现金管理输入框")
    
    col_input1, col_input2, col_input3, col_input4, col_input5 = st.columns([1.5, 1.2, 1.2, 1.5, 1.0])
    with col_input1:
        cash_capital = st.number_input("💵 可用现金 Capital ($)", min_value=0.0, value=float(st.session_state.get("user_cash", 3.95)), step=100.0, key="in_cash_capital")
        st.session_state["user_cash"] = cash_capital
    with col_input2:
        in_sym = st.text_input("股票代码", value="NVDA", key="in_stock_sym").upper().strip()
    with col_input3:
        in_shares = st.number_input("持股数量", min_value=0.0001, value=10.0, step=1.0, key="in_stock_shares")
    with col_input4:
        default_cost = price_dict.get(in_sym, {}).get("price", 100.0) if in_sym in price_dict else 100.0
        in_cost = st.number_input("买入成本 ($)", min_value=0.01, value=float(default_cost), step=1.0, key="in_stock_cost")
    with col_input5:
        st.markdown("<div style='height:28px;'></div>", unsafe_allow_html=True)
        if st.button("💾 存入/更新", key="btn_save_manual_pos"):
            if in_sym:
                if not df_pos.empty and in_sym in df_pos["Symbol"].values:
                    df_pos.loc[df_pos["Symbol"] == in_sym, ["Shares", "AvgCost"]] = [in_shares, in_cost]
                else:
                    new_row = pd.DataFrame([{"Symbol": in_sym, "Shares": in_shares, "AvgCost": in_cost}])
                    df_pos = pd.concat([df_pos, new_row], ignore_index=True)
                save_portfolio_data(df_pos)
                st.success(f"已成功录入 {in_sym}！")
                st.rerun()

    # 2. 持仓逐笔精确核算与形态识别
    rows_summary = []
    total_market_val = 0.0
    total_unrealized_pnl = 0.0

    if not df_pos.empty:
        for idx, r in df_pos.iterrows():
            sym = str(r["Symbol"]).upper().strip()
            shares = float(r["Shares"])
            cost = float(r["AvgCost"])
            cost_total = shares * cost

            curr_info = price_dict.get(sym, None)
            df_s = data_daily_all.get(sym, None)
            pattern_txt, pattern_col = detect_candlestick_patterns(df_s)

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

            # 综合买卖指令裁决 (形态 + 轮动阶段)
            if "黄昏之星" in pattern_txt or "看跌吞没" in pattern_txt or "2B Top" in pattern_txt or "滞涨" in phase:
                action_advice = "🚨 建议减仓/卖出 (形态见顶/滞涨，释放现金)"
            elif "早晨之星" in pattern_txt or "看涨吞没" in pattern_txt or "2B Bottom" in pattern_txt:
                action_advice = "🟢 强力买入/补仓 (经典反转形态确立)"
            elif "主升" in phase:
                action_advice = "🚀 顺势持有 (主升浪奔跑，保本止损)"
            else:
                action_advice = "⚪ 防守持有/观望"

            total_market_val += market_val
            total_unrealized_pnl += pnl_dollar

            rows_summary.append({
                "代码": sym,
                "持股数": round(shares, 4) if shares % 1 != 0 else int(shares),
                "成本均价 ($)": round(cost, 2),
                "最新现价 ($)": round(curr_p, 2),
                "持仓市值 ($)": round(market_val, 2),
                "浮动盈亏 ($)": round(pnl_dollar, 2),
                "盈亏率 (%)": round(pnl_pct, 2),
                "K线形态识别": pattern_txt,
                "精准买入建仓区": buy_zone,
                "精准减仓卖出区": sell_zone,
                "实操买卖决策": action_advice
            })

    total_account_nav = total_market_val + cash_capital
    total_cost_basis = total_market_val - total_unrealized_pnl
    total_pnl_pct = (total_unrealized_pnl / total_cost_basis * 100) if total_cost_basis > 0 else 0.0

    # 3. KPI 资产全景
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("💰 账户总资产 (NAV)", f"${total_account_nav:,.2f}", f"盈亏率: {total_pnl_pct:+.2f}%")
    m2.metric("📊 持仓总市值", f"${total_market_val:,.2f}", f"仓位: {(total_market_val/total_account_nav*100):.1f}%" if total_account_nav > 0 else "0%")
    m3.metric("💵 可用现金 Capital", f"${cash_capital:,.2f}", "机动流动性")
    m4.metric("📈 浮动总盈亏", f"{total_unrealized_pnl:+,.2f} USD", f"{total_pnl_pct:+.2f}%")

    st.markdown("---")

    # 4. 持仓明细与形态分析表格
    if rows_summary:
        st.markdown("##### 📋 持仓资产与形态学买卖点诊断表")
        df_display = pd.DataFrame(rows_summary)
        st.dataframe(df_display, use_container_width=True, hide_index=True)

        with st.expander("🗑️ 平仓 / 移除某只持仓代码"):
            del_sym = st.selectbox("选择平仓标的", options=df_pos["Symbol"].tolist(), key="del_pos_manual")
            if st.button(f"确认清仓移除 {del_sym}", key="btn_confirm_del_manual"):
                df_pos = df_pos[df_pos["Symbol"] != del_sym]
                save_portfolio_data(df_pos)
                st.success(f"已成功平仓移除 {del_sym}！")
                st.rerun()

    # 5. AI 诊断 Prompt 导出
    st.markdown("---")
    st.markdown("#### 🤖 AI 形态与资产滚动诊断战报 (点击右上角复制)")

    md_report = f"""# 💼 交易员实操持仓与形态学精准买卖点 AI 战报

### 1. 账户资产全景
- **总资产 (NAV)**: `${total_account_nav:,.2f}` | **持仓总市值**: `${total_market_val:,.2f}` | **可用现金**: `${cash_capital:,.2f}`
- **浮动总盈亏**: `${total_unrealized_pnl:+,.2f}` ({total_pnl_pct:+.2f}%)

### 2. 持仓形态学与买卖点分析
| 代码 | 股数 | 成本 ($) | 现价 ($) | 盈亏 ($ / %) | K线形态分析 | 减仓目标区 | 实操指令 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
"""
    for r in rows_summary:
        md_report += f"| **{r['代码']}** | {r['持股数']} | {r['成本均价 ($)']:.2f} | {r['最新现价 ($)']:.2f} | {r['浮动盈亏 ($)']:+.2f} ({r['盈亏率 (%)']:+.2f}%) | {r['K线形态识别']} | {r['精准减仓卖出区']} | {r['实操买卖决策']} |\n"

    md_report += f"""
---
### 💡 给 AI 的诊断 Prompt:
请依据以上持仓的 K 线形态学（Morning Star / Evening Star / Engulfing / 2B）、买卖点区间与可用现金 `${cash_capital:,.2f}`：
1. 评估是否有标的出现见顶形态（如黄昏之星/看跌吞没）需要立即减仓；
2. 结合 13 核心标的，指出哪些未持仓标的出现了早晨之星或看涨吞没反转，建议如何分批建仓；
3. 给出精准的进场价、止损价与 1:2 止盈目标位。
"""
    st.code(md_report, language="markdown")
