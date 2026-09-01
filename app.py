# 文件名: app.py
# 作用: QQQ 战区座舱主控台 (Tab 1 宏观雷达 + Tab 2 富途13行参数 + Tab 3 月历账本与复盘)

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

st.set_page_config(page_title="QQQ 2B与战区同频座舱", layout="wide", page_icon="🎯")

tz_myt = pytz.timezone("Asia/Kuala_Lumpur")
tz_ny = pytz.timezone("America/New_York")
now_myt = datetime.datetime.now(tz_myt)
now_ny = datetime.datetime.now(tz_ny)

df_j = load_journal()
yesterday_d = now_myt.date() - timedelta(days=1)
yesterday_myt_str = yesterday_d.strftime("%Y-%m-%d")
has_10pm_p = (now_myt.hour >= 22 or now_myt.hour < 5)
has_8am_report = yesterday_myt_str in df_j["Date_MYT"].astype(str).values if not df_j.empty else False

st.title("🎯 QQQ 战区与 2B 同频座舱")

# 顶部状态导航
s1, s2, s3, s4 = st.columns(4)
s1.success("✅ 10:00 PM 战区引擎就绪" if has_10pm_p else "⏳ 10:00 PM 战区等待中")
s2.success(f"✅ 昨夜战报已交付 ({yesterday_myt_str})" if has_8am_report else f"⏳ 昨夜战报待更新 ({yesterday_myt_str})")
s3.info("🎯 纪律窗口：22:00 - 24:00 (MYT) | 1:2 TP / 结构止损")

with s4:
    if st.button("🧪 全链路自检"):
        with st.spinner("正在检测行情接口..."):
            d1, d5, errs = fetch_raw_data_with_retry(period_5m="5d")
            if errs: st.error("异常: " + "; ".join(errs))
            else: st.success("自检通过：接口正常。")

st.markdown("---")

# 3 个清晰的核心 Tab
tab_macro, tab_cockpit, tab_journal = st.tabs([
    "📡 宏观雷达 (13 标的事实穿透)",
    "🎯 战区座舱 (13 行富途代码)",
    "📅 QQQ 2B 同频月历与深度复盘"
])

# ================= TAB 1: 宏观雷达 =================
with tab_macro:
    render_macro_radar_tab()

# ================= TAB 2: 战区座舱 =================
with tab_cockpit:
    st.subheader("🎯 QQQ 5M 战区座舱 (含 SBR/SBR2/RBS/RBS2 & 2B)")
    c_t1, c_t2 = st.columns(2)
    c_t1.info("🕒 大马时间 (MYT): " + now_myt.strftime("%Y-%m-%d %H:%M:%S"))
    c_t2.info("🇺🇸 美东时间 (ET): " + now_ny.strftime("%Y-%m-%d %H:%M:%S"))

    if not has_10pm_p:
        st.warning("🔒 处于日间准备期。大马时间 22:00 准时解锁并生成今晚 13 行战区代码。")
    else:
        if st.button("🔄 刷新最新点位", key="btn_refresh_cockpit_points"):
            st.cache_data.clear()
            st.rerun()
        d1h, d5m, _ = fetch_raw_data_with_retry(period_5m="5d")
        if d1h is not None:
            p = compute_futu_13_params(d1h, d5m, now_ny)
            if p:
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("🎯 QQQ 现价", f"${p['live_price']:.2f}")
                m2.metric("🚦 三灯信号定调", p["BIAS_DESC"])
                m3.metric("📈 1H EMA20 均线", f"${p['EMA20_1H']:.2f}")
                m4.metric("📊 1H ATR 波动", f"${p['ATR_1H']:.2f}")

                out_lines = [
                    f"TREND_BIAS := {p['TREND_BIAS']};       {{ 1. QQQ三灯判定: 1=绿灯做多, -1=红灯做空, 0=黄灯防守 }}",
                    "",
                    "{ --- 第一梯队主战区 (PRIMARY ZONES) --- }",
                    f"SBR_TOP := {round(p['SBR_TOP'], 2)}; {{ 2. PRIMARY 1H 阻力顶沿 [{p['SBR_TIME']}] }}",
                    f"SBR_BOT := {round(p['SBR_BOT'], 2)}; {{ 3. PRIMARY 1H 阻力底沿 [{p['SBR_TIME']}] }}",
                    f"RBS_TOP := {round(p['RBS_TOP'], 2)}; {{ 4. PRIMARY 1H 支撑顶沿 [{p['RBS_TIME']}] }}",
                    f"RBS_BOT := {round(p['RBS_BOT'], 2)}; {{ 5. PRIMARY 1H 支撑底沿 [{p['RBS_TIME']}] }}",
                    "",
                    "{ --- 第二梯队拓展战区 (SECONDARY ZONES) --- }",
                    f"SBR2_TOP := {round(p['SBR2_TOP'], 2)}; {{ 6. SECONDARY 1H 更高阻力顶沿 [{p['SBR2_TIME']}] }}",
                    f"SBR2_BOT := {round(p['SBR2_BOT'], 2)}; {{ 7. SECONDARY 1H 更高阻力底沿 [{p['SBR2_TIME']}] }}",
                    f"RBS2_TOP := {round(p['RBS2_TOP'], 2)}; {{ 8. SECONDARY 1H 更低支撑顶沿 [{p['RBS2_TIME']}] }}",
                    f"RBS2_BOT := {round(p['RBS2_BOT'], 2)}; {{ 9. SECONDARY 1H 更低支撑底沿 [{p['RBS2_TIME']}] }}",
                    "",
                    "{ --- 全市场客观极值 (SWEEP ANCHORS) --- }",
                    f"PDH_LINE := {round(p['PDH'], 2)}; {{ 10. 昨日最高价 PDH [{p['PDH_TIME']}] }}",
                    f"PDL_LINE := {round(p['PDL'], 2)}; {{ 11. 昨日最低价 PDL [{p['PDL_TIME']}] }}",
                    f"PMH_LINE := {round(p['PMH'], 2)}; {{ 12. 盘前最高价 PMH [{p['PMH_TIME']}] }}",
                    f"PML_LINE := {round(p['PML'], 2)}; {{ 13. 盘前最低价 PML [{p['PML_TIME']}] }}"
                ]
                st.markdown("#### 📋 复制到富途指标顶部 13 行代码 (点击右上角复制):")
                st.code("\n".join(out_lines), language="pascal")

# ================= TAB 3: 月历账本与深度复盘 =================
with tab_journal:
    st.subheader("📅 QQQ 2B 同频月历账本与历史回放 (22:00 - 24:00 MYT)")
    
    c_y, c_m, c_exp = st.columns([1, 1, 2])
    with c_y:
        sel_y = st.selectbox("年份选择", [2026, 2025, 2024], index=0, key="sel_y_picker")
    with c_m:
        sel_m = st.selectbox("月份选择", list(range(1, 13)), index=now_myt.month - 1, key="sel_m_picker")

    st.markdown("---")

    col_btn1, col_btn2, col_btn3 = st.columns([1.5, 2, 1.5])
    with col_btn1:
        if st.button("🛠️ 结算昨夜 22:00-24:00 账本"):
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
        if st.button(f"⚡ 一键回溯/刷新 {sel_y}年{sel_m}月 历史账本"):
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
        if st.button("🗑️ 清空历史账本"):
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
            st.download_button(f"📥 导出 {sel_y}年{sel_m}月 账本 (.csv)", csv_data, f"journal_{sel_y}_{sel_m:02d}.csv", "text/csv")

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("🗓️ 统计月份", f"{sel_y} 年 {sel_m} 月")
    k2.metric("💰 窗口净盈亏", f"{net_pnl:+.2f} pt", "正向收益" if net_pnl >= 0 else "回撤控制中")
    k3.metric("🎯 战区胜率", f"{win_rate:.1f}%", f"{win_trades} 胜 / {total_trades} 战")
    k4.metric("📊 交易笔数", f"{total_trades} 笔", f"空仓 {empty_days} 天")

    st.markdown("---")

    cal = calendar.monthcalendar(sel_y, sel_m)
    cols_header = st.columns(7)
    days_name = ["周一 (Mon)", "周二 (Tue)", "周三 (Wed)", "周四 (Thu)", "周五 (Fri)", "周六 (Sat)", "周日 (Sun)"]
    for idx, d_name in enumerate(days_name):
        cols_header[idx].markdown(f"**{d_name}**")

    day_records = {}
    if not df_month.empty:
        for _, row in df_month.iterrows():
            d_num = pd.to_datetime(row["Date_MYT"]).day
            day_records[d_num] = row

    for week in cal:
        w_cols = st.columns(7)
        for d_idx, day_num in enumerate(week):
            with w_cols[d_idx]:
                if day_num == 0:
                    st.markdown("<div style='height:95px;'></div>", unsafe_allow_html=True)
                elif d_idx in [5, 6]:
                    st.markdown(f"<div style='border:1px solid #2d3748; border-radius:6px; padding:8px; height:95px; background-color:#141824; text-align:center;'><span style='color:#718096; font-size:12px;'>{day_num}</span><br><span style='color:#4a5568; font-size:12px;'>💤<br>周末休市</span></div>", unsafe_allow_html=True)
                else:
                    if day_num in day_records:
                        rec = day_records[day_num]
                        pnl = float(rec["PnL_Points"])
                        bias_v = rec["TREND_BIAS"]
                        bias_tag = "多" if bias_v > 0 else ("空" if bias_v < 0 else "震荡")
                        
                        if rec["Signal"] == "NO_TRADE":
                            st.markdown(f"<div style='border:1px solid #2d3748; border-radius:6px; padding:6px; height:95px; background-color:#1a202c;'><span style='color:#a0aec0; font-size:11px;'>{day_num} ({bias_tag})</span><br><br><span style='color:#e2e8f0; font-size:12px;'>⚪ 门槛未达</span><br><span style='color:#718096; font-size:10px;'>纪律空仓</span></div>", unsafe_allow_html=True)
                        else:
                            bg_c = "#064e3b" if pnl > 0 else "#7f1d1d"
                            st.markdown(f"<div style='border:1px solid #48bb78; border-radius:6px; padding:6px; height:95px; background-color:{bg_c};'><span style='color:#e2e8f0; font-size:11px;'>{day_num} ({bias_tag})</span><br><span style='color:#fff; font-size:13px; font-weight:bold;'>{pnl:+.2f} pt</span><br><span style='color:#cbd5e0; font-size:10px;'>1 笔交易</span></div>", unsafe_allow_html=True)
                    else:
                        st.markdown(f"<div style='border:1px dashed #2d3748; border-radius:6px; padding:8px; height:95px; text-align:center;'><span style='color:#4a5568; font-size:12px;'>{day_num}</span><br><span style='color:#4a5568; font-size:11px;'>-</span></div>", unsafe_allow_html=True)

    st.markdown("---")
    st.subheader("🔍 历史单日 5M 走势与量能图表回放")
    if not df_month.empty:
        recorded_dates = sorted(list(set(df_month["Date_MYT"].astype(str).values)), reverse=True)
        sel_hist_date_str = st.selectbox("选择要复盘的交易日", options=recorded_dates, key="hist_chart_picker")
        
        if st.button("🎬 载入选定日期走势与量能图"):
            with st.spinner("正在加载历史数据并绘制双层画布..."):
                d1h_hist, d5m_hist, _ = fetch_raw_data_with_retry(period_5m="1mo")
                if d1h_hist is not None and d5m_hist is not None:
                    target_hist_d = datetime.datetime.strptime(sel_hist_date_str, "%Y-%m-%d").date()
                    dt_hist_10pm_myt = tz_myt.localize(datetime.datetime.combine(target_hist_d, datetime.time(22, 0, 0)))
                    cutoff_hist_ny = dt_hist_10pm_myt.astimezone(tz_ny)
                    window_hist_end_ny = cutoff_hist_ny + timedelta(hours=2)
                    
                    p_hist = compute_futu_13_params(d1h_hist, d5m_hist, cutoff_hist_ny)
                    trades_hist, day_5m_hist = simulate_trades_with_2b(d5m_hist, p_hist, cutoff_hist_ny, window_hist_end_ny)
                    
                    render_dual_chart(
                        day_5m_hist, p_hist, trades_hist, dt_hist_10pm_myt,
                        title_text=f"历史回放 ({sel_hist_date_str}) | 5M 战场执行与 VPA 量能异动"
                    )
