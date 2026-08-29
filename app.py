# 文件名：app.py
# 作用：精簡瘦身版主界面調度文件
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
from journal_manager import CSV_FILE, append_to_journal, load_journal

st.set_page_config(page_title="QQQ 2B與戰區同頻座艙", page_icon="🎯", layout="wide")

tz_myt = pytz.timezone("Asia/Kuala_Lumpur")
tz_ny = pytz.timezone("America/New_York")

now_myt = datetime.datetime.now(tz_myt)
now_ny = datetime.datetime.now(tz_ny)

df_j = load_journal()
yesterday_d = now_myt.date() - timedelta(days=1)
yesterday_myt_str = yesterday_d.strftime("%Y-%m-%d")
has_10pm_p = (now_myt.hour >= 22 or now_myt.hour < 5)
has_8am_report = yesterday_myt_str in df_j["Date_MYT"].astype(str).values if not df_j.empty else False

# 頂部狀態欄
s1, s2, s3, s4 = st.columns(4)
s1.success("✅ 10:00 PM 戰區引擎已就緒" if has_10pm_p else "⏳ 10:00 PM 戰區引擎等待中")
s2.success(f"✅ 戰報已交付 ({yesterday_myt_str})" if has_8am_report else f"⏳ 戰報待更新 ({yesterday_myt_str})")
s3.info("🎯 紀律窗口：22:00 - 24:00 (MYT) | 結構止損 / 1:2 TP")

with s4:
    if st.button("🧪 執行系統全鏈路測試"):
        with st.spinner("正在自檢..."):
            d1, d5, errs = fetch_raw_data_with_retry(period_5m="5d")
            if errs: st.error("異常: " + "; ".join(errs))
            else: st.success("自檢通過：接口正常。")

st.markdown("---")
tab1, tab2, tab3 = st.tabs(["🎯 QQQ 戰區座艙 (13行富途參數複製)", "📅 QQQ 2B同頻月曆賬本", "⚡ 昨夜 22:00-24:00 信號核驗與 5M 戰場"])

with tab1:
    st.subheader("🎯 QQQ 5M 戰區座艙 (含 SBR/SBR2/RBS/RBS2 & 2B)")
    c_t1, c_t2 = st.columns(2)
    c_t1.info("🕒 大馬時間 (MYT): " + now_myt.strftime("%Y-%m-%d %H:%M:%S"))
    c_t2.info("🇺🇸 美東時間 (ET): " + now_ny.strftime("%Y-%m-%d %H:%M:%S"))

    if not has_10pm_p:
        st.warning("🔒 處於日間準備期。大馬時間 22:00 準時解鎖並生成今晚 13 行戰區代碼。")
    else:
        if st.button("🔄 刷新最新點位"): st.cache_data.clear(); st.rerun()
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

with tab2:
    st.subheader("📅 QQQ 2B 同頻月曆賬本 (22:00 - 24:00 MYT)")
    col_btn1, col_btn2, col_btn3 = st.columns([1.5, 2, 1.5])
    with col_btn1:
        if st.button("🛠️ 結算昨夜 22:00-24:00 賬本"):
            with st.spinner("正在結算..."):
                d1h, d5m, _ = fetch_raw_data_with_retry(period_5m="5d")
                target_d = now_myt.date() - timedelta(days=1)
                dt_10pm_myt = tz_myt.localize(datetime.datetime.combine(target_d, datetime.time(22, 0, 0)))
                cutoff_ny = dt_10pm_myt.astimezone(tz_ny)
                window_end_ny = cutoff_ny + timedelta(hours=2)
                p = compute_futu_13_params(d1h, d5m, cutoff_ny)
                if p:
                    trades, _ = simulate_trades_with_2b(d5m, p, cutoff_ny, window_end_ny)
                    ok, msg = append_to_journal(target_d.strftime("%Y-%m-%d"), p, trades)
                    if ok: st.success(msg); st.rerun()
                    else: st.warning(msg)
    with col_btn2:
        if st.button("⚡ 一鍵回溯補錄當月所有歷史交易日 (Backfill)"):
            with st.spinner("正在回溯運算..."):
                d1h, d5m, _ = fetch_raw_data_with_retry(period_5m="1mo")
                if d1h is not None and d5m is not None:
                    dates_in_5m = sorted(list(set(d5m.index.date)))
                    added_cnt = 0
                    for d in dates_in_5m:
                        if d >= now_ny.date(): continue
                        dt_10pm_myt = tz_myt.localize(datetime.datetime.combine(d, datetime.time(22, 0, 0)))
                        cutoff_ny = dt_10pm_myt.astimezone(tz_ny)
                        window_end_ny = cutoff_ny + timedelta(hours=2)
                        p_day = compute_futu_13_params(d1h, d5m, cutoff_ny)
                        if p_day:
                            trades_day, _ = simulate_trades_with_2b(d5m, p_day, cutoff_ny, window_end_ny)
                            ok, _ = append_to_journal(d.strftime("%Y-%m-%d"), p_day, trades_day)
                            if ok: added_cnt += 1
                    st.success(f"🎉 回溯完成，新增 {added_cnt} 個交易日記錄！")
                    st.rerun()
    with col_btn3:
        if st.button("🗑️ 清空歷史賬本重新生成"):
            if os.path.exists(CSV_FILE): os.remove(CSV_FILE); st.success("賬本已重置！"); st.rerun()

    df_journal = load_journal()
    if not df_journal.empty and "Date_MYT" in df_journal.columns:
        df_journal["Date_MYT_dt"] = pd.to_datetime(df_journal["Date_MYT"]).dt.date
        df_journal["Year"] = pd.to_datetime(df_journal["Date_MYT"]).dt.year
        df_journal["Month"] = pd.to_datetime(df_journal["Date_MYT"]).dt.month
    else:
        df_journal["Year"], df_journal["Month"], df_journal["Date_MYT_dt"] = [], [], []

    cy, cm, cdl = st.columns([1.5, 1.5, 2])
    with cy: sel_y = st.selectbox("年份", options=[2025, 2026, 2027], index=1)
    with cm: sel_m = st.selectbox("月份", options=list(range(1, 13)), index=now_myt.month - 1)

    df_m = df_journal[(df_journal["Year"] == sel_y) & (df_journal["Month"] == sel_m)] if not df_journal.empty else pd.DataFrame()
    valid_t = df_m[df_m["Signal"] != "NO_TRADE"] if not df_m.empty else pd.DataFrame()
    tot_pts = valid_t["PnL_Points"].sum() if not valid_t.empty else 0.0
    tot_cnt = len(valid_t)
    w_cnt = len(valid_t[valid_t["PnL_Points"] > 0]) if not valid_t.empty else 0
    w_rate = (w_cnt / tot_cnt * 100) if tot_cnt > 0 else 0.0

    with cdl:
        csv_bytes = df_m.to_csv(index=False).encode("utf-8-sig") if not df_m.empty else "".encode("utf-8-sig")
        st.download_button(
            label=f"📥 導出 {sel_y}年{sel_m}月 完整賬本 (.csv)",
            data=csv_bytes, file_name=f"Futu_Full_Journal_{sel_y}_{str(sel_m).zfill(2)}.csv", mime="text/csv", disabled=df_m.empty
        )

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("🗓️ 選定月份", f"{sel_y} 年 {sel_m} 月")
    k2.metric("💰 窗口盈虧", f"{tot_pts:+.2f} pt")
    k3.metric("🎯 窗口勝率", f"{w_rate:.1f}%", f"{w_cnt}/{tot_cnt} 勝")
    k4.metric("📊 開倉總筆數", f"{tot_cnt} 筆")

    st.markdown("---")
    weekdays = ["周一 (Mon)", "周二 (Tue)", "周三 (Wed)", "周四 (Thu)", "周五 (Fri)", "周六 (Sat)", "周日 (Sun)"]
    h_cols = st.columns(7)
    for idx, hc in enumerate(h_cols): hc.markdown(f"<div style='text-align:center; font-weight:bold; color:#4a5568;'>{weekdays[idx]}</div>", unsafe_allow_html=True)

    cal = calendar.monthcalendar(sel_y, sel_m)
    for week in cal:
        w_cols = st.columns(7)
        for d_idx, day in enumerate(week):
            with w_cols[d_idx]:
                if day == 0: st.markdown("<div style='height:120px;'></div>", unsafe_allow_html=True); continue
                cur_d = datetime.date(sel_y, sel_m, day)
                is_weekend = (d_idx >= 5)
                if is_weekend:
                    st.markdown(f"<div style='background-color:#edf2f7; border-radius:8px; padding:8px; height:120px; border:1px dashed #cbd5e0; text-align:center;'><div style='font-size:13px; color:#a0aec0; text-align:left;'><b>{day}</b></div><div style='font-size:18px; margin-top:10px;'>❌</div><div style='font-size:11px; color:#a0aec0;'>週末休市</div></div>", unsafe_allow_html=True)
                else:
                    d_recs = df_m[df_m["Date_MYT_dt"] == cur_d] if not df_m.empty else pd.DataFrame()
                    if not d_recs.empty:
                        r_t = d_recs[d_recs["Signal"] != "NO_TRADE"]
                        cnt = len(r_t); pts = r_t["PnL_Points"].sum() if not r_t.empty else 0.0
                        b_val = d_recs.iloc[0].get("TREND_BIAS", 0)
                        b_str = "多" if b_val == 1 else ("空" if b_val == -1 else "黃燈")
                        if cnt == 0:
                            st.markdown(f"<div style='background-color:#f7fafc; border-radius:8px; padding:8px; height:120px; border:1px solid #e2e8f0; text-align:center;'><div style='font-size:13px; color:#718096; text-align:left;'><b>{day}</b> <span style='font-size:10px; color:#a0aec0;'>({b_str})</span></div><div style='font-size:12px; color:#718096; margin-top:15px;'>⚪ 未觸及戰區</div><div style='font-size:10px; color:#a0aec0;'>空倉休戰</div></div>", unsafe_allow_html=True)
                        else:
                            bg = "#e6fffa" if pts >= 0 else "#fff5f5"
                            bd = "#38b2ac" if pts >= 0 else "#e53e3e"
                            tc = "#234e52" if pts >= 0 else "#742a2a"
                            sgn = "+" if pts > 0 else ""
                            st.markdown(f"<div style='background-color:{bg}; border-radius:8px; padding:8px; height:120px; border:2px solid {bd}; text-align:center;'><div style='font-size:13px; color:{tc}; text-align:left;'><b>{day}</b> <span style='font-size:10px; color:{bd};'>({b_str})</span></div><div style='font-size:15px; font-weight:bold; color:{bd}; margin-top:2px;'>{sgn}{pts:.2f} pt</div><div style='font-size:11px; color:{tc};'>{cnt} 筆交易 (22-24點)</div></div>", unsafe_allow_html=True)
                    else:
                        st.markdown(f"<div style='background-color:#ffffff; border-radius:8px; padding:8px; height:120px; border:1px solid #edf2f7; text-align:center;'><div style='font-size:13px; color:#cbd5e0; text-align:left;'><b>{day}</b></div><div style='font-size:11px; color:#cbd5e0; margin-top:25px;'>-</div></div>", unsafe_allow_html=True)

    with st.expander("🔍 展開查看完整明細表 (Full Data Table)"):
        if not df_m.empty: st.dataframe(df_m.drop(columns=["Date_MYT_dt", "Year", "Month"], errors="ignore"), use_container_width=True)
        else: st.info("當月暫無交易明細。")

    st.markdown("---")
    st.subheader("🔍 歷史單日 5M 戰場與 VPA 量能深度回放")
    if not df_m.empty:
        recorded_dates = sorted(list(set(df_m["Date_MYT"].astype(str).values)), reverse=True)
        sel_hist_date_str = st.selectbox("請選擇要回放復盤的交易日", options=recorded_dates)
        
        if st.button("🎬 開始回放選定日期走勢"):
            with st.spinner("正在加載歷史數據並繪製圖表..."):
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
