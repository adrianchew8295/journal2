# 文件名: app.py
# 作用: 旗舰级 QQQ 战区座舱 (Tab 1 宏观雷达与持仓输入罗盘 + Tab 2 富途13行参数 + Tab 3 同频月历与深度复盘)

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

# 顶部系统状态栏
s1, s2, s3, s4 = st.columns(4)
s1.success("✅ 10:00 PM 战区引擎已就绪" if has_10pm_p else "⏳ 10:00 PM 战区引擎等待中")
s2.success(f"✅ 昨夜战报已交付 ({yesterday_myt_str})" if has_8am_report else f"⏳ 昨夜战报待更新 ({yesterday_myt_str})")
s3.info("🎯 纪律窗口：22:00 - 24:00 (MYT) | 0.5 ATR 止损 / 1:2 TP")

with s4:
    if st.button("🧪 全链路接口自检"):
        with st.spinner("正在检测行情接口..."):
            d1, d5, errs = fetch_raw_data_with_retry(period_5m="5d")
            if errs: st.error("异常: " + "; ".join(errs))
            else: st.success("自检通过：接口正常。")

st.markdown("---")

# 3 个核心 Tab 分工
tab1, tab2, tab3 = st.tabs([
    "📋 Tab 1: 13 标的宏观雷达与实操持仓罗盘",
    "🎯 Tab 2: 战区座舱 (13行富途代码)",
    "📅 Tab 3: QQQ 2B 同频月历与深度复盘"
])

# ================= TAB 1: 宏观雷达与持仓管理 (已挂载输入框与形态学) =================
with tab1:
    render_macro_radar_tab()

# ================= TAB 2: 富途 13 行战区代码 =================
with tab2:
    st.subheader("🎯 QQQ 5M 战区座舱 (含 SBR/SBR2/RBS/RBS2 & 2B)")
    c_t1, c_t2 = st.columns(2)
    c_t1.info("🕒 大马时间 (MYT): " + now_myt.strftime("%Y-%m-%d %H:%M:%S"))
    c_t2.info("🇺🇸 美东时间 (ET): " + now_ny.strftime("%Y-%m-%d %H:%M:%S"))

    if st.button("🔄 随时拉取/计算当前最新战区代码", key="btn_refresh_cockpit_points"):
        st.cache_data.clear()
        st.rerun()

    if not has_10pm_p:
        st.info("💡 提示：当前处于日间/盘前预览模式。下方数据为基于当前最新行情的即时战区；22:00 将作为后台基准。")
    else:
        st.success("✅ 22:00 战区引擎已正式就绪。")

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
with tab3:
    st.subheader("📅 QQQ 2B 同频月历账本与深度复盘 (22:00 - 24:00 MYT)")
    
    # 昨夜战况核验
    with st.expander(f"⚡ 展开查看【昨夜 ({yesterday_myt_str}) 22:00-24:00 战况极速核验】", expanded=True):
        col_y_btn, col_y_txt = st.columns([1.5, 3])
        with col_y_btn:
            if st.button("🔄 刷新昨夜信号核验", key="btn_refresh_yest_box"):
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

    # 年月选择与账本管理
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

    # 月历渲染
    cal = calendar.monthcalendar(sel_y, sel_m)
    cols_header = st.columns(7)
    days_name = ["周一 (Mon)", "周二 (Tue)", "周三 (Wed)", "周四 (Thu)", "周五 (Fri)", "周六 (Sat)", "周日 (Sun)"]
    for idx, d_name in enumerate(days_name):
        cols_header[idx].markdown(f"<div style='text-align:center; font-weight:bold; color:#a0aec0;'>{d_name}</div>", unsafe_allow_html=True)

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
                    st.markdown(f"<div style='border:1px dashed #2d3748; border-radius:6px; padding:6px; height:115px; background-color:#141824; text-align:center;'><span style='color:#718096; font-size:11px;'>{day_num}</span><br><span style='color:#4a5568; font-size:11px;'>💤 休市</span></div>", unsafe_allow_html=True)
                else:
                    if day_num in day_records:
                        rec = day_records[day_num]
                        pnl = float(rec["PnL_Points"])
                        bias_v = rec["TREND_BIAS"]
                        bias_tag = "多" if bias_v > 0 else ("空" if bias_v < 0 else "震荡")
                        this_date_str = str(rec["Date_MYT"])
                        
                        if rec["Signal"] == "NO_TRADE":
                            st.markdown(f"<div style='border:1px solid #2d3748; border-radius:6px; padding:4px; height:70px; background-color:#1a202c;'><span style='color:#a0aec0; font-size:11px;'>{day_num} ({bias_tag})</span><br><span style='color:#718096; font-size:11px;'>⚪ 纪律空仓</span></div>", unsafe_allow_html=True)
                        else:
                            bg_c = "#064e3b" if pnl > 0 else "#7f1d1d"
                            st.markdown(f"<div style='border:1px solid #48bb78; border-radius:6px; padding:4px; height:70px; background-color:{bg_c};'><span style='color:#e2e8f0; font-size:11px;'>{day_num} ({bias_tag})</span><br><span style='color:#fff; font-size:12px; font-weight:bold;'>{pnl:+.2f} pt</span></div>", unsafe_allow_html=True)
                        
                        is_cur = (st.session_state["active_chart_date"] == this_date_str)
                        btn_txt = "👉 正在看" if is_cur else "🔍 查图"
                        if st.button(btn_txt, key=f"btn_cal_day_{this_date_str}"):
                            st.session_state["active_chart_date"] = this_date_str
                            st.rerun()
                    else:
                        st.markdown(f"<div style='border:1px dashed #2d3748; border-radius:6px; padding:6px; height:115px; text-align:center;'><span style='color:#4a5568; font-size:11px;'>{day_num}</span><br><span style='color:#4a5568; font-size:10px;'>-</span></div>", unsafe_allow_html=True)

    # 13 行全量战区参数历史明细表
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

    # 5M 走势与副图 VPA 量价异动双层图表
    st.markdown("---")
    active_date = st.session_state.get("active_chart_date")
    if active_date and not df_month.empty:
        st.subheader(f"📊 5M 走势与 VPA 量能回放：[{active_date}]")
        
        st.write("📌 **快速点击胶囊切换其他日期：**")
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
