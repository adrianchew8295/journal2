# 文件名：app.py
# 作用：極簡雙標籤 QQQ 戰區座艙（去冗餘、秒響應、深色自適應）
# 文件名：app.py
# 作用：極簡雙標籤 QQQ 戰區座艙（徹底修復月份切換、100% 綁定選定月份與 Bias=0 鎖死）
import datetime
from datetime import timedelta
import calendar
import os
import pytz
import numpy as np
import pandas as pd
import streamlit as st

from data_fetcher import fetch_raw_data_with_retry
from futu_engine import compute_futu_13_params, simulate_trades_with_2b
from journal_manager import load_journal, append_to_journal

st.set_page_config(page_title="QQQ 2B与战区同频座舱", layout="wide", page_icon="🎯")

tz_myt = pytz.timezone("Asia/Kuala_Lumpur")
tz_ny = pytz.timezone("America/New_York")
now_myt = datetime.datetime.now(tz_myt)
now_ny = datetime.datetime.now(tz_ny)

st.title("🎯 QQQ 战区与 2B 同频座舱")

tab1, tab2 = st.tabs(["🎯 战区座舱 (13行富途代码)", "📅 同频月历与深度复盘"])

with tab1:
    st.info("💡 每天大马时间 22:00（冬令时 23:00）自动锁定 1H 战区并生成富途 13 行参数。")

with tab2:
    st.subheader("📅 QQQ 2B 同频月历账本 (22:00 - 24:00 MYT)")
    
    # 1. 顶部年月选择器 (放在最上方，确保按钮与视图严格共享选择的年月)
    c_y, c_m, c_exp = st.columns([1, 1, 2])
    with c_y:
        sel_y = st.selectbox("年份选择", [2026, 2025, 2024], index=0, key="sel_y_picker")
    with c_m:
        # 默认选中当前月，但只要切换月份，全页面立刻切换
        sel_m = st.selectbox("月份选择", list(range(1, 13)), index=now_myt.month - 1, key="sel_m_picker")

    st.markdown("---")

    col_btn1, col_btn2, col_btn3 = st.columns([1.5, 2, 1.5])
    
    with col_btn1:
        if st.button("🛠️ 结算昨夜 22:00-24:00 账本"):
            with st.spinner("正在结算昨夜交易..."):
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
        # 严格回溯当前选中的 sel_y 与 sel_m
        if st.button(f"⚡ 一键回溯/刷新 {sel_y}年{sel_m}月 历史账本"):
            with st.spinner(f"正在重新回溯计算 {sel_y} 年 {sel_m} 月数据..."):
                d1h, d5m, _ = fetch_raw_data_with_retry(period_5m="1mo")
                if d1h is not None and d5m is not None:
                    dates_in_5m = sorted(list(set(d5m.index.date)))
                    # 仅筛选出属于当前选定年月的交易日
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
                    
                    st.success(f"🎉 {sel_y}年{sel_m}月 回溯完成，共生成 {added_cnt} 个交易日记录！")
                    st.rerun()

    with col_btn3:
        if st.button("🗑️ 清空历史账本重新生成"):
            if os.path.exists("monthly_trade_records.csv"):
                os.remove("monthly_trade_records.csv")
                st.success("账本已清空！")
                st.rerun()

    st.markdown("---")

    # 2. 读取数据并严格按照 sel_y 与 sel_m 进行过滤
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

    # 3. 四大统计卡片严格显示选中的年月
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("🗓️ 统计月份", f"{sel_y} 年 {sel_m} 月")
    k2.metric("💰 窗口净盈亏", f"{net_pnl:+.2f} pt", f"{'正向收益' if net_pnl >= 0 else '回撤亏损'}")
    k3.metric("🎯 实操胜率", f"{win_rate:.1f}%", f"↑ {win_trades} 胜 / {total_trades} 战")
    k4.metric("📊 总出手次数", f"{total_trades} 笔", f"↑ 空仓 {empty_days} 天")

    st.markdown("---")

    # 4. 根据用户选中的 sel_y, sel_m 绘制当月的真实日历网格
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
                            st.markdown(f"<div style='border:1px solid #2d3748; border-radius:6px; padding:6px; height:95px; background-color:#1a202c;'><span style='color:#a0aec0; font-size:11px;'>{day_num} ({bias_tag})</span><br><br><span style='color:#e2e8f0; font-size:12px;'>⚪ 未达门槛</span><br><span style='color:#718096; font-size:10px;'>纪律空仓</span></div>", unsafe_allow_html=True)
                        else:
                            bg_c = "#064e3b" if pnl > 0 else "#7f1d1d"
                            st.markdown(f"<div style='border:1px solid #48bb78; border-radius:6px; padding:6px; height:95px; background-color:{bg_c};'><span style='color:#e2e8f0; font-size:11px;'>{day_num} ({bias_tag})</span><br><span style='color:#fff; font-size:13px; font-weight:bold;'>{pnl:+.2f} pt</span><br><span style='color:#cbd5e0; font-size:10px;'>1 笔交易</span></div>", unsafe_allow_html=True)
                    else:
                        st.markdown(f"<div style='border:1px dashed #2d3748; border-radius:6px; padding:8px; height:95px; text-align:center;'><span style='color:#4a5568; font-size:12px;'>{day_num}</span><br><span style='color:#4a5568; font-size:11px;'>-</span></div>", unsafe_allow_html=True)
