# 文件名: app.py
# 作用: 癸水 · QQQ 战区座舱（50px 极简微缩 Emoji 导航轨 + 95% 宽屏主视口 + 5M 执行级大白话复盘）

import calendar
import datetime
from datetime import timedelta
import os
import pandas as pd
import pytz
import streamlit as st

from chart_renderer import render_dual_chart
from data_fetcher import fetch_raw_data_with_retry
from futu_engine import compute_futu_13_params, simulate_trades_with_2b
from journal_manager import append_to_journal, load_journal
from macro_radar_plugin import fetch_watchlist_data, analyze_watchlist_rotation, render_macro_radar_tab
from portfolio_manager_plugin import render_portfolio_expansion

# 1. 宽屏页面与初始配置
st.set_page_config(
    page_title="癸水 · QQQ 战区与 2B 同频座舱",
    layout="wide",
    page_icon="🌊",
    initial_sidebar_state="collapsed"
)

# 2. 注入暗黑高对比度护眼 CSS
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&family=JetBrains+Mono:wght@500;700;800&family=Noto+Serif+SC:wght@700;900&display=swap');

    .stApp {
        background-color: #06090E !important;
        color: #E2E8F0 !important;
        font-family: 'Inter', -apple-system, sans-serif !important;
    }
    .block-container {
        padding: 6px 14px !important;
        max-width: 100vw !important;
    }

    /* 顶部紧凑 HUD */
    .compact-hud {
        display: flex;
        align-items: center;
        justify-content: space-between;
        background: rgba(14, 20, 32, 0.85);
        border: 1px solid rgba(255, 255, 255, 0.12);
        border-radius: 6px;
        padding: 6px 14px;
        margin-bottom: 8px;
        backdrop-filter: blur(16px);
    }
    .brand-title {
        font-family: 'Noto Serif SC', serif;
        font-size: 18px;
        font-weight: 900;
        letter-spacing: 0.08em;
        color: #38BDF8;
    }
    .badge-chip {
        font-family: 'JetBrains Mono', monospace;
        font-size: 12px;
        background: rgba(0, 0, 0, 0.4);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 4px;
        padding: 3px 8px;
        color: #94A3B8;
    }
    .badge-chip b { color: #FFFFFF; font-weight: 700; }
    .badge-green {
        background: rgba(0, 230, 118, 0.12);
        border: 1px solid rgba(0, 230, 118, 0.4);
        color: #00E676;
        font-size: 11px;
        font-weight: 700;
        padding: 3px 8px;
        border-radius: 12px;
    }

    /* 指标卡加粗放大 */
    div[data-testid="stMetric"] {
        background: rgba(14, 20, 32, 0.85) !important;
        border: 1px solid rgba(255, 255, 255, 0.12) !important;
        border-radius: 6px !important;
        padding: 8px 12px !important;
    }
    div[data-testid="stMetricValue"] {
        font-family: 'JetBrains Mono', monospace !important;
        font-size: 20px !important;
        font-weight: 800 !important;
        color: #FFFFFF !important;
    }
    div[data-testid="stMetricLabel"] {
        font-size: 12px !important;
        font-weight: 700 !important;
        color: #94A3B8 !important;
    }

    /* 左侧 Mini Rail 图标按钮定制 */
    div[data-testid="column"]:nth-of-type(1) .stButton>button {
        height: 48px !important;
        font-size: 20px !important;
        padding: 0 !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        border-radius: 8px !important;
        background: #0D131F !important;
        border: 1px solid #1E293B !important;
        margin-bottom: 4px !important;
    }
    div[data-testid="column"]:nth-of-type(1) .stButton>button:hover {
        border-color: #38BDF8 !important;
        box-shadow: 0 0 12px rgba(56, 189, 248, 0.35) !important;
        background: rgba(56, 189, 248, 0.1) !important;
    }
</style>
""", unsafe_allow_html=True)

# 3. 时区与时间计算
tz_myt = pytz.timezone("Asia/Kuala_Lumpur")
tz_ny = pytz.timezone("America/New_York")
now_myt = datetime.datetime.now(tz_myt)
now_ny = datetime.datetime.now(tz_ny)

df_j = load_journal()
yesterday_d = now_myt.date() - timedelta(days=1)
yesterday_myt_str = yesterday_d.strftime("%Y-%m-%d")
has_10pm_p = (now_myt.hour >= 22 or now_myt.hour < 5)
has_8am_report = yesterday_myt_str in df_j["Date_MYT"].astype(str).values if not df_j.empty else False

# 4. 顶部超微型紧凑状态条 (HUD)
st.markdown(f"""
<div class="compact-hud">
    <div style="display: flex; align-items: center; gap: 12px;">
        <span class="brand-title">🌊 癸 水</span>
        <span class="badge-chip">MYT <b>{now_myt.strftime('%H:%M:%S')}</b></span>
        <span class="badge-chip">ET <b>{now_ny.strftime('%H:%M:%S')}</b></span>
        <span class="badge-green">● 22:00-24:00 战区窗口</span>
    </div>
    <div style="display: flex; align-items: center; gap: 10px; font-size: 12px;">
        <span>引擎: <b style="color: {'#00E676' if has_10pm_p else '#F59E0B'};">{'✅ 已就绪' if has_10pm_p else '⏳ 准备中'}</b></span>
        <span>战报: <b style="color: {'#00E676' if has_8am_report else '#F59E0B'};">{'✅ 已归档' if has_8am_report else '⏳ 待更新'} ({yesterday_myt_str[-5:]})</b></span>
    </div>
</div>
""", unsafe_allow_html=True)

# 5. 左侧微缩 Mini Rail (0.65) + 右侧 95% 全屏主视口 (9.35)
col_rail, col_main = st.columns([0.65, 9.35], gap="small")

if "active_main_tab" not in st.session_state:
    st.session_state["active_main_tab"] = "tab1"

with col_rail:
    if st.button("📡", help="1. 宏观雷达与 13 标的 Watchlist", use_container_width=True, type="primary" if st.session_state["active_main_tab"] == "tab1" else "secondary"):
        st.session_state["active_main_tab"] = "tab1"
        st.rerun()

    if st.button("💼", help="2. 个人实操持仓与资金滚动罗盘", use_container_width=True, type="primary" if st.session_state["active_main_tab"] == "tab2_port" else "secondary"):
        st.session_state["active_main_tab"] = "tab2_port"
        st.rerun()

    if st.button("🎯", help="3. QQQ 战区富途 13 行代码 (含手动微调)", use_container_width=True, type="primary" if st.session_state["active_main_tab"] == "tab3_cockpit" else "secondary"):
        st.session_state["active_main_tab"] = "tab3_cockpit"
        st.rerun()

    if st.button("📅", help="4. QQQ 2B 同频月历账本与 5M 走势深度复盘", use_container_width=True, type="primary" if st.session_state["active_main_tab"] == "tab4_journal" else "secondary"):
        st.session_state["active_main_tab"] = "tab4_journal"
        st.rerun()

    st.markdown("<div style='height:12px; border-bottom:1px solid #1E293B; margin-bottom:12px;'></div>", unsafe_allow_html=True)
    
    if st.button("🔄", help="刷新全盘最新行情与战区数据", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    if st.button("🧪", help="全链路接口与连接自检", use_container_width=True):
        with st.spinner("自检中..."):
            d1, d5, errs = fetch_raw_data_with_retry(period_5m="5d")
            if errs: st.error("异常: " + "; ".join(errs))
            else: st.success("接口正常")

# ----------------- 右侧 95% 全屏主工作区 -----------------
with col_main:
    
    # ================= TAB 1: 宏观雷达 =================
    if st.session_state["active_main_tab"] == "tab1":
        render_macro_radar_tab()

    # ================= TAB 2: 资金滚动罗盘 =================
    elif st.session_state["active_main_tab"] == "tab2_port":
        st.subheader("💼 我的实操持仓与资金滚动罗盘 (Portfolio Rolling Compass)")
        st.caption("系统自动结合 13 核心标的大级别日周轮动阶段，核算持仓盈亏并给出滚动换股策略。")
        
        with st.spinner("正在提取 13 标的实时行情以核算持仓..."):
            d_daily_p, d_weekly_p = fetch_watchlist_data()
            res_p = analyze_watchlist_rotation(d_daily_p, d_weekly_p)
            
        p_dict = res_p.get("price_lookup", {}) if (res_p and isinstance(res_p, dict)) else {}
        render_portfolio_expansion(price_dict=p_dict)

    # ================= TAB 3: 战区富途代码 =================
    elif st.session_state["active_main_tab"] == "tab3_cockpit":
        st.subheader("🎯 QQQ 5M 战区座舱 (富途 13 行指标代码)")
        
        df_journal_all = load_journal()
        recorded_dates = sorted(list(set(df_journal_all["Date_MYT"].dropna().astype(str).values)), reverse=True) if not df_journal_all.empty else []
        mode_options = ["🔴 实时 / 当前最新战区"] + ([f"📅 历史战区: {d}" for d in recorded_dates] if recorded_dates else [])
        sel_mode = st.selectbox("请选择战区版本（白天可调阅过去任意一天 13 行参数）:", options=mode_options, key="tab3_mode_picker")

        p_to_display = None
        display_title = ""

        if sel_mode.startswith("📅 历史战区:"):
            target_hist_date = sel_mode.replace("📅 历史战区: ", "").strip()
            hist_row = df_journal_all[df_journal_all["Date_MYT"].astype(str) == target_hist_date].iloc[0]
            p_to_display = {
                "live_price": float(hist_row.get("Entry_Price", hist_row.get("PDH", 488.62))),
                "TREND_BIAS": int(hist_row.get("TREND_BIAS", 1)),
                "BIAS_DESC": "🟢 绿灯 (做多为主)" if hist_row.get("TREND_BIAS", 1) == 1 else ("🔴 红灯 (做空为主)" if hist_row.get("TREND_BIAS", 1) == -1 else "🟡 黄灯 (震荡防守)"),
                "EMA20_1H": float(hist_row.get("EMA20_1H", 487.50)),
                "ATR_1H": float(hist_row.get("ATR_1H", 1.25)),
                "SBR_TOP": float(hist_row.get("SBR_TOP", 491.50)), "SBR_BOT": float(hist_row.get("SBR_BOT", 490.80)), "SBR_TIME": f"{target_hist_date} 战区",
                "RBS_TOP": float(hist_row.get("RBS_TOP", 487.00)), "RBS_BOT": float(hist_row.get("RBS_BOT", 486.20)), "RBS_TIME": f"{target_hist_date} 战区",
                "SBR2_TOP": float(hist_row.get("SBR2_TOP", 493.20)), "SBR2_BOT": float(hist_row.get("SBR2_BOT", 492.50)), "SBR2_TIME": "Tier-2 High",
                "RBS2_TOP": float(hist_row.get("RBS2_TOP", 485.00)), "RBS2_BOT": float(hist_row.get("RBS2_BOT", 484.20)), "RBS2_TIME": "Tier-2 Low",
                "PDH": float(hist_row.get("PDH", 489.90)), "PDH_TIME": "PDH",
                "PDL": float(hist_row.get("PDL", 484.10)), "PDL_TIME": "PDL",
                "PMH": float(hist_row.get("PMH", 489.20)), "PMH_TIME": "PMH",
                "PML": float(hist_row.get("PML", 486.80)), "PML_TIME": "PML"
            }
            display_title = f"📋 历史存档 [{target_hist_date}] 13 行富途代码 (可直接复制):"
        else:
            d1h, d5m, _ = fetch_raw_data_with_retry(period_5m="5d")
            if d1h is not None and d5m is not None:
                p_to_display = compute_futu_13_params(d1h, d5m, now_ny)
                display_title = "📋 最新实时 13 行富途代码 (点击右上角复制):"
            
            if not p_to_display:
                if recorded_dates:
                    latest_d = recorded_dates[0]
                    hist_row = df_journal_all[df_journal_all["Date_MYT"].astype(str) == latest_d].iloc[0]
                    p_to_display = {
                        "live_price": float(hist_row.get("PDH", 488.62)),
                        "TREND_BIAS": int(hist_row.get("TREND_BIAS", 1)),
                        "BIAS_DESC": "🟢 绿灯 (做多为主)" if hist_row.get("TREND_BIAS", 1) == 1 else ("🔴 红灯 (做空为主)" if hist_row.get("TREND_BIAS", 1) == -1 else "🟡 黄灯 (震荡防守)"),
                        "EMA20_1H": float(hist_row.get("EMA20_1H", 487.50)),
                        "ATR_1H": float(hist_row.get("ATR_1H", 1.25)),
                        "SBR_TOP": float(hist_row.get("SBR_TOP", 491.50)), "SBR_BOT": float(hist_row.get("SBR_BOT", 490.80)), "SBR_TIME": f"{latest_d} 战区",
                        "RBS_TOP": float(hist_row.get("RBS_TOP", 487.00)), "RBS_BOT": float(hist_row.get("RBS_BOT", 486.20)), "RBS_TIME": f"{latest_d} 战区",
                        "SBR2_TOP": float(hist_row.get("SBR2_TOP", 493.20)), "SBR2_BOT": float(hist_row.get("SBR2_BOT", 492.50)), "SBR2_TIME": "Tier-2 High",
                        "RBS2_TOP": float(hist_row.get("RBS2_TOP", 485.00)), "RBS2_BOT": float(hist_row.get("RBS2_BOT", 484.20)), "RBS2_TIME": "Tier-2 Low",
                        "PDH": float(hist_row.get("PDH", 489.90)), "PDH_TIME": "PDH",
                        "PDL": float(hist_row.get("PDL", 484.10)), "PDL_TIME": "PDL",
                        "PMH": float(hist_row.get("PMH", 489.20)), "PMH_TIME": "PMH",
                        "PML": float(hist_row.get("PML", 486.80)), "PML_TIME": "PML"
                    }
                    display_title = f"📋 最近存档 [{latest_d}] 13 行富途代码 (可直接复制):"
                else:
                    p_to_display = {
                        "live_price": 488.62, "TREND_BIAS": 1, "BIAS_DESC": "🟢 绿灯 (做多为主)",
                        "EMA20_1H": 487.50, "ATR_1H": 1.25,
                        "SBR_TOP": 491.50, "SBR_BOT": 490.80, "SBR_TIME": "1H 阻力",
                        "RBS_TOP": 487.00, "RBS_BOT": 486.20, "RBS_TIME": "1H 支撑",
                        "SBR2_TOP": 493.20, "SBR2_BOT": 492.50, "SBR2_TIME": "Tier-2 High",
                        "RBS2_TOP": 485.00, "RBS2_BOT": 484.20, "RBS2_TIME": "Tier-2 Low",
                        "PDH": 489.90, "PDH_TIME": "PDH", "PDL": 484.10, "PDL_TIME": "PDL",
                        "PMH": 489.20, "PMH_TIME": "PMH", "PML": 486.80, "PML_TIME": "PML"
                    }
                    display_title = "📋 默认基准 13 行富途代码 (点击右上角复制):"

        if p_to_display:
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("🎯 现价 / 锚点", f"${p_to_display['live_price']:.2f}")
            m2.metric("🚦 三灯信号定调", p_to_display["BIAS_DESC"])
            m3.metric("📈 1H EMA20 均线", f"${p_to_display['EMA20_1H']:.2f}")
            m4.metric("📊 1H ATR 波动", f"${p_to_display['ATR_1H']:.2f}")

            with st.expander("⚙️ 手动微调 / 覆盖当前 13 行战区参数", expanded=False):
                st.caption("允许交易员根据盘感或消息面手动修正 SBR/RBS 与多空三灯，点击保存后实时生效。")
                c_m1, c_m2, c_m3 = st.columns(3)
                with c_m1:
                    m_bias = st.selectbox("1. TREND_BIAS (三灯定调)", options=[1, 0, -1], index=0 if p_to_display['TREND_BIAS']==1 else (1 if p_to_display['TREND_BIAS']==0 else 2), format_func=lambda x: "🟢 1 (多头绿灯)" if x==1 else ("🟡 0 (震荡防守)" if x==0 else "🔴 -1 (空头红灯)"))
                    m_sbr_top = st.number_input("2. SBR_TOP (1H 阻力顶沿)", value=float(p_to_display['SBR_TOP']), step=0.5)
                    m_sbr_bot = st.number_input("3. SBR_BOT (1H 阻力底沿)", value=float(p_to_display['SBR_BOT']), step=0.5)
                with c_m2:
                    m_rbs_top = st.number_input("4. RBS_TOP (1H 支撑顶沿)", value=float(p_to_display['RBS_TOP']), step=0.5)
                    m_rbs_bot = st.number_input("5. RBS_BOT (1H 支撑底沿)", value=float(p_to_display['RBS_BOT']), step=0.5)
                    m_pdh = st.number_input("10. PDH_LINE (昨日最高价)", value=float(p_to_display['PDH']), step=0.5)
                with c_m3:
                    m_pdl = st.number_input("11. PDL_LINE (昨日最低价)", value=float(p_to_display['PDL']), step=0.5)
                    m_pmh = st.number_input("12. PMH_LINE (盘前最高价)", value=float(p_to_display['PMH']), step=0.5)
                    m_pml = st.number_input("13. PML_LINE (盘前最低价)", value=float(p_to_display['PML']), step=0.5)

                if st.button("💾 保存并应用手动微调参数", key="btn_apply_manual_p13"):
                    p_to_display['TREND_BIAS'] = m_bias
                    p_to_display['BIAS_DESC'] = "🟢 绿灯 (做多为主)" if m_bias == 1 else ("🔴 红灯 (做空为主)" if m_bias == -1 else "🟡 黄灯 (震荡防守)")
                    p_to_display['SBR_TOP'] = m_sbr_top
                    p_to_display['SBR_BOT'] = m_sbr_bot
                    p_to_display['RBS_TOP'] = m_rbs_top
                    p_to_display['RBS_BOT'] = m_rbs_bot
                    p_to_display['PDH'] = m_pdh
                    p_to_display['PDL'] = m_pdl
                    p_to_display['PMH'] = m_pmh
                    p_to_display['PML'] = m_pml
                    st.success("✅ 手动参数已成功覆盖并生效！")

            out_lines = [
                f"TREND_BIAS := {p_to_display['TREND_BIAS']};       {{ 1. QQQ三灯判定: 1=绿灯做多, -1=红灯做空, 0=黄灯防守 }}",
                "",
                "{ --- 第一梯队主战区 (PRIMARY ZONES) --- }",
                f"SBR_TOP := {round(p_to_display['SBR_TOP'], 2)}; {{ 2. PRIMARY 1H 阻力顶沿 [{p_to_display['SBR_TIME']}] }}",
                f"SBR_BOT := {round(p_to_display['SBR_BOT'], 2)}; {{ 3. PRIMARY 1H 阻力底沿 [{p_to_display['SBR_TIME']}] }}",
                f"RBS_TOP := {round(p_to_display['RBS_TOP'], 2)}; {{ 4. PRIMARY 1H 支撑顶沿 [{p_to_display['RBS_TIME']}] }}",
                f"RBS_BOT := {round(p_to_display['RBS_BOT'], 2)}; {{ 5. PRIMARY 1H 支撑底沿 [{p_to_display['RBS_TIME']}] }}",
                "",
                "{ --- 第二梯队拓展战区 (SECONDARY ZONES) --- }",
                f"SBR2_TOP := {round(p_to_display['SBR2_TOP'], 2)}; {{ 6. SECONDARY 1H 更高阻力顶沿 [{p_to_display['SBR2_TIME']}] }}",
                f"SBR2_BOT := {round(p_to_display['SBR2_BOT'], 2)}; {{ 7. SECONDARY 1H 更高阻力底沿 [{p_to_display['SBR2_TIME']}] }}",
                f"RBS2_TOP := {round(p_to_display['RBS2_TOP'], 2)}; {{ 8. SECONDARY 1H 更低支撑顶沿 [{p_to_display['RBS2_TIME']}] }}",
                f"RBS2_BOT := {round(p_to_display['RBS2_BOT'], 2)}; {{ 9. SECONDARY 1H 更低支撑底沿 [{p_to_display['RBS2_TIME']}] }}",
                "",
                "{ --- 全市场客观极值 (SWEEP ANCHORS) --- }",
                f"PDH_LINE := {round(p_to_display['PDH'], 2)}; {{ 10. 昨日最高价 PDH [{p_to_display['PDH_TIME']}] }}",
                f"PDL_LINE := {round(p_to_display['PDL'], 2)}; {{ 11. 昨日最低价 PDL [{p_to_display['PDL_TIME']}] }}",
                f"PMH_LINE := {round(p_to_display['PMH'], 2)}; {{ 12. 盘前最高价 PMH [{p_to_display['PMH_TIME']}] }}",
                f"PML_LINE := {round(p_to_display['PML'], 2)}; {{ 13. 盘前最低价 PML [{p_to_display['PML_TIME']}] }}"
            ]
            st.markdown(f"#### {display_title}")
            st.code("\n".join(out_lines), language="pascal")

    # ================= TAB 4: 2B月历与深度复盘 =================
    elif st.session_state["active_main_tab"] == "tab4_journal":
        st.subheader("📅 QQQ 2B 同频月历账本与多维复盘 (22:00 - 24:00 MYT)")
        
        # 模块 A: 昨夜战况极速核验与大白话聊天复盘 Prompt 数据包
        with st.expander(f"⚡ 展开查看【昨夜 ({yesterday_myt_str}) 22:00-24:00 战况极速核验】", expanded=True):
            d1h_y, d5m_y, _ = fetch_raw_data_with_retry(period_5m="5d")
            if d1h_y is not None and d5m_y is not None:
                dt_y_10pm_myt = tz_myt.localize(datetime.datetime.combine(yesterday_d, datetime.time(22, 0, 0)))
                cutoff_y_ny = dt_y_10pm_myt.astimezone(tz_ny)
                window_y_end_ny = cutoff_y_ny + timedelta(hours=2)
                
                p_y = compute_futu_13_params(d1h_y, d5m_y, cutoff_y_ny)
                if p_y:
                    trades_y, day_5m_y = simulate_trades_with_2b(d5m_y, p_y, cutoff_y_ny, window_y_end_ny)
                    yc1, yc2, yc3, yc4 = st.columns(4)
                    yc1.metric("🚦 昨夜三灯定调", p_y["BIAS_DESC"])
                    yc2.metric("📈 昨夜 1H EMA20", f"${p_y['EMA20_1H']:.2f}")
                    yc3.metric("📊 昨夜 1H ATR", f"${p_y['ATR_1H']:.2f}")
                    
                    if trades_y:
                        t_first = trades_y[0]
                        yc4.metric("🎯 昨夜战果", f"{t_first['Result']} ({t_first['PnL_Points']:+.2f} pt)", f"信号: {t_first['Signal']}")
                        df_y_show = pd.DataFrame(trades_y)[[c for c in pd.DataFrame(trades_y).columns if not c.endswith("_DT_NY")]]
                        
                        def style_yest_table(row):
                            styles = [""] * len(row)
                            if "PnL_Points" in df_y_show.columns:
                                p_idx = df_y_show.columns.get_loc("PnL_Points")
                                p_v = row["PnL_Points"]
                                if p_v > 0: styles[p_idx] = "color: #00E676; font-weight: 800; font-family: 'JetBrains Mono';"
                                elif p_v < 0: styles[p_idx] = "color: #FF5252; font-weight: 800; font-family: 'JetBrains Mono';"
                            return styles
                            
                        st.dataframe(df_y_show.style.apply(style_yest_table, axis=1), use_container_width=True, hide_index=True)
                    else:
                        yc4.metric("🎯 昨夜战果", "⚪ 严格空仓", "未触发开仓形态")
                        st.info("昨夜价格未触及战区准入条件，或未出现 1.25 倍放量 2B/吞没反转，严格执行空仓纪律。")

                    # 提取 5M 走势细部事实
                    if day_5m_y is not None and not day_5m_y.empty:
                        min_p_5m = day_5m_y["Low"].min()
                        max_p_5m = day_5m_y["High"].max()
                        heavy_vol_cnt = int(day_5m_y["VOL_HEAVY"].sum()) if "VOL_HEAVY" in day_5m_y.columns else 0
                        pierce_info = "在战区边缘窄幅拉锯"
                        if min_p_5m < p_y["PDL"]: pierce_info = "向下刺穿了昨日最低价 PDL"
                        elif max_p_5m > p_y["PDH"]: pierce_info = "向上冲破了昨日最高价 PDH"
                    else:
                        min_p_5m, max_p_5m, heavy_vol_cnt, pierce_info = 0.0, 0.0, 0, "数据同步中"

                    # 提取实操执行状态
                    if trades_y:
                        t_obj = trades_y[0]
                        t_res_str = f"{t_obj['Result']} ({t_obj['PnL_Points']:+.2f} pt)"
                        t_sig_str = t_obj['Signal']
                        t_entry_str = f"${t_obj['Entry_Price']:.2f} ({t_obj['Entry_MYT']} MYT)"
                        t_exit_str = f"${t_obj['Exit_Price']:.2f} ({t_obj['Exit_MYT']} MYT)"
                        t_tp_sl_str = f"止盈 TP: ${t_obj['TP']:.2f} | 止损 SL: ${t_obj['SL']:.2f}"
                        t_reason_str = t_obj['Reason']
                    else:
                        t_res_str = "⚪ 严格纪律空仓 (0.00 pt)"
                        t_sig_str = "NO_TRADE (未出信号)"
                        t_entry_str = "未开仓"
                        t_exit_str = "未开仓"
                        t_tp_sl_str = "无"
                        t_reason_str = "价格未进战区缓冲带，或未出现 ≥1.25x 放量 2B/吞没形态，按纪律管住手空仓保本金。"

                    # 构建通俗易懂的大白话复盘 Prompt
                    ai_chat_prompt_t4 = f"""# 🎯 QQQ 5M 走势与新闻大白话复盘指令包 (发给 ChatGPT/Claude 聊盘面)

## 一、 昨夜战区客观数据事实 ({yesterday_myt_str})
- **复盘时间窗口**: `22:00 - 24:00 (MYT)` [美东时间 `10:00 - 12:00 (ET)`]
- **宏观三灯总闸门**: `{p_y['BIAS_DESC']}` (TREND_BIAS = `{p_y['TREND_BIAS']}`)
- **核心均线与波幅**: 1H EMA20 = `${p_y['EMA20_1H']:.2f}` | 1H ATR 基础波幅 = `${p_y['ATR_1H']:.2f}`
- **1H 战区阻力与支撑防线**:
  - 天花板 (SBR 阻力战区): `${p_y['SBR_BOT']:.2f} ~ ${p_y['SBR_TOP']:.2f}` [{p_y['SBR_TIME']}]
  - 地板 (RBS 支撑战区): `${p_y['RBS_BOT']:.2f} ~ ${p_y['RBS_TOP']:.2f}` [{p_y['RBS_TIME']}]
  - 昨日最高/最低 (PDH / PDL): `${p_y['PDH']:.2f}` / `${p_y['PDL']:.2f}`
  - 盘前最高/最低 (PMH / PML): `${p_y['PMH']:.2f}` / `${p_y['PML']:.2f}`
- **5M K线走势细节**:
  - 窗口内最低/最高价: `${min_p_5m:.2f}` ~ `${max_p_5m:.2f}`
  - 异动放量 K 表现: 窗口内共有 `{heavy_vol_cnt}` 根 5M K线成交量达到 1.25 倍均量
  - 关键点位刺穿情况: `{pierce_info}`
- **座舱系统执行判定**:
  - 战果状态: **{t_res_str}** | 执行信号: `{t_sig_str}`
  - 进出场记录: `{t_entry_str}` -> `{t_exit_str}` ({t_reason_str})
  - 挂单止损与止盈: `{t_tp_sl_str}`

---

## 二、 给军师 AI 的大白话聊天任务 (请严格遵守以下规则与我对话):
请你扮演我身边最懂实战的「贴身看盘军师」与「老操盘手朋友」，像平时跟我喝茶聊天一样，用最接地气的大白话跟我聊聊昨晚的走势：

1. **【严禁输出任何表格】**：绝对不要给我发冷冰冰的 Markdown 表格或代码框，完全用自然分段的聊天口吻和我交流。
2. **【联网查昨夜新闻，打比方讲内幕】**：请联网搜索昨夜美股到底出了什么宏观大事件（如 CPI/非农/美联储表态/国债收益率）以及科技巨头（英伟达、苹果、微软、特斯拉）的异动。用生动形象的比喻（比如神仙打架、主力演戏、挖坑诱敌）告诉我昨晚主力在玩什么套路。
3. **【核对系统信号对不对】**：帮我客观核查昨晚 5M 走势有没有出现“假突破扫损翻转”或“战区反转”？系统的定调（比如红灯空头、或者没开仓空仓）到底做对了没有？有没有帮我避开来回挨打的泥潭？
4. **【今晚怎么干的大白话指引】**：不画饼、不给虚假希望，用一两句大白话告诉我今晚 22:00 (MYT) 开盘前看什么天花板和地板点位，大盘踩到什么价位咱才考虑顺势出手，否则怎么继续喝茶防守。
"""
                    st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)
                    with st.expander("🤖 展开查看【📋 一键复制 AI 大白话复盘与新闻诊断 Prompt】", expanded=True):
                        st.caption("👇 点击下方代码框右上角一键复制完整战报，直接粘贴给 ChatGPT / Claude / Gemini 开启聊天：")
                        st.code(ai_chat_prompt_t4, language="markdown")
            else:
                st.warning("行情接口连接中，请稍候点击刷新。")

        st.markdown("---")

        c_y, c_m, c_exp = st.columns([1, 1, 2])
        with c_y:
            sel_y = st.selectbox("年份选择", [2026, 2025, 2024], index=0, key="sel_y_picker_tab4_final")
        with c_m:
            sel_m = st.selectbox("月份选择", list(range(1, 13)), index=now_myt.month - 1, key="sel_m_picker_tab4_final")

        col_btn1, col_btn2, col_btn3 = st.columns([1.5, 2, 1.5])
        with col_btn1:
            if st.button("🛠️ 结算昨夜 22:00-24:00 账本", key="btn_settle_yest_journal_tab4_final"):
                with st.spinner("正在核算昨夜交易..."):
                    d1h, d5m, _ = fetch_raw_data_with_retry(period_5m="5d")
                    target_d = now_myt.date() - timedelta(days=1) if now_myt.hour < 22 else now_myt.date()
                    dt_10pm_myt = tz_myt.localize(datetime.datetime.combine(target_d, datetime.time(22, 0, 0)))
                    cutoff_ny = dt_10pm_myt.astimezone(tz_ny)
                    window_end_ny = cutoff_ny + timedelta(hours=2)
                    
                    p = compute_futu_13_params(d1h, d5m, cutoff_ny)
                    if p:
                        trades, _ = simulate_trades_with_2b(d5m, p, cutoff_ny, window_end_ny)
                        ok, msg = append_to_journal(target_d.strftime("%Y-%m-%d"), p, trades, overwrite=True)
                        if ok: st.success(f"🎉 {target_d} 结算完成！"); st.rerun()
                        else: st.warning(msg)

        with col_btn2:
            if st.button(f"⚡ 一键回溯/刷新 {sel_y}年{sel_m}月 历史账本", key="btn_backfill_monthly_journal_tab4_final"):
                with st.spinner(f"正在回溯计算 {sel_y} 年 {sel_m} 月数据..."):
                    d1h, d5m, _ = fetch_raw_data_with_retry(period_5m="1mo")
                    if d1h is not None and d5m is not None:
                        dates_in_5m = sorted(list(set(d5m.index.date)))
                        target_dates = [d for d in dates_in_5m if d.year == sel_y and d.month == sel_m and d < now_ny.date()]
                        
                        added_cnt = 0
                        for d in target_dates:
                            dt_10pm_myt = tz_myt.localize(datetime.datetime.combine(d, datetime.time(22, 0, 0)))
                            cutoff_ny = dt_10pm_myt.astimezone(tz_ny)
                            window_end_ny = cutoff_ny + timedelta(hours=2)
                            
                            p_day = compute_futu_13_params(d1h, d5m, cutoff_ny)
                            if p_day:
                                trades_day, _ = simulate_trades_with_2b(d5m, p_day, cutoff_ny, window_end_ny)
                                ok, _ = append_to_journal(d.strftime("%Y-%m-%d"), p_day, trades_day, overwrite=True)
                                if ok: added_cnt += 1
                        
                        st.success(f"🎉 回溯完成，已生成 {added_cnt} 个交易日记录！")
                        st.rerun()

        with col_btn3:
            if st.button("🗑️ 清空历史账本重新生成", key="btn_clear_journal_file_tab4_final"):
                if os.path.exists("monthly_trade_records.csv"):
                    os.remove("monthly_trade_records.csv")
                    st.success("账本已清空！")
                    st.rerun()

        st.markdown("---")

        df_journal = load_journal()
        if not df_journal.empty and "Date_MYT" in df_journal.columns:
            df_journal["DT_OBJ"] = pd.to_datetime(df_journal["Date_MYT"])
            df_month = df_journal[(df_journal["DT_OBJ"].dt.year == sel_y) & (df_journal["DT_OBJ"].dt.month == sel_m)].copy()
        else:
            df_month = pd.DataFrame()

        valid_trades = df_month[df_month["Signal"] != "NO_TRADE"] if not df_month.empty else pd.DataFrame()
        total_trades = len(valid_trades)
        win_trades = len(valid_trades[valid_trades["PnL_Points"] > 0]) if total_trades > 0 else 0
        loss_trades = len(valid_trades[valid_trades["PnL_Points"] < 0]) if total_trades > 0 else 0
        win_rate = (win_trades / total_trades * 100) if total_trades > 0 else 0.0
        net_pnl = df_month["PnL_Points"].sum() if not df_month.empty else 0.0
        empty_days = len(df_month[df_month["Signal"] == "NO_TRADE"]) if not df_month.empty else 0

        with c_exp:
            if not df_month.empty:
                csv_data = df_month.to_csv(index=False, encoding="utf-8-sig")
                st.download_button(f"📥 导出 {sel_y}年{sel_m}月 完整账本 (.csv)", csv_data, f"journal_{sel_y}_{sel_m:02d}.csv", "text/csv")

        k1, k2, k3, k4 = st.columns(4)
        k1.metric("🗓️ 统计月份", f"{sel_y} 年 {sel_m} 月")
        k2.metric("💰 窗口净盈亏", f"{net_pnl:+.2f} pt", "正向收益" if net_pnl >= 0 else "回撤控制中")
        k3.metric("🎯 战区胜率", f"{win_rate:.1f}%", f"{win_trades} 胜 / {total_trades} 战")
        k4.metric("📊 交易笔数", f"{total_trades} 笔", f"空仓 {empty_days} 天")

        st.markdown("---")

        # 模块 C: 纯 5 交易日宽屏月历
        col_cal_left, col_cal_right = st.columns([3.2, 1.2])

        day_records = {}
        recorded_dates_list = []
        if not df_month.empty:
            for _, row in df_month.iterrows():
                d_num = pd.to_datetime(row["Date_MYT"]).day
                day_records[d_num] = row
                recorded_dates_list.append(str(row["Date_MYT"]))
            recorded_dates_list = sorted(list(set(recorded_dates_list)), reverse=True)

        if "active_chart_date" not in st.session_state:
            st.session_state["active_chart_date"] = recorded_dates_list[0] if recorded_dates_list else None
        elif st.session_state["active_chart_date"] not in recorded_dates_list and recorded_dates_list:
            st.session_state["active_chart_date"] = recorded_dates_list[0]

        with col_cal_left:
            st.markdown("#### 🗓️ 交易日月历 (周一至周五 · 点击即时查图)")
            cal = calendar.monthcalendar(sel_y, sel_m)
            
            cols_header = st.columns(5)
            days_name = ["周一 (Mon)", "周二 (Tue)", "周三 (Wed)", "周四 (Thu)", "周五 (Fri)"]
            for idx, d_name in enumerate(days_name):
                cols_header[idx].markdown(f"<div style='text-align:center; font-weight:700; color:#94A3B8; font-size:12px;'>{d_name}</div>", unsafe_allow_html=True)

            for week in cal:
                workdays = week[0:5]
                if all(d == 0 for d in workdays):
                    continue
                    
                w_cols = st.columns(5)
                for d_idx, day_num in enumerate(workdays):
                    with w_cols[d_idx]:
                        if day_num == 0:
                            st.markdown("<div style='height:105px;'></div>", unsafe_allow_html=True)
                        else:
                            if day_num in day_records:
                                rec = day_records[day_num]
                                pnl = float(rec["PnL_Points"])
                                bias_v = rec["TREND_BIAS"]
                                bias_tag = "多" if bias_v > 0 else ("空" if bias_v < 0 else "震荡")
                                this_date_str = str(rec["Date_MYT"])
                                is_active = (st.session_state["active_chart_date"] == this_date_str)
                                
                                border_style = "2px solid #38BDF8" if is_active else ("1px solid #00E676" if pnl > 0 else ("1px solid #FF5252" if pnl < 0 else "1px solid #334155"))
                                
                                if rec["Signal"] == "NO_TRADE":
                                    bg_color = "#0F172A"
                                    status_html = "<span style='color:#94A3B8; font-size:11px; font-weight:700;'>⚪ 纪律空仓</span>"
                                else:
                                    bg_color = "#064E3B" if pnl > 0 else "#7F1D1D"
                                    sgn = "+" if pnl > 0 else ""
                                    status_html = f"<span style='color:#FFFFFF; font-size:13px; font-weight:800;'>{sgn}{pnl:.2f} pt</span><br><span style='color:#E2E8F0; font-size:10px;'>{rec['Signal']}</span>"

                                st.markdown(f"""
                                <div style='border:{border_style}; border-radius:6px; padding:6px; min-height:68px; background-color:{bg_color}; text-align:center;'>
                                    <div style='text-align:left; color:#CBD5E1; font-size:11px; font-weight:700;'>{day_num} <span style='font-size:9px; color:#94A3B8;'>({bias_tag})</span></div>
                                    {status_html}
                                </div>
                                """, unsafe_allow_html=True)
                                
                                btn_label = "👉 正在看" if is_active else "🔍 查图"
                                if st.button(btn_label, key=f"btn_cal_5d_final_{this_date_str}"):
                                    st.session_state["active_chart_date"] = this_date_str
                                    st.rerun()
                            else:
                                st.markdown(f"""
                                <div style='border:1px dashed #1E293B; border-radius:6px; padding:6px; min-height:100px; text-align:center; background-color:#0B0F19;'>
                                    <div style='text-align:left; color:#475569; font-size:11px;'>{day_num}</div>
                                    <div style='margin-top:25px; color:#475569; font-size:11px;'>休战 / 无数据</div>
                                </div>
                                """, unsafe_allow_html=True)

        with col_cal_right:
            st.markdown("#### 🛡️ 战术纪律看板")
            cur_sel_date = st.session_state.get("active_chart_date")
            if cur_sel_date and not df_month.empty:
                sel_rec_series = df_month[df_month["Date_MYT"].astype(str) == cur_sel_date]
                if not sel_rec_series.empty:
                    s_row = sel_rec_series.iloc[0]
                    b_val = s_row.get("TREND_BIAS", 0)
                    b_desc = "🟢 绿灯多" if b_val > 0 else ("🔴 红灯空" if b_val < 0 else "🟡 震荡防守")
                    
                    st.info(f"""
                    **📌 选中日期**: `{cur_sel_date}`
                    - **宏观定调**: `{b_desc}`
                    - **执行信号**: `{s_row['Signal']}`
                    - **窗口盈亏**: `{float(s_row['PnL_Points']):+.2f} pt`
                    - **入场点位**: `${float(s_row.get('Entry_Price', 0.0)):.2f}`
                    - **止盈 / 止损**: `${float(s_row.get('TP', 0.0)):.2f}` / `${float(s_row.get('SL', 0.0)):.2f}`
                    - **平仓原因**: `{s_row.get('Reason', '纪律平仓')}`
                    """)
                else:
                    st.info(f"选定 `{cur_sel_date}` 无详细开仓数据。")
            else:
                st.info("💡 点击左侧月历中任意一天的「🔍 查图」，此处将实时联动展示战术明细。")

            st.markdown("---")
            total_days_cnt = max(len(df_month), 1)
            discipline_rate = (empty_days / total_days_cnt) * 100
            st.write(f"🛡️ **空仓防守率**: `{discipline_rate:.1f}%`")
            st.write(f"🎯 **开仓出手率**: `{100 - discipline_rate:.1f}%`")
            if total_trades > 0:
                avg_win = valid_trades[valid_trades["PnL_Points"] > 0]["PnL_Points"].mean() if win_trades > 0 else 0.0
                avg_loss = abs(valid_trades[valid_trades["PnL_Points"] < 0]["PnL_Points"].mean()) if loss_trades > 0 else 0.0
                pnl_ratio = (avg_win / avg_loss) if avg_loss > 0 else (avg_win if avg_win > 0 else 1.0)
                st.write(f"⚖️ **实操盈亏比**: `{pnl_ratio:.2f} : 1`")

        # 模块 D: 13 行全量战区参数历史大表
        st.markdown("---")
        with st.expander(f"🔍 展开查看【{sel_y} 年 {sel_m} 月 13 行全量战区点位与交易历史大表】", expanded=False):
            if not df_month.empty:
                cols_13_order = [
                    "Date_MYT", "TREND_BIAS", "EMA20_1H", "ATR_1H",
                    "SBR_TOP", "SBR_BOT", "RBS_TOP", "RBS_BOT",
                    "SBR2_TOP", "SBR2_BOT", "RBS2_TOP", "RBS2_BOT",
                    "PDH", "PDL", "PMH", "PML",
                    "Signal", "Entry_MYT", "Exit_MYT", "Entry_Price", "Exit_Price", "SL", "TP", "PnL_Points", "Reason", "Result"
                ]
                valid_show_cols = [c for c in cols_13_order if c in df_month.columns]
                df_history_show = df_month[valid_show_cols].sort_values(by="Date_MYT", ascending=False)

                def style_history_table(row):
                    styles = [""] * len(row)
                    if "PnL_Points" in df_history_show.columns:
                        p_idx = df_history_show.columns.get_loc("PnL_Points")
                        p_v = row["PnL_Points"]
                        if p_v > 0: styles[p_idx] = "color: #00E676; font-weight: 800; font-family: 'JetBrains Mono';"
                        elif p_v < 0: styles[p_idx] = "color: #FF5252; font-weight: 800; font-family: 'JetBrains Mono';"
                    if "TREND_BIAS" in df_history_show.columns:
                        b_idx = df_history_show.columns.get_loc("TREND_BIAS")
                        b_v = row["TREND_BIAS"]
                        if b_v == 1: styles[b_idx] = "color: #00E676; font-weight: 800;"
                        elif b_v == -1: styles[b_idx] = "color: #FF5252; font-weight: 800;"
                    return styles

                st.dataframe(df_history_show.style.apply(style_history_table, axis=1), use_container_width=True, hide_index=True)
            else:
                st.info("当月暂无历史数据，请点击上方「一键回溯」生成。")

        # 模块 E: 5M 走势与副图 VPA 量能回放
        st.markdown("---")
        active_date = st.session_state.get("active_chart_date")
        if active_date and not df_month.empty:
            st.subheader(f"📊 5M 走势与 VPA 量能回放：[{active_date}]")
            
            st.write("📌 **快速切换日期：**")
            chip_cols = st.columns(min(len(recorded_dates_list), 10)) if recorded_dates_list else []
            for c_i, r_date in enumerate(recorded_dates_list[:10]):
                with chip_cols[c_i]:
                    is_sel = (r_date == active_date)
                    label = f"👉 {r_date[-5:]}" if is_sel else f"{r_date[-5:]}"
                    if st.button(label, key=f"chip_jump_final_{r_date}"):
                        st.session_state["active_chart_date"] = r_date
                        st.rerun()

            with st.spinner(f"正在加载 {active_date} 5M 走势与 VPA 量能双层图..."):
                d1h_hist, d5m_hist, _ = fetch_raw_data_with_retry(period_5m="1mo")
                if d1h_hist is not None and d5m_hist is not None:
                    target_hist_d = datetime.datetime.strptime(active_date, "%Y-%m-%d").date()
                    dt_hist_10pm_myt = tz_myt.localize(datetime.datetime.combine(target_hist_d, datetime.time(22, 0, 0)))
                    cutoff_hist_ny = dt_hist_10pm_myt.astimezone(tz_ny)
                    window_hist_end_ny = cutoff_hist_ny + timedelta(hours=2)
                    
                    p_hist = compute_futu_13_params(d1h_hist, d5m_hist, cutoff_hist_ny)
                    trades_hist, day_5m_hist = simulate_trades_with_2b(d5m_hist, p_hist, cutoff_hist_ny, window_hist_end_ny)
                    
                    if trades_hist:
                        t = trades_hist[0]
                        st.success(f"🎯 **战果明细**：{t['Result']} ({t['PnL_Points']:+.2f} pt) | 信号：`{t['Signal']}` | 入场：`{t['Entry_MYT']}` | 出场：`{t['Exit_MYT']}` ({t['Reason']})")
                    else:
                        st.info(f"⚪ **战果明细**：{active_date} 22:00-24:00 (MYT) 未触发战区或 2B 条件，严格按纪律空仓。")

                    render_dual_chart(
                        day_5m_hist, p_hist, trades_hist, dt_hist_10pm_myt,
                        title_text=f"历史复盘 ({active_date}) | 5M 战场执行与 VPA 量能异动"
                    )
        else:
            st.info("💡 请在上方月历点击任意日期的「🔍 查图」，或点击上方快捷胶囊直接展示图表。")
