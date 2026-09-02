# 文件名: portfolio_manager_plugin.py
# 作用: 独立 Tab 2 - 实操持仓维护、4大资产指标卡、高亮色彩战术表格、闲置推荐池与 AI 调仓报告

import os
import datetime
import numpy as np
import pandas as pd
import streamlit as st
import pytz

PORTFOLIO_FILE = "portfolio_positions.csv"
tz_myt = pytz.timezone("Asia/Kuala_Lumpur")

DEFAULT_INIT_POSITIONS = [
    {"Symbol": "NVDA", "Shares": 10.0, "AvgCost": 199.99},
    {"Symbol": "SNDK", "Shares": 1.4281, "AvgCost": 1488.58},
    {"Symbol": "QQQM", "Shares": 7.0, "AvgCost": 294.53},
    {"Symbol": "SKHY", "Shares": 4.0, "AvgCost": 171.93},
    {"Symbol": "DRAM", "Shares": 10.0, "AvgCost": 55.18}
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

def render_portfolio_expansion(*args, **kwargs):
    price_dict = {}
    if "price_dict" in kwargs and isinstance(kwargs["price_dict"], dict):
        price_dict = kwargs["price_dict"]
    elif len(args) >= 2 and isinstance(args[1], dict):
        price_dict = args[1]
    elif len(args) >= 1 and isinstance(args[0], dict):
        price_dict = args[0]

    df_pos = load_portfolio_data()

    # 1. 顶部：实操资产与调仓输入框
    st.markdown("##### 📝 实操资产与调仓输入框")
    
    col_input1, col_input2, col_input3, col_input4, col_input5 = st.columns([1.5, 1.5, 1.2, 1.5, 1.2])
    with col_input1:
        cash_capital = st.number_input(
            "💵 可用现金 Capital ($)",
            min_value=0.0,
            value=float(st.session_state.get("user_cash", 3.95)),
            step=10.0,
            key="input_cash_capital_main_t2"
        )
        st.session_state["user_cash"] = cash_capital

    with col_input2:
        sym_input = st.text_input("股票代码 (如 NVDA, QQQM)", value="NVDA", key="input_sym_main_t2").upper().strip()
    with col_input3:
        shares_input = st.number_input("持股数量", min_value=0.0001, value=10.0, step=1.0, key="input_shares_main_t2")
    with col_input4:
        def_cost = price_dict.get(sym_input, {}).get("price", 217.44) if sym_input in price_dict else 217.44
        cost_input = st.number_input("买入成本 ($)", min_value=0.01, value=float(def_cost) if def_cost > 0 else 217.44, step=1.0, key="input_cost_main_t2")
    with col_input5:
        st.markdown("<div style='height:28px;'></div>", unsafe_allow_html=True)
        if st.button("💾 存入/更新", key="btn_save_main_pos_t2"):
            if sym_input:
                if not df_pos.empty and sym_input in df_pos["Symbol"].values:
                    df_pos.loc[df_pos["Symbol"] == sym_input, ["Shares", "AvgCost"]] = [shares_input, cost_input]
                else:
                    new_row = pd.DataFrame([{"Symbol": sym_input, "Shares": shares_input, "AvgCost": cost_input}])
                    df_pos = pd.concat([df_pos, new_row], ignore_index=True)
                save_portfolio_data(df_pos)
                st.success(f"已成功更新 {sym_input} 持仓！")
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
                sell_zone = curr_info.get("sell_zone", "$225.00 - $241.20")
            else:
                curr_p = cost
                phase = "阶段2: 运行中"
                pattern_txt = "➖ 常规走势"
                sell_zone = "$225.00 - $241.20"

            market_val = shares * curr_p
            pnl_dollar = market_val - cost_total
            pnl_pct = (pnl_dollar / cost_total) * 100 if cost_total > 0 else 0.0

            if "滞涨" in phase or "减仓" in phase or "黄昏之星" in pattern_txt or "看跌吞没" in pattern_txt:
                roll_advice = "🚨 建议减仓/卖出"
            elif "破位" in phase or "观望" in phase:
                roll_advice = "⚠️ 设防破位止损"
            elif "主升" in phase:
                roll_advice = "🚀 顺势持有待涨"
            elif "筑底" in phase or "买入" in phase or "早晨之星" in pattern_txt:
                roll_advice = "🟢 企稳逢低可加"
            else:
                roll_advice = "⚪ 正常持仓观察"

            total_market_val += market_val
            total_unrealized_pnl += pnl_dollar

            rows_summary.append({
                "代码": sym,
                "持股量": round(shares, 4) if shares % 1 != 0 else int(shares),
                "买入成本 ($)": round(cost, 2),
                "最新现价 ($)": round(curr_p, 2),
                "持仓市值 ($)": round(market_val, 2),
                "浮动盈亏 ($)": round(pnl_dollar, 2),
                "盈亏率 (%)": round(pnl_pct, 2),
                "K线形态": pattern_txt,
                "减仓卖出目标区": sell_zone,
                "资金滚动指令": roll_advice
            })

    total_account_nav = total_market_val + cash_capital
    total_cost_basis = total_market_val - total_unrealized_pnl
    total_pnl_pct = (total_unrealized_pnl / total_cost_basis * 100) if total_cost_basis > 0 else 0.0

    st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)

    # 3. 四大核心资产指标卡
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("💰 账户总资产 (NAV)", f"${total_account_nav:,.2f}", f"整体盈亏: {total_pnl_pct:+.2f}%")
    m2.metric("📊 持仓总市值", f"${total_market_val:,.2f}", f"仓位: {(total_market_val/total_account_nav*100):.1f}%" if total_account_nav > 0 else "0%")
    m3.metric("💵 可用现金 Capital", f"${cash_capital:,.2f}", "机动流动性")
    m4.metric("📈 浮动总盈亏", f"{total_unrealized_pnl:+,.2f} USD", f"{total_pnl_pct:+.2f}%")

    st.markdown("---")

    # 4. 持仓资产与形态诊断明细大表 (注入高亮战术着色)
    st.markdown("##### 📋 持仓资产与形态诊断明细")
    if rows_summary:
        df_display = pd.DataFrame(rows_summary)

        # 高亮持仓表格函数
        def style_portfolio_table(row):
            styles = [""] * len(row)
            pnl_idx = df_display.columns.get_loc("浮动盈亏 ($)")
            rate_idx = df_display.columns.get_loc("盈亏率 (%)")
            sell_idx = df_display.columns.get_loc("减仓卖出目标区")
            act_idx = df_display.columns.get_loc("资金滚动指令")

            pnl_v = row["浮动盈亏 ($)"]
            act_v = row["资金滚动指令"]

            # 盈亏着色
            if pnl_v > 0:
                styles[pnl_idx] = "color: #34D399; font-weight: 800; font-family: 'JetBrains Mono';"
                styles[rate_idx] = "color: #34D399; font-weight: 800; font-family: 'JetBrains Mono';"
            elif pnl_v < 0:
                styles[pnl_idx] = "color: #F87171; font-weight: 800; font-family: 'JetBrains Mono';"
                styles[rate_idx] = "color: #F87171; font-weight: 800; font-family: 'JetBrains Mono';"

            # 减仓卖出目标区醒目金黄色
            styles[sell_idx] = "color: #FCD34D; font-weight: 700; font-family: 'JetBrains Mono';"

            # 实操指令胶囊高亮
            if "加" in act_v or "企稳" in act_v:
                styles[act_idx] = "background-color: #064E3B; color: #6EE7B7; font-weight: bold; border-radius: 4px;"
            elif "减仓" in act_v or "卖出" in act_v:
                styles[act_idx] = "background-color: #78350F; color: #FCD34D; font-weight: bold; border-radius: 4px;"
            elif "设防" in act_v or "止损" in act_v:
                styles[act_idx] = "background-color: #7F1D1D; color: #FCA5A5; font-weight: bold; border-radius: 4px;"
            elif "顺势" in act_v:
                styles[act_idx] = "background-color: #0284C7; color: #E0F2FE; font-weight: bold; border-radius: 4px;"

            return styles

        styled_port_df = df_display.style.apply(style_portfolio_table, axis=1)
        st.dataframe(styled_port_df, use_container_width=True, hide_index=True)

        with st.expander("🗑️ 平仓 / 移除某只持仓代码"):
            del_sym = st.selectbox("选择要平仓移除的标的", options=df_pos["Symbol"].tolist(), key="del_port_picker_final_t2")
            if st.button(f"确认清仓移除 {del_sym}", key="btn_confirm_del_final_t2"):
                df_pos = df_pos[df_pos["Symbol"] != del_sym]
                save_portfolio_data(df_pos)
                st.success(f"已移除 {del_sym}！")
                st.rerun()

    st.markdown("---")

    # 5. 【高亮色彩 Table】闲置现金滚动买入推荐池 (完全采用高对比彩色表格)
    st.markdown("##### 🎯 闲置现金滚动买入推荐池 & 调仓法则")
    
    held_syms = df_pos["Symbol"].tolist() if not df_pos.empty else []
    buy_rows = []
    
    if isinstance(price_dict, dict) and price_dict:
        for s, v in price_dict.items():
            if isinstance(v, dict) and s not in held_syms:
                p = float(v.get("price", 0.0))
                if p > 0:
                    max_s = int(cash_capital // p) if cash_capital > 0 else 0
                    buy_rows.append({
                        "推荐龙头": s,
                        "最新现价 ($)": round(p, 2),
                        "建议建仓区间 (Buy Area)": v.get("buy_zone", "-"),
                        "可用现金可买": f"{max_s} 股",
                        "实操战略建议": v.get("action", "【分批买入】")
                    })
    
    # 优质保底候选池
    if not buy_rows:
        default_candidates = [
            ("AMZN", 254.92, "$247.36 - $260.12", "【分批买入】"),
            ("GOOGL", 335.02, "$331.75 - $352.40", "【分批买入】"),
            ("TSLA", 338.85, "$325.80 - $342.61", "【分批买入】"),
            ("MU", 102.66, "$99.80 - $107.95", "【分批买入】"),
            ("AMD", 150.81, "$142.50 - $157.91", "【分批买入】"),
            ("AAPL", 325.13, "$302.05 - $315.89", "【加仓/持有】"),
            ("META", 578.54, "$535.37 - $598.26", "【加仓/持有】")
        ]
        for s, p, bz, act in default_candidates:
            if s not in held_syms:
                max_s = int(cash_capital // p) if cash_capital > 0 else 0
                buy_rows.append({
                    "推荐龙头": s,
                    "最新现价 ($)": round(p, 2),
                    "建议建仓区间 (Buy Area)": bz,
                    "可用现金可买": f"{max_s} 股",
                    "实操战略建议": act
                })

    c_tbl_left, c_tbl_right = st.columns([3.2, 1.8], gap="medium")
    with c_tbl_left:
        df_buy_candidates = pd.DataFrame(buy_rows)

        # 高亮买入推荐池表格函数
        def style_buy_table(row):
            styles = [""] * len(row)
            sym_idx = df_buy_candidates.columns.get_loc("推荐龙头")
            price_idx = df_buy_candidates.columns.get_loc("最新现价 ($)")
            zone_idx = df_buy_candidates.columns.get_loc("建议建仓区间 (Buy Area)")
            shares_idx = df_buy_candidates.columns.get_loc("可用现金可买")
            act_idx = df_buy_candidates.columns.get_loc("实操战略建议")

            act_v = row["实操战略建议"]

            # 标的代码与现价粗体高亮
            styles[sym_idx] = "color: #FFFFFF; font-weight: 800;"
            styles[price_idx] = "color: #FFFFFF; font-weight: 700; font-family: 'JetBrains Mono';"

            # 建议建仓区间：天蓝色发光，一眼看出关键支撑价
            styles[zone_idx] = "color: #38BDF8; font-weight: 800; font-family: 'JetBrains Mono';"
            
            # 可买股数
            styles[shares_idx] = "color: #94A3B8; font-weight: 700; font-family: 'JetBrains Mono';"

            # 建议高亮胶囊
            if "买入" in act_v:
                styles[act_idx] = "background-color: #064E3B; color: #34D399; font-weight: 800; border-radius: 4px;"
            elif "加仓" in act_v or "持有" in act_v:
                styles[act_idx] = "background-color: #0284C7; color: #E0F2FE; font-weight: 800; border-radius: 4px;"
            else:
                styles[act_idx] = "background-color: #7F1D1D; color: #FCA5A5; font-weight: 800; border-radius: 4px;"

            return styles

        styled_buy_df = df_buy_candidates.style.apply(style_buy_table, axis=1)
        st.dataframe(
            styled_buy_df,
            use_container_width=True,
            height=240,
            hide_index=True
        )

    with c_tbl_right:
        st.info("""
        **💡 资金滚动调仓法则**
        1. **持仓若进入 ⚠️ 阶段3 (滞涨)** 或出现 **黄昏之星 / 看跌吞没** 时，逢高部分减仓以收回可用现金；
        2. **将收回的现金滚动买入左表 🟢 阶段1 (筑底)** 或出现 **早晨之星** 的优质标的。
        """)

    # 6. 底部 AI 调仓数据包
    st.markdown("---")
    st.markdown("#### 🤖 AI 资产滚动调仓诊断战报 (点击右上角复制)")
    md_report = f"""# 💼 交易员实操持仓与资产滚动 AI 诊断战报

### 1. 账户资产全景
- **总资产 (NAV)**: `${total_account_nav:,.2f}` | **持仓总市值**: `${total_market_val:,.2f}` | **可用现金**: `${cash_capital:,.2f}`
- **浮动总盈亏**: `${total_unrealized_pnl:+,.2f}` ({total_pnl_pct:+.2f}%)

### 2. 当前持仓明细
"""
    for r in rows_summary:
        md_report += f"- **{r['代码']}**: {r['持股量']} 股 | 成本: `${r['买入成本 ($)']:.2f}` | 现价: `${r['最新价 ($)']:.2f}` | 盈亏: `{r['浮动盈亏 ($)']:+.2f} ({r['盈亏率 (%)']:+.2f}%)` | 指令: {r['资金滚动指令']}\n"

    st.code(md_report, language="markdown")
