# 文件名: portfolio_manager_plugin.py
# 作用: 独立 Tab 2 - 实操持仓管理、浮盈亏核算、资金滚动与 AI 调仓战报导出

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

def render_portfolio_expansion(df_watchlist_summary=None, price_dict=None):
    if price_dict is None or not isinstance(price_dict, dict):
        price_dict = {}

    df_pos = load_portfolio_data()

    # 1. 顶部现金维护
    st.markdown("##### 📝 实操持仓维护与资金池")
    col_cap1, col_cap2 = st.columns([1.5, 2.5])
    with col_cap1:
        cash_capital = st.number_input(
            "💵 账户剩余可用现金 Capital ($)",
            min_value=0.0,
            value=float(st.session_state.get("user_cash", 3.95)),
            step=100.0,
            key="input_cash_capital_t2_clean"
        )
        st.session_state["user_cash"] = cash_capital

    with st.expander("➕ 添加 / 修改持仓股票与成本", expanded=False):
        c1, c2, c3, c4 = st.columns([2, 1.5, 1.5, 1])
        with c1:
            sym_input = st.text_input("股票代码 (如 NVDA, QQQM, MU)", value="NVDA", key="in_new_sym_t2_clean").upper().strip()
        with c2:
            shares_input = st.number_input("持仓股数", min_value=0.0001, value=10.0, step=1.0, key="in_new_shares_t2_clean")
        with c3:
            def_cost = price_dict.get(sym_input, {}).get("price", 100.0) if sym_input in price_dict else 100.0
            cost_input = st.number_input("买入成本均价 ($)", min_value=0.01, value=float(def_cost) if def_cost > 0 else 100.0, step=1.0, key="in_new_cost_t2_clean")
        with c4:
            st.markdown("<div style='height:28px;'></div>", unsafe_allow_html=True)
            if st.button("💾 保存持仓", key="btn_save_new_pos_t2_clean"):
                if sym_input:
                    if not df_pos.empty and sym_input in df_pos["Symbol"].values:
                        df_pos.loc[df_pos["Symbol"] == sym_input, ["Shares", "AvgCost"]] = [shares_input, cost_input]
                    else:
                        new_row = pd.DataFrame([{"Symbol": sym_input, "Shares": shares_input, "AvgCost": cost_input}])
                        df_pos = pd.concat([df_pos, new_row], ignore_index=True)
                    save_portfolio_data(df_pos)
                    st.success(f"已成功保存 {sym_input}！")
                    st.rerun()

    # 2. 持仓逐笔核算
    rows_summary = []
    total_market_val = 0.0
    total_unrealized_pnl = 0.0

    if not df_pos.empty:
        for idx, r in df_pos.iterrows():
            sym = str(r["Symbol"]).upper().strip()
            shares = float(r["Shares"])
            cost = float(r["AvgCost"])
            cost_total = shares * cost

            curr_info = price_dict.get(sym, {})
            if isinstance(curr_info, dict) and curr_info.get("price", 0) > 0:
                curr_p = float(curr_info["price"])
                phase = curr_info.get("phase", "阶段2: 运行中")
                pattern_txt = curr_info.get("pattern", "➖ 整理震荡")
                sell_zone = curr_info.get("sell_zone", "-")
            else:
                curr_p = cost
                phase = "阶段2: 运行中"
                pattern_txt = "➖"
                sell_zone = "-"

            market_val = shares * curr_p
            pnl_dollar = market_val - cost_total
            pnl_pct = (pnl_dollar / cost_total) * 100 if cost_total > 0 else 0.0

            if "滞涨" in phase or "减仓" in phase or "黄昏之星" in pattern_txt or "看跌吞没" in pattern_txt:
                roll_advice = "🚨 建议减仓/卖出 (锁定利润，释放资金)"
            elif "破位" in phase or "观望" in phase:
                roll_advice = "⚠️ 设防支撑 (跌破止损，严禁盲目加仓)"
            elif "主升" in phase:
                roll_advice = "🚀 顺势持有 (盈利奔跑，上移保本线)"
            elif "筑底" in phase or "买入" in phase or "早晨之星" in pattern_txt:
                roll_advice = "🟢 支撑企稳 (持有待涨，逢低可补)"
            else:
                roll_advice = "⚪ 正常持仓"

            total_market_val += market_val
            total_unrealized_pnl += pnl_dollar

            rows_summary.append({
                "代码": sym,
                "持仓股数": round(shares, 4) if shares % 1 != 0 else int(shares),
                "成本均价 ($)": round(cost, 2),
                "最新现价 ($)": round(curr_p, 2),
                "持仓市值 ($)": round(market_val, 2),
                "浮动盈亏 ($)": round(pnl_dollar, 2),
                "盈亏率 (%)": round(pnl_pct, 2),
                "K线形态": pattern_txt,
                "减仓卖出区": sell_zone,
                "资金滚动指令": roll_advice
            })

    total_account_nav = total_market_val + cash_capital
    total_cost_basis = total_market_val - total_unrealized_pnl
    total_pnl_pct = (total_unrealized_pnl / total_cost_basis * 100) if total_cost_basis > 0 else 0.0

    # 3. 账户大指标卡
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("💰 账户总资产 (NAV)", f"${total_account_nav:,.2f}", f"盈亏率: {total_pnl_pct:+.2f}%")
    m2.metric("📊 持仓总市值", f"${total_market_val:,.2f}", f"仓位: {(total_market_val/total_account_nav*100):.1f}%" if total_account_nav > 0 else "0%")
    m3.metric("💵 可用闲置现金", f"${cash_capital:,.2f}", "机动流动性")
    m4.metric("📈 整体未实现盈亏", f"{total_unrealized_pnl:+,.2f} USD", f"{total_pnl_pct:+.2f}%")

    st.markdown("---")

    # 4. 持仓明细与清仓区
    if rows_summary:
        st.markdown("##### 📋 当前持仓明细与滚动状态表")
        df_display = pd.DataFrame(rows_summary)
        st.dataframe(df_display, use_container_width=True, hide_index=True)

        with st.expander("🗑️ 平仓 / 移除持仓标的"):
            del_sym = st.selectbox("选择要平仓移除的股票代码", options=df_pos["Symbol"].tolist(), key="del_port_picker_clean_t2")
            if st.button(f"确认清仓移除 {del_sym}", key="btn_confirm_del_clean_t2"):
                df_pos = df_pos[df_pos["Symbol"] != del_sym]
                save_portfolio_data(df_pos)
                st.success(f"已移除 {del_sym}！")
                st.rerun()

    # 5. 资金滚动换股推荐池
    st.markdown("---")
    st.markdown("##### 🎯 闲置现金滚动买入推荐池 (从 13 标的中筛选)")
    held_syms = df_pos["Symbol"].tolist() if not df_pos.empty else []
    
    buy_candidates = []
    if isinstance(price_dict, dict):
        for s, v in price_dict.items():
            if isinstance(v, dict) and s not in held_syms and ("筑底" in v.get("phase", "") or "买入" in v.get("action", "") or "早晨之星" in v.get("pattern", "")):
                buy_candidates.append({"sym": s, "price": v.get("price", 0.0), "action": v.get("action", ""), "buy_zone": v.get("buy_zone", "-")})

    c_rec1, c_rec2 = st.columns(2)
    with c_rec1:
        st.markdown("🟢 **推荐逢低建仓池 (阶段1 - 支撑企稳)**")
        if buy_candidates:
            for b in buy_candidates:
                p = b["price"]
                max_s = int(cash_capital // p) if p > 0 else 0
                st.success(f"**{b['sym']}** | 现价: `${p:.2f}` | 建仓区: `{b['buy_zone']}` | 可买: `{max_s} 股`\n\n*建议*: `{b['action']}`")
        else:
            st.info("当前 13 监控池中暂无可逢低建仓的未持仓标的。")

    with c_rec2:
        st.markdown("💡 **调仓滚动执行法则**")
        st.write("1. 若持有标的进入 **⚠️ 阶段3 (滞涨)** 或出现 **黄昏之星**，执行逢高部分减仓以收回现金；")
        st.write("2. 将收回的可用现金，滚动分批买入左侧 **🟢 阶段1 (筑底)** 的新龙头。")

    # 6. 导出 AI 诊断战报
    st.markdown("---")
    st.markdown("#### 🤖 AI 资产滚动调仓诊断战报 (点击右上角复制)")

    md_report = f"""# 💼 交易员实操持仓与资产滚动 AI 诊断战报

### 1. 账户资产全景
- **总资产 (NAV)**: `${total_account_nav:,.2f}` | **持仓总市值**: `${total_market_val:,.2f}` | **可用现金**: `${cash_capital:,.2f}`
- **浮动总盈亏**: `${total_unrealized_pnl:+,.2f}` ({total_pnl_pct:+.2f}%)

### 2. 当前持仓明细与形态
| 代码 | 股数 | 成本均价 ($) | 当前现价 ($) | 盈亏 ($ / %) | K线形态 | 减仓目标区 | 资金滚动指令 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
"""
    for r in rows_summary:
        md_report += f"| **{r['代码']}** | {r['持仓股数']} | {r['成本均价 ($)']:.2f} | {r['最新现价 ($)']:.2f} | {r['浮动盈亏 ($)']:+.2f} ({r['盈亏率 (%)']:+.2f}%) | {r['K线形态']} | {r['减仓卖出区']} | {r['资金滚动指令']} |\n"

    md_report += f"""
---
### 💡 给 AI 的诊断 Prompt:
请依据以上持仓盈亏状况、剩余可用现金 `${cash_capital:,.2f}` 以及 13 核心标的的轮动阶段：
1. 诊断当前持仓（如 NVDA, SNDK, SKHY 等）是否需要立即止盈或止损调仓；
2. 若减仓滞涨标的释放资金后，应重点滚动买入哪 1~2 只处于筑底（阶段1）或主升（阶段2）的标的；
3. 给出具体的仓位配置方案与防守止损线。
"""
    st.code(md_report, language="markdown")
