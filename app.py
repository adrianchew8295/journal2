# 文件名：app.py
# 作用：完整版 QQQ 戰區座艙（Tab1 支持歷史 13 行參數查看與實時解鎖、Tab2 月曆歷史明細、Tab3 昨夜 5M/VPA 雙層圖）
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
from chart_renderer import render_dual_chart

st.set_page_config(page_title="QQQ 2B與戰區同頻座艙", layout="wide", page_icon="🎯")

tz_myt = pytz.timezone("Asia/Kuala_Lumpur")
tz_ny = pytz.timezone("America/New_York")
now_myt = datetime.datetime.now(tz_myt)
now_ny = datetime.datetime.now(tz_ny)

df_j = load_journal()
yesterday_d = now_myt.date() - timedelta(days=1)
yesterday_myt_str = yesterday_d.strftime("%Y-%m-%d")
has_10pm_p = (now_myt.hour >= 22 or now_myt.hour < 5)
has_8am_report = yesterday_myt_str in df_j["Date_MYT"].astype(str).values if not df_j.empty else False

st.title("🎯 QQQ 戰區與 2B 同頻座艙")

# 頂部狀態欄
s1, s2, s3, s4 = st.columns(4)
s1.success("✅ 10:00 PM 戰區引擎已就緒" if has_10pm_p else "⏳ 10:00 PM 戰區引擎等待中")
s2.success(f"✅ 昨夜戰報已交付 ({yesterday_myt_str})" if has_8am_report else f"⏳ 昨夜戰報待更新 ({yesterday_myt_str})")
s3.info("🎯 紀律窗口：22:00 - 24:00 (MYT) | 1:2 TP / 結構止損")

with s4:
    if st.button("🧪 執行系統全鏈路自檢"):
        with st.spinner("正在自檢..."):
            d1, d5, errs = fetch_raw_data_with_retry(period_5m="5d")
            if errs: st.error("異常: " + "; ".join(errs))
            else: st.success("自檢通過：行情接口正常。")

st.markdown("---")

tab1, tab2, tab3 = st.tabs([
    "🎯 戰區座艙 (13行富途代碼)", 
    "📅 QQQ 2B同頻月曆與歷史回放", 
    "⚡ 昨夜 22:00-24:00 信號核驗與 5M 戰場"
])

# ================= TAB 1: 戰區座艙 (支持查看過去 13 行參數) =================
with tab1:
    st.subheader("🎯 QQQ 5M 戰區座艙 (13 行富途代碼)")
    c_t1, c_t2 = st.columns(2)
    c_t1.info("🕒 大馬時間 (MYT): " + now_myt.strftime("%Y-%m-%d %H:%M:%S"))
    c_t2.info("🇺🇸 美東時間 (ET): " + now_ny.strftime("%Y-%m-%d %H:%M:%S"))

    df_journal_all = load_journal()
    recorded_dates = sorted(list(set(df_journal_all["Date_MYT"].dropna().astype(str).values)), reverse=True) if not df_journal_all.empty else []

    mode_options = ["🔴 實時/當前最新戰區"] + ([f"📅 歷史戰區: {d}" for d in recorded_dates] if recorded_dates else [])
    sel_mode = st.selectbox("請選擇要查看的戰區點位版本（支持查看歷史過去 13 行參數）:", options=mode_options, key="tab1_mode_picker")

    p_to_display = None
    display_title = ""

    if sel_mode.startswith("📅 歷史戰區:"):
        target_hist_date = sel_mode.replace("📅 歷史戰區: ", "").strip()
        hist_row = df_journal_all[df_journal_all["Date_MYT"].astype(str) == target_hist_date].iloc[0]
        
        p_to_display = {
            "live_price": float(hist_row.get("Entry_Price", hist_row.get("PDH", 0.0))),
            "TREND_BIAS": int(hist_row.get("TREND_BIAS", 0)),
            "BIAS_DESC": "🟢 綠燈 (做多為主)" if hist_row.get("TREND_BIAS", 0) == 1 else ("🔴 紅燈 (做空為主)" if hist_row.get("TREND_BIAS", 0) == -1 else "🟡 黃燈 (震盪防守)"),
            "EMA20_1H": float(hist_row.get("EMA20_1H", 0.0)),
            "ATR_1H": float(hist_row.get("ATR_1H", 0.0)),
            "SBR_TOP": float(hist_row.get("SBR_TOP", 0.0)), "SBR_BOT": float(hist_row.get("SBR_BOT", 0.0)), "SBR_TIME": f"{target_hist_date} 戰區",
            "RBS_TOP": float(hist_row.get("RBS_TOP", 0.0)), "RBS_BOT": float(hist_row.get("RBS_BOT", 0.0)), "RBS_TIME": f"{target_hist_date} 戰區",
            "SBR2_TOP": float(hist_row.get("SBR2_TOP", 0.0)), "SBR2_BOT": float(hist_row.get("SBR2_BOT", 0.0)), "SBR2_TIME": "Tier-2 High",
            "RBS2_TOP": float(hist_row.get("RBS2_TOP", 0.0)), "RBS2_BOT": float(hist_row.get("RBS2_BOT", 0.0)), "RBS2_TIME": "Tier-2 Low",
            "PDH": float(hist_row.get("PDH", 0.0)), "PDH_TIME": "PDH",
            "PDL": float(hist_row.get("PDL", 0.0)), "PDL_TIME": "PDL",
            "PMH": float(hist_row.get("PMH", 0.0)), "PMH_TIME": "PMH",
            "PML": float(hist_row.get("PML", 0.0)), "PML_TIME": "PML"
        }
        display_title = f"📋 歷史記錄 [{target_hist_date}] 13 行富途代碼 (可直接複製):"
    else:
        # 實時最新模式
        if not has_10pm_p:
            st.warning("🔒 當前處於日間準備期（夜間 22:00 解鎖實時更新）。下方已自動切換為最近一次歷史交易日的 13 行參數供您查看。")
            if recorded_dates:
                latest_d = recorded_dates[0]
                hist_row = df_journal_all[df_journal_all["Date_MYT"].astype(str) == latest_d].iloc[0]
                p_to_display = {
                    "live_price": float(hist_row.get("PDH", 0.0)),
                    "TREND_BIAS": int(hist_row.get("TREND_BIAS", 0)),
                    "BIAS_DESC": "🟢 綠燈 (做多為主)" if hist_row.get("TREND_BIAS", 0) == 1 else ("🔴 紅燈 (做空為主)" if hist_row.get("TREND_BIAS", 0) == -1 else "🟡 黃燈 (震盪防守)"),
                    "EMA20_1H": float(hist_row.get("EMA20_1H", 0.0)),
                    "ATR_1H": float(hist_row.get("ATR_1H", 0.0)),
                    "SBR_TOP": float(hist_row.get("SBR_TOP", 0.0)), "SBR_BOT": float(hist_row.get("SBR_BOT", 0.0)), "SBR_TIME": f"{latest_d} 戰區",
                    "RBS_TOP": float(hist_row.get("RBS_TOP", 0.0)), "RBS_BOT": float(hist_row.get("RBS_BOT", 0.0)), "RBS_TIME": f"{latest_d} 戰區",
                    "SBR2_TOP": float(hist_row.get("SBR2_TOP", 0.0)), "SBR2_BOT": float(hist_row.get("SBR2_BOT", 0.0)), "SBR2_TIME": "Tier-2 High",
                    "RBS2_TOP": float(hist_row.get("RBS2_TOP", 0.0)), "RBS2_BOT": float(hist_row.get("RBS2_BOT", 0.0)), "RBS2_TIME": "Tier-2 Low",
                    "PDH": float(hist_row.get("PDH", 0.0)), "PDH_TIME": "PDH",
                    "PDL": float(hist_row.get("PDL", 0.0)), "PDL_TIME": "PDL",
                    "PMH": float(hist_row.get("PMH", 0.0)), "PMH_TIME": "PMH",
                    "PML": float(hist_row.get("PML", 0.0)), "PML_TIME": "PML"
                }
                display_title = f"📋 最近交易日 [{latest_d}] 13 行富途代碼 (可直接複製):"
        else:
            if st.button("🔄 刷新最新點位"): 
                st.cache_data.clear()
                st.rerun()
            d1h, d5m, _ = fetch_raw_data_with_retry(period_5m="5d")
            if d1h is not None:
                p_to_display = compute_futu_13_params(d1h, d5m, now_ny)
                display_title = "📋 今晚實時 13 行富途代碼 (點右上角複製):"

    if p_to_display:
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("🎯 參考點位", f"${p_to_display['live_price']:.2f}")
        m2.metric("🚦 三燈判定", p_to_display["BIAS_DESC"])
        m3.metric("📈 1H EMA20 均線", f"${p_to_display['EMA20_1H']:.2f}")
        m4.metric("📊 1H ATR 波動", f"${p_to_display['ATR_1H']:.2f}")

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

# ================= TAB 2: 月曆賬本與歷史回放 =================
with tab2:
    st.subheader("📅 QQQ 2B 同頻月曆賬本 (22:00 - 24:00 MYT)")
    
    c_y, c_m, c_exp = st.columns([1, 1, 2])
    with c_y:
        sel_y = st.selectbox("年份選擇", [2026, 2025, 2024], index=0, key="sel_y_picker")
    with c_m:
        sel_m = st.selectbox("月份選擇", list(range(1, 13)), index=now_myt.month - 1, key="sel_m_picker")

    st.markdown("---")

    col_btn1, col_btn2, col_btn3 = st.columns([1.5, 2, 1.5])
    with col_btn1:
        if st.button("🛠️ 結算昨夜 22:00-24:00 賬本"):
            with st.spinner("正在結算昨夜交易..."):
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
                        st.success(f"🎉 {target_d} 結算完成！")
                        st.rerun()
                    else:
                        st.warning(msg)

    with col_btn2:
        if st.button(f"⚡ 一鍵回溯/刷新 {sel_y}年{sel_m}月 歷史賬本"):
            with st.spinner(f"正在回溯計算 {sel_y} 年 {sel_m} 月數據..."):
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
                    
                    st.success(f"🎉 {sel_y}年{sel_m}月 回溯完成，共生成 {added_cnt} 個交易日記錄！")
                    st.rerun()

    with col_btn3:
        if st.button("🗑️ 清空歷史賬本重新生成"):
            if os.path.exists("monthly_trade_records.csv"):
                os.remove("monthly_trade_records.csv")
                st.success("賬本已清空！")
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
            st.download_button(f"📥 導出 {sel_y}年{sel_m}月 完整賬本 (.csv)", csv_data, f"journal_{sel_y}_{sel_m:02d}.csv", "text/csv")

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("🗓️ 統計月份", f"{sel_y} 年 {sel_m} 月")
    k2.metric("💰 窗口淨盈虧", f"{net_pnl:+.2f} pt", f"{'正向收益' if net_pnl >= 0 else '回撤虧損'}")
    k3.metric("🎯 實操勝率", f"{win_rate:.1f}%", f"↑ {win_trades} 勝 / {total_trades} 戰")
    k4.metric("📊 總出手次數", f"{total_trades} 筆", f"↑ 空倉 {empty_days} 天")

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
                    st.markdown(f"<div style='border:1px solid #2d3748; border-radius:6px; padding:8px; height:95px; background-color:#141824; text-align:center;'><span style='color:#718096; font-size:12px;'>{day_num}</span><br><span style='color:#4a5568; font-size:12px;'>💤<br>週末休市</span></div>", unsafe_allow_html=True)
                else:
                    if day_num in day_records:
                        rec = day_records[day_num]
                        pnl = float(rec["PnL_Points"])
                        bias_v = rec["TREND_BIAS"]
                        bias_tag = "多" if bias_v > 0 else ("空" if bias_v < 0 else "震盪")
                        
                        if rec["Signal"] == "NO_TRADE":
                            st.markdown(f"<div style='border:1px solid #2d3748; border-radius:6px; padding:6px; height:95px; background-color:#1a202c;'><span style='color:#a0aec0; font-size:11px;'>{day_num} ({bias_tag})</span><br><br><span style='color:#e2e8f0; font-size:12px;'>⚪ 未達門檻</span><br><span style='color:#718096; font-size:10px;'>紀律空倉</span></div>", unsafe_allow_html=True)
                        else:
                            bg_c = "#064e3b" if pnl > 0 else "#7f1d1d"
                            st.markdown(f"<div style='border:1px solid #48bb78; border-radius:6px; padding:6px; height:95px; background-color:{bg_c};'><span style='color:#e2e8f0; font-size:11px;'>{day_num} ({bias_tag})</span><br><span style='color:#fff; font-size:13px; font-weight:bold;'>{pnl:+.2f} pt</span><br><span style='color:#cbd5e0; font-size:10px;'>1 筆交易</span></div>", unsafe_allow_html=True)
                    else:
                        st.markdown(f"<div style='border:1px dashed #2d3748; border-radius:6px; padding:8px; height:95px; text-align:center;'><span style='color:#4a5568; font-size:12px;'>{day_num}</span><br><span style='color:#4a5568; font-size:11px;'>-</span></div>", unsafe_allow_html=True)

    # 13 行戰區參數完整歷史明細表
    st.markdown("---")
    with st.expander("🔍 展開查看完整明細表 (Full Data Table - 含13行戰區參數與執行詳情)", expanded=False):
        if not df_month.empty:
            display_df = df_month.drop(columns=["DT_OBJ"], errors="ignore").sort_values(by="Date_MYT", ascending=False)
            st.dataframe(display_df, use_container_width=True)
        else:
            st.info(f"{sel_y} 年 {sel_m} 月暫無歷史賬本數據。")

    # 歷史單日 5M 圖表回放
    st.markdown("---")
    st.subheader("🔍 歷史單日 5M 戰場與 VPA 量能深度回放")
    if not df_month.empty:
        recorded_dates_tab2 = sorted(list(set(df_month["Date_MYT"].astype(str).values)), reverse=True)
        sel_hist_date_str = st.selectbox("請選擇要回放復盤的交易日", options=recorded_dates_tab2, key="hist_chart_picker")
        
        if st.button("🎬 開始回放選定日期走勢與量能圖"):
            with st.spinner("正在加載歷史數據並繪製雙層畫布..."):
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
                        title_text=f"歷史回放 ({sel_hist_date_str}) | 5M 戰場執行與 VPA 量能異動"
                    )

# ================= TAB 3: 昨夜戰場與雙層圖表 =================
with tab3:
    st.subheader(f"⚡ 昨夜 ({yesterday_myt_str}) 22:00 - 24:00 信號核驗與 5M 戰場")
    
    col_t3_btn, _ = st.columns([1.5, 3])
    with col_t3_btn:
        if st.button("🔄 重新核驗昨夜執行信號"):
            st.cache_data.clear()
            st.rerun()

    d1h, d5m, _ = fetch_raw_data_with_retry(period_5m="5d")
    
    if d1h is not None and d5m is not None:
        target_d = yesterday_d
        dt_10pm_myt = tz_myt.localize(datetime.datetime.combine(target_d, datetime.time(22, 0, 0)))
        cutoff_ny = dt_10pm_myt.astimezone(tz_ny)
        window_end_ny = cutoff_ny + timedelta(hours=2)
        
        p = compute_futu_13_params(d1h, d5m, cutoff_ny)
        if p:
            trades, day_5m = simulate_trades_with_2b(d5m, p, cutoff_ny, window_end_ny)
            
            tc1, tc2, tc3, tc4 = st.columns(4)
            tc1.metric("🚦 昨夜三燈方向", p["BIAS_DESC"])
            tc2.metric("📈 1H EMA20 戰區", f"${p['EMA20_1H']:.2f}")
            tc3.metric("📊 1H ATR 基準", f"${p['ATR_1H']:.2f}")
            
            if trades:
                t = trades[0]
                tc4.metric(
                    "🎯 昨夜戰果",
                    f"{t['Result']} ({t['PnL_Points']:+.2f} pt)",
                    f"信號: {t['Signal']}"
                )
            else:
                tc4.metric("🎯 昨夜戰果", "⚪ 未觸發信號", "空倉觀望")

            st.markdown("#### 📋 昨夜執行明細核驗 (結構止損 / 1:2 止盈)")
            if trades:
                t_df = pd.DataFrame(trades)
                show_cols = [c for c in t_df.columns if not c.endswith("_DT_NY")]
                st.table(t_df[show_cols])
            else:
                st.info("昨夜 22:00 - 24:00 (MYT) 價格未觸及戰區准入條件或未形成標準 2B / 吞沒形態，按紀律未開倉。")

            st.markdown("#### 📊 5M 戰場執行結構全景圖 (含 CALL / PUT / 2B 與 VPA 量能異動)")
            render_dual_chart(
                day_5m, p, trades, dt_10pm_myt,
                title_text="昨夜 5M 戰場回放 | 主圖買賣執行與副圖 VPA 量能異動"
            )
        else:
            st.error("計算昨夜 13 行戰區參數失敗，請檢查數據完整性。")
    else:
        st.warning("正在獲取數據，請稍後刷新。")
