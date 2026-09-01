# 文件名：app.py
# 作用：完整版 QQQ 戰區座艙（含宏觀雷達波形圖、富途13行代碼、月曆賬本與歷史回放）
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
from macro_radar_plugin import render_macro_radar_tab

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

# 4 個獨立清晰的 Tab
tab_macro, tab1, tab2, tab3 = st.tabs([
    "📡 宏觀雷達 (13核心波形圖)",
    "🎯 戰區座艙 (13行富途代碼)", 
    "📅 QQQ 2B同頻月曆與歷史回放", 
    "⚡ 昨夜 22:00-24:00 信號核驗與 5M 戰場"
])

# ================= TAB 0: 宏觀雷達 =================
with tab_macro:
    render_macro_radar_tab()

# ================= TAB 1: 戰區座艙 =================
with tab1:
    st.subheader("🎯 QQQ 5M 戰區座艙 (含 SBR/SBR2/RBS/RBS2 & 2B)")
    c_t1, c_t2 = st.columns(2)
    c_t1.info("🕒 大馬時間 (MYT): " + now_myt.strftime("%Y-%m-%d %H:%M:%S"))
    c_t2.info("🇺🇸 美東時間 (ET): " + now_ny.strftime("%Y-%m-%d %H:%M:%S"))

    if not has_10pm_p:
        st.warning("🔒 處於日間準備期。大馬時間 22:00 準時解鎖並生成今晚 13 行戰區代碼。")
    else:
        if st.button("🔄 刷新最新點位"): 
            st.cache_data.clear()
            st.rerun()
        d1h, d5m, _ = fetch_raw_data_with_retry(period_5m="5d")
        if d1h is not None:
            p = compute_futu_13_params(d1h, d5m, now_ny)
            if p:
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("🎯 QQQ 現價", f"${p['live_price']:.2f}")
                m2.metric("🚦 三燈信號定調", p["BIAS_DESC"])
                m3.metric("📈 1H EMA20 均線", f"${p['EMA20_1H']:.2f}")
                m4.metric("📊 1H ATR 波動", f"${p['ATR_1H']:.2f}")

                out_lines = [
                    f"TREND_BIAS := {p['TREND_BIAS']};       {{ 1. QQQ三燈判定: 1=綠燈做多, -1=紅燈做空, 0=黃燈防守 }}",
                    "",
                    "{ --- 第一梯隊主戰區 (PRIMARY ZONES) --- }",
                    f"SBR_TOP := {round(p['SBR_TOP'], 2)}; {{ 2. PRIMARY 1H 阻力頂沿 [{p['SBR_TIME']}] }}",
                    f"SBR_BOT := {round(p['SBR_BOT'], 2)}; {{ 3. PRIMARY 1H 阻力底沿 [{p['SBR_TIME']}] }}",
                    f"RBS_TOP := {round(p['RBS_TOP'], 2)}; {{ 4. PRIMARY 1H 支撐頂沿 [{p['RBS_TIME']}] }}",
                    f"RBS_BOT := {round(p['RBS_BOT'], 2)}; {{ 5. PRIMARY 1H 支撐底沿 [{p['RBS_TIME']}] }}",
                    "",
                    "{ --- 第二梯隊拓展戰區 (SECONDARY ZONES) --- }",
                    f"SBR2_TOP := {round(p['SBR2_TOP'], 2)}; {{ 6. SECONDARY 1H 更高阻力頂沿 [{p['SBR2_TIME']}] }}",
                    f"SBR2_BOT := {round(p['SBR2_BOT'], 2)}; {{ 7. SECONDARY 1H 更高阻力底沿 [{p['SBR2_TIME']}] }}",
                    f"RBS2_TOP := {round(p['RBS2_TOP'], 2)}; {{ 8. SECONDARY 1H 更低支撐頂沿 [{p['RBS2_TIME']}] }}",
                    f"RBS2_BOT := {round(p['RBS2_BOT'], 2)}; {{ 9. SECONDARY 1H 更低支撐底沿 [{p['RBS2_TIME']}] }}",
                    "",
                    "{ --- 全市場客觀極值 (SWEEP ANCHORS) --- }",
                    f"PDH_LINE := {round(p['PDH'], 2)}; {{ 10. 昨日最高價 PDH [{p['PDH_TIME']}] }}",
                    f"PDL_LINE := {round(p['PDL'], 2)}; {{ 11. 昨日最低價 PDL [{p['PDL_TIME']}] }}",
                    f"PMH_LINE := {round(p['PMH'], 2)}; {{ 12. 盤前最高價 PMH [{p['PMH_TIME']}] }}",
                    f"PML_LINE := {round(p['PML'], 2)}; {{ 13. 盤前最低價 PML [{p['PML_TIME']}] }}"
                ]
                st.markdown("#### 📋 複製到富途指標頂部 13 行代碼 (點右上角複製):")
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

    st.markdown("---")
    with st.expander("🔍 展開查看完整明細表 (Full Data Table - 含13行戰區參數與執行詳情)", expanded=False):
        if not df_month.empty:
            display_df = df_month.drop(columns=["DT_OBJ"], errors="ignore").sort_values(by="Date_MYT", ascending=False)
            st.dataframe(display_df, use_container_width=True)
        else:
            st.info(f"{sel_y} 年 {sel_m} 月暫無歷史賬本數據。")

    st.markdown("---")
    st.subheader("🔍 歷史單日 5M 戰場與 VPA 量能深度回放")
    if not df_month.empty:
        recorded_dates = sorted(list(set(df_month["Date_MYT"].astype(str).values)), reverse=True)
        sel_hist_date_str = st.selectbox("請選擇要回放復盤的交易日", options=recorded_dates, key="hist_chart_picker")
        
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