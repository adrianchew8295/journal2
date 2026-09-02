# 文件名: app.py
# 作用: 癸水 · QQQ 战区与 2B 同频座舱（大字护眼 · 真实数据全功能原生版）

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
from macro_radar_plugin import render_macro_radar_tab

# 1. 页面基础配置
st.set_page_config(
    page_title="癸水 · QQQ 2B与战区同频座舱",
    layout="wide",
    page_icon="🌊",
    initial_sidebar_state="collapsed"
)

# 2. 注入针对 41 岁舒适护眼的大字号、高对比暗黑 CSS
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&family=JetBrains+Mono:wght@500;700;800&family=Noto+Serif+SC:wght@700;900&display=swap');

    /* 全局背景与高对比字体 */
    .stApp {
        background-color: #06090E !important;
        color: #E2E8F0 !important;
        font-family: 'Inter', -apple-system, sans-serif !important;
        font-size: 14px !important;
    }

    /* 顶部大标题与癸水 Logo */
    .brand-title-box {
        display: flex;
        align-items: center;
        gap: 12px;
        margin-bottom: 8px;
    }
    .brand-main-title {
        font-family: 'Noto Serif SC', serif;
        font-size: 26px;
        font-weight: 900;
        letter-spacing: 0.08em;
        background: linear-gradient(135deg, #FFFFFF 20%, #BAE6FD 60%, #38BDF8 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    .brand-sub {
        font-family: 'JetBrains Mono', monospace;
        font-size: 11px;
        font-weight: 700;
        color: #38BDF8;
        letter-spacing: 0.15em;
    }

    /* 指标卡加粗放大 (告别眯眼) */
    div[data-testid="stMetric"] {
        background: rgba(14, 20, 32, 0.85) !important;
        border: 1px solid rgba(255, 255, 255, 0.12) !important;
        border-radius: 8px !important;
        padding: 10px 14px !important;
        box-shadow: 0 4px 12px rgba(0,0,0,0.3) !important;
    }
    div[data-testid="stMetricValue"] {
        font-family: 'JetBrains Mono', monospace !important;
        font-size: 22px !important;
        font-weight: 800 !important;
        color: #FFFFFF !important;
    }
    div[data-testid="stMetricLabel"] {
        font-size: 13px !important;
        font-weight: 700 !important;
        color: #94A3B8 !important;
    }

    /* Tab 标签页放大美化 */
    .stTabs [data-baseweb="tab-list"] {
        gap: 10px !important;
        border-bottom: 2px solid #1E293B !important;
        padding-bottom: 6px !important;
    }
    .stTabs [data-baseweb="tab"] {
        font-size: 15px !important;
        font-weight: 700 !important;
        color: #94A3B8 !important;
        border-radius: 6px 6px 0 0 !important;
        padding: 8px 20px !important;
    }
    .stTabs [aria-selected="true"] {
        background-color: rgba(2, 132, 199, 0.2) !important;
        color: #38BDF8 !important;
        border-bottom: 3px solid #38BDF8 !important;
    }

    /* 操作按钮放大 */
    .stButton>button {
        font-size: 14px !important;
        font-weight: 700 !important;
        border-radius: 6px !important;
        padding: 8px 16px !important;
        background: #0F172A !important;
        color: #F8FAFC !important;
        border: 1px solid #334155 !important;
        transition: all 0.2s ease !important;
    }
    .stButton>button:hover {
        border-color: #38BDF8 !important;
        color: #38BDF8 !important;
        box-shadow: 0 0 12px rgba(56, 189, 248, 0.25) !important;
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

# 顶部【癸水】品牌与状态栏
st.markdown("""
<div class="brand-title-box">
    <div>
        <div class="brand-main-title">癸 水 · 量化战略座舱</div>
        <div class="brand-sub">GUI SHUI QUANT TERMINAL</div>
    </div>
</div>
""", unsafe_allow_html=True)

s1, s2, s3, s4 = st.columns(4)
s1.metric("🕒 大马时间 (MYT)", now_myt.strftime("%H:%M:%S"), now_myt.strftime("%Y-%m-%d"))
s2.metric("🇺🇸 美东时间 (ET)", now_ny.strftime("%H:%M:%S"), "盘中纪律" if has_10pm_p else "日间备战")
s3.metric("🚦 战区引擎状态", "✅ 22:00-24:00 已就绪" if has_10pm_p else "⏳ 等待 22:00 定调", "0.5 ATR / 1:2 TP")
s4.metric("📋 昨夜战报交付", "✅ 已核验存档" if has_8am_report else "⏳ 待更新", f"{yesterday_myt_str}")

st.markdown("---")

# 4. 原生 3 个核心 Tab 完整回归
tab_macro, tab_cockpit, tab_journal = st.tabs([
    "📡 宏观雷达 (13 标的事实穿透与持仓罗盘)",
    "🎯 战区座舱 (实时/历史 13 行富途代码)",
    "📅 QQQ 2B 同频月历与深度复盘全景"
])

# ================= TAB 1: 宏观雷达 =================
with tab_macro:
    render_macro_radar_tab()

# ================= TAB 2: 战区座舱 =================
with tab_cockpit:
    st.subheader("🎯 QQQ 5M 战区座舱 (富途牛牛 13 行代码)")
    
    df_journal_all = load_journal()
    recorded_dates = sorted(list(set(df_journal_all["Date_MYT"].dropna().astype(str).values)), reverse=True) if not df_journal_all.empty else []
    mode_options = ["🔴 实时 / 当前最新战区"] + ([f"📅 历史战区: {d}" for d in recorded_dates] if recorded_dates else [])
    sel_mode = st.selectbox("请选择战区版本（支持白天调阅过去 13 行参数）:", options=mode_options, key="tab1_mode_picker")

    p_to_display = None
    display_title = ""

    if sel_mode.startswith("📅 历史战区:"):
        target_hist_date = sel_mode.replace("📅 历史战区: ", "").strip()
        hist_row = df_journal_all[df_journal_all["Date_MYT"].astype(str) == target_hist_date].iloc[0]
        
        p_to_display = {
            "live_price": float(hist_row.get("Entry_Price", hist_row.get("PDH", 0.0))),
            "TREND_BIAS": int(hist_row.get("TREND_BIAS", 0)),
            "BIAS_DESC": "🟢 绿灯 (做多为主)" if hist_row.get("TREND_BIAS", 0) == 1 else ("🔴 红灯 (做空为主)" if hist_row.get("TREND_BIAS", 0) == -1 else "🟡 黄灯 (震荡防守)"),
            "EMA20_1H": float(hist_row.get("EMA20_1H", 0.0)),
            "ATR_1H": float(hist_row.get("ATR_1H", 0.0)),
            "SBR_TOP": float(hist_row.get("SBR_TOP", 0.0)), "SBR_BOT": float(hist_row.get("SBR_BOT", 0.0)), "SBR_TIME": f"{target_hist_date} 战区",
            "RBS_TOP": float(hist_row.get("RBS_TOP", 0.0)), "RBS_BOT": float(hist_row.get("RBS_BOT", 0.0)), "RBS_TIME": f"{target_hist_date} 战区",
            "SBR2_TOP": float(hist_row.get("SBR2_TOP", 0.0)), "SBR2_BOT": float(hist_row.get("SBR2_BOT", 0.0)), "SBR2_TIME": "Tier-2 High",
            "RBS2_TOP": float(hist_row.get("RBS2_TOP", 0.0)), "RBS2_BOT": float(hist_row.get("RBS2_BOT", 0.0)), "RBS2_TIME": "Tier-2 Low",
            "PDH": float(hist_row.get("PDH", 0.0)), "PDH_TIME": "PDH",
            "PDL": float(hist_row.get("PDL", 0.0)), "PDL_TIME": "PDL",
            "PMH": float(hist_row.get("PMH", 0.0)), "PMH_TIME": "PMH",
            "PML": float(hist_row.get("PML", 0.0)), "PML_TIME": "PML"
        }
        display_title = f"📋 历史存档 [{target_hist_date}] 13 行富途代码 (可直接复制):"
    else:
        if not has_10pm_p:
            st.info("🔒 当前处于日间准备期（夜间 22:00 解锁实时更新）。下方已自动切换为最近一次历史交易日的 13 行参数。")
            if recorded_dates:
                latest_d = recorded_dates[0]
                hist_row = df_journal_all[df_journal_all["Date_MYT"].astype(str) == latest_d].iloc[0]
                p_to_display = {
                    "live_price": float(hist_row.get("PDH", 0.0)),
                    "TREND_BIAS": int(hist_row.get("TREND_BIAS", 0)),
                    "BIAS_DESC": "🟢 绿灯 (做多为主)" if hist_row.get("TREND_BIAS", 0) == 1 else ("🔴 红灯 (做空为主)" if hist_row.get("TREND_BIAS", 0) == -1 else "🟡 黄灯 (震荡防守)"),
                    "EMA20_1H": float(hist_row.get("EMA20_1H", 0.0)),
                    "ATR_1H": float(hist_row.get("ATR_1H", 0.0)),
                    "SBR_TOP": float(hist_row.get("SBR_TOP", 0.0)), "SBR_BOT": float(hist_row.get("SBR_BOT", 0.0)), "SBR_TIME": f"{latest_d} 战区",
                    "RBS_TOP": float(hist_row.get("RBS_TOP", 0.0)), "RBS_BOT": float(hist_row.get("RBS_BOT", 0.0)), "RBS_TIME": f"{latest_d} 战区",
                    "SBR2_TOP": float(hist_row.get("SBR2_TOP", 0.0)), "SBR2_BOT": float(hist_row.get("SBR2_BOT", 0.0)), "SBR2_TIME": "Tier-2 High",
                    "RBS2_TOP": float(hist_row.get("RBS2_TOP", 0.0)), "RBS2_BOT": float(hist_row.get("RBS2_BOT", 0.0)), "RBS2_TIME": "Tier-2 Low",
                    "PDH": float(hist_row.get("PDH", 0.0)), "PDH_TIME": "PDH",
                    "PDL": float(hist_row.get("PDL", 0.0)), "PDL_TIME": "PDL",
                    "PMH": float(hist_row.get("PMH", 0.0)), "PMH_TIME": "PMH",
                    "PML": float(hist_row.get("PML", 0.0)), "PML_TIME": "PML"
                }
                display_title = f"📋 最近交易日 [{latest_d}] 13 行富途代码 (可直接复制):"
        else:
            if st.button("🔄 刷新最新点位"): 
                st.cache_data.clear()
                st.rerun()
            d1h, d5m, _ = fetch_raw_data_with_retry(period_5m="5d")
            if d1h is not None:
                p_to_display = compute_futu_13_params(d1h, d5m, now_ny)
                display_title = "📋 今晚实时 13 行富途代码 (点击右上角复制):"

    if p_to_display:
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("🎯 现价 / 锚点", f"${p_to_display['live_price']:.2f}")
        m2.metric("🚦 三灯信号定调", p_to_display["BIAS_DESC"])
        m3.metric("📈 1H EMA20 均线", f"${p_to_display['EMA20_1H']:.2f}")
        m4.metric("📊 1H ATR 波动", f"${p_to_display['ATR_1H']:.2f}")

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

# ================= TAB 3: 月历账本与全量深度复盘 =================
with tab_journal:
    st.subheader("📅 QQQ 2B 同频月历账本与多维复盘 (22:00 - 24:00 MYT)")
    
    # 模块 A: 昨夜战况极速核验
    with st.expander(f"⚡ 展开查看【昨夜 ({yesterday_myt_str}) 22:00-24:00 战况极速核验】", expanded=True):
        col_y_btn, _ = st.columns([1.5, 3])
        with col_y_btn:
            if st.button("🔄 重新核验昨夜信号", key="btn_refresh_yest_box"):
                st.cache_data.clear()
                st.rerun()
        
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
                    st.dataframe(pd.DataFrame(trades_y)[[c for c in pd.DataFrame(trades_y).columns if not c.endswith("_DT_NY")]], use_container_width=True, hide_index=True)
                else:
                    yc4.metric("🎯 昨夜战果", "⚪ 严格空仓", "未触发开仓形态")
                    st.info("昨夜价格未触及战区准入条件，或未出现 1.25 倍放量 2B/吞没反转，严格执行空仓纪律。")
            else:
                st.warning("昨夜战区参数正在同步中...")
        else:
            st.warning("行情接口连接中，请稍候点击刷新。")

    st.markdown("---")

    # 模块 B: 月历年月选择与四大指标卡
    c_y, c_m, c_exp = st.columns([1, 1, 2])
    with c_y:
        sel_y = st.selectbox("年份选择", [2026, 2025, 2024], index=0, key="sel_y_picker")
    with c_m:
        sel_m = st.selectbox("月份选择", list(range(1, 13)), index=now_myt.month - 1, key="sel_m_picker")

    col_btn1, col_btn2, col_btn3 = st.columns([1.5, 2, 1.5])
    with col_btn1:
        if st.button("🛠️ 结算昨夜 22:00-24:00 账本", key="btn_settle_yest_journal"):
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
                    if ok:
                        st.success(f"🎉 {target_d} 结算完成！")
                        st.rerun()
                    else:
                        st.warning(msg)

    with col_btn2:
        if st.button(f"⚡ 一键回溯/刷新 {sel_y}年{sel_m}月 历史账本", key="btn_backfill_monthly_journal"):
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
        if st.button("🗑️ 清空历史账本重新生成", key="btn_clear_journal_file"):
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

    # 模块 C: 月历大网格与查图
    cal = calendar.monthcalendar(sel_y, sel_m)
    cols_header = st.columns(7)
    days_name = ["周一 (Mon)", "周二 (Tue)", "周三 (Wed)", "周四 (Thu)", "周五 (Fri)", "周六 (Sat)", "周日 (Sun)"]
    for idx, d_name in enumerate(days_name):
        cols_header[idx].markdown(f"<div style='text-align:center; font-weight:700; color:#94A3B8; font-size:13px;'>{d_name}</div>", unsafe_allow_html=True)

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

    for week in cal:
        w_cols = st.columns(7)
        for d_idx, day_num in enumerate(week):
            with w_cols[d_idx]:
                if day_num == 0:
                    st.markdown("<div style='height:115px;'></div>", unsafe_allow_html=True)
                elif d_idx in [5, 6]:
                    st.markdown(f"<div style='border:1px dashed #334155; border-radius:6px; padding:6px; height:115px; background-color:#0B0F19; text-align:center;'><span style='color:#64748B; font-size:12px; font-weight:700;'>{day_num}</span><br><span style='color:#475569; font-size:12px;'>💤 休市</span></div>", unsafe_allow_html=True)
                else:
                    if day_num in day_records:
                        rec = day_records[day_num]
                        pnl = float(rec["PnL_Points"])
                        bias_v = rec["TREND_BIAS"]
                        bias_tag = "多" if bias_v > 0 else ("空" if bias_v < 0 else "震荡")
                        this_date_str = str(rec["Date_MYT"])
                        
                        if rec["Signal"] == "NO_TRADE":
                            st.markdown(f"<div style='border:1px solid #334155; border-radius:6px; padding:6px; height:75px; background-color:#0F172A;'><span style='color:#94A3B8; font-size:12px; font-weight:700;'>{day_num} ({bias_tag})</span><br><span style='color:#64748B; font-size:12px;'>⚪ 纪律空仓</span></div>", unsafe_allow_html=True)
                        else:
                            bg_c = "#064E3B" if pnl > 0 else "#7F1D1D"
                            st.markdown(f"<div style='border:1px solid #10B981; border-radius:6px; padding:6px; height:75px; background-color:{bg_c};'><span style='color:#E2E8F0; font-size:12px; font-weight:700;'>{day_num} ({bias_tag})</span><br><span style='color:#FFFFFF; font-size:14px; font-weight:800;'>{pnl:+.2f} pt</span></div>", unsafe_allow_html=True)
                        
                        is_cur = (st.session_state["active_chart_date"] == this_date_str)
                        btn_txt = "👉 正在看" if is_cur else "🔍 查图"
                        if st.button(btn_txt, key=f"btn_cal_day_{this_date_str}"):
                            st.session_state["active_chart_date"] = this_date_str
                            st.rerun()
                    else:
                        st.markdown(f"<div style='border:1px dashed #1E293B; border-radius:6px; padding:6px; height:115px; text-align:center;'><span style='color:#475569; font-size:12px;'>{day_num}</span><br><span style='color:#334155; font-size:11px;'>-</span></div>", unsafe_allow_html=True)

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
            st.dataframe(df_month[valid_show_cols].sort_values(by="Date_MYT", ascending=False), use_container_width=True, hide_index=True)
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
                if st.button(label, key=f"chip_jump_{r_date}"):
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
