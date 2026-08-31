# 文件名：app.py
# 作用：極簡雙標籤 QQQ 戰區座艙（去冗餘、秒響應、深色自適應）
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

st.set_page_config(
    page_title="QQQ 2B與戰區同頻座艙",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# 注入自定義現代暗黑質感 CSS
st.markdown("""
<style>
    .main { background-color: #0e1117; }
    .stMetric {
        background-color: #161b22;
        padding: 12px 16px;
        border-radius: 10px;
        border: 1px solid #30363d;
    }
    div[data-testid="stMetricValue"] { font-size: 1.5rem !important; }
    .stButton>button {
        width: 100%;
        border-radius: 8px;
        font-weight: bold;
        transition: all 0.2s;
    }
    .stButton>button:hover {
        border-color: #00e676;
        color: #00e676;
    }
</style>
""", unsafe_allow_html=True)

tz_myt = pytz.timezone("Asia/Kuala_Lumpur")
tz_ny = pytz.timezone("America/New_York")

now_myt = datetime.datetime.now(tz_myt)
now_ny = datetime.datetime.now(tz_ny)

df_j = load_journal()
yesterday_d = now_myt.date() - timedelta(days=1)
yesterday_myt_str = yesterday_d.strftime("%Y-%m-%d")
has_10pm_p = (now_myt.hour >= 22 or now_myt.hour < 5)
has_8am_report = yesterday_myt_str in df_j["Date_MYT"].astype(str).values if not df_j.empty else False

# 頂部狀態導航
st.title("🎯 QQQ 戰區與 2B 同頻座艙")
c1, c2, c3, c4 = st.columns(4)
c1.metric("🕒 大馬時間 (MYT)", now_myt.strftime("%H:%M:%S"), yesterday_myt_str)
c2.metric("🇺🇸 美東時間 (ET)", now_ny.strftime("%H:%M:%S"), "盤中紀律" if has_10pm_p else "日間備戰")
c3.metric("🚦 戰區引擎狀態", "✅ 已就緒" if has_10pm_p else "⏳ 等待 22:00", "22:00 - 24:00 窗口")
c4.metric("📋 昨夜戰報交付", "✅ 已存檔" if has_8am_report else "⏳ 待更新", f"{yesterday_myt_str}")

st.markdown("---")
tab1, tab2 = st.tabs(["🎯 戰區座艙 (13行富途代碼)", "📅 同頻月曆與深度復盤"])

with tab1:
    st.subheader("🎯 實時 13 行戰區參數 (一鍵複製至富途)")
    if not has_10pm_p:
        st.info("🔒 當前處於日間準備期。大馬時間 22:00 準時自動鎖定今晚戰區點位。")
    
    col_t1_left, col_t1_right = st.columns([1, 2])
    with col_t1_left:
        if st.button("🔄 立即刷新最新點位"):
            st.cache_data.clear()
            st.rerun()
            
    d1h, d5m, _ = fetch_raw_data_with_retry(period_5m="5d")
    if d1h is not None:
        p = compute_futu_13_params(d1h, d5m, now_ny)
        if p:
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("🎯 QQQ 實時現價", f"${p['live_price']:.2f}")
            m2.metric("🚦 三燈定調", p["BIAS_DESC"])
            m3.metric("📈 1H EMA20", f"${p['EMA20_1H']:.2f}")
            m4.metric("📊 1H ATR", f"${p['ATR_1H']:.2f}")

            out_lines = [
                f"TREND_BIAS := {p['TREND_BIAS']};       {{ 1. 三燈判定: 1=多, -1=空, 0=防守 }}",
                "",
                "{ --- 第一梯隊主戰區 --- }",
                f"SBR_TOP := {round(p['SBR_TOP'], 2)}; {{ 2. 阻力頂沿 [{p['SBR_TIME']}] }}",
                f"SBR_BOT := {round(p['SBR_BOT'], 2)}; {{ 3. 阻力底沿 [{p['SBR_TIME']}] }}",
                f"RBS_TOP := {round(p['RBS_TOP'], 2)}; {{ 4. 支撐頂沿 [{p['RBS_TIME']}] }}",
                f"RBS_BOT := {round(p['RBS_BOT'], 2)}; {{ 5. 支撐底沿 [{p['RBS_TIME']}] }}",
                "",
                "{ --- 第二梯隊拓展戰區 --- }",
                f"SBR2_TOP := {round(p['SBR2_TOP'], 2)}; {{ 6. 更高阻力頂沿 [{p['SBR2_TIME']}] }}",
                f"SBR2_BOT := {round(p['SBR2_BOT'], 2)}; {{ 7. 更高阻力底沿 [{p['SBR2_TIME']}] }}",
                f"RBS2_TOP := {round(p['RBS2_TOP'], 2)}; {{ 8. 更低支撐頂沿 [{p['RBS2_TIME']}] }}",
                f"RBS2_BOT := {round(p['RBS2_BOT'], 2)}; {{ 9. 更低支撐底沿 [{p['RBS2_TIME']}] }}",
                "",
                "{ --- 全市場極值錨點 --- }",
                f"PDH_LINE := {round(p['PDH'], 2)}; {{ 10. 昨日最高 PDH [{p['PDH_TIME']}] }}",
                f"PDL_LINE := {round(p['PDL'], 2)}; {{ 11. 昨日最低 PDL [{p['PDL_TIME']}] }}",
                f"PMH_LINE := {round(p['PMH'], 2)}; {{ 12. 盤前最高 PMH [{p['PMH_TIME']}] }}",
                f"PML_LINE := {round(p['PML'], 2)}; {{ 13. 盤前最低 PML [{p['PML_TIME']}] }}"
            ]
            st.markdown("#### 📋 點擊右上角一鍵複製代碼塊:")
            st.code("\n".join(out_lines), language="pascal")

with tab2:
    st.subheader("📅 QQQ 2B 同频月历账本 (22:00 - 24:00 MYT)")
    col_btn1, col_btn2, col_btn3 = st.columns([1.5, 2, 1.5])
    
    with col_btn1:
        # 12点（24:00）一过即可立刻结算昨夜
        if st.button("🛠️ 结算昨夜 22:00-24:00 账本"):
            with st.spinner("正在结算昨夜交易..."):
                d1h, d5m, _ = fetch_raw_data_with_retry(period_5m="5d")
                # 如果当前时间是午夜 00:00 之后，结算的就是昨天晚上的 22:00-24:00
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
        # 一键强制全量重算当月，自动覆盖旧记录
        if st.button("⚡ 一键回溯/刷新当月所有交易日 (Force Backfill)"):
            with st.spinner("正在用最新严格风控规则重新回溯整月..."):
                d1h, d5m, _ = fetch_raw_data_with_retry(period_5m="1mo")
                if d1h is not None and d5m is not None:
                    # 重新计算前先清空旧账本，彻底消除旧数据
                    if os.path.exists(CSV_FILE):
                        os.remove(CSV_FILE)
                    
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
                    
                    st.success(f"🎉 整月回溯与数据刷新完成，共重新生成 {added_cnt} 个交易日！")
                    st.rerun()

    with col_btn3:
        if st.button("🗑️ 清空历史账本重新生成"):
            if os.path.exists(CSV_FILE):
                os.remove(CSV_FILE)
                st.success("账本已清空！")
                st.rerun()
    df_journal = load_journal()
    if not df_journal.empty and "Date_MYT" in df_journal.columns:
        df_journal["Date_MYT_dt"] = pd.to_datetime(df_journal["Date_MYT"]).dt.date
        df_journal["Year"] = pd.to_datetime(df_journal["Date_MYT"]).dt.year
        df_journal["Month"] = pd.to_datetime(df_journal["Date_MYT"]).dt.month
    else:
        df_journal["Year"], df_journal["Month"], df_journal["Date_MYT_dt"] = [], [], []

    cy, cm, cdl = st.columns([1, 1, 2])
    with cy: sel_y = st.selectbox("年份選擇", options=[2025, 2026, 2027], index=1)
    with cm: sel_m = st.selectbox("月份選擇", options=list(range(1, 13)), index=now_myt.month - 1)

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
            data=csv_bytes, file_name=f"Futu_Journal_{sel_y}_{str(sel_m).zfill(2)}.csv", mime="text/csv", disabled=df_m.empty
        )

    # 戰績儀表欄
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("🗓️ 統計月份", f"{sel_y} 年 {sel_m} 月")
    k2.metric("💰 窗口淨盈虧", f"{tot_pts:+.2f} pt", "正向收益" if tot_pts >= 0 else "回撤控制中")
    k3.metric("🎯 實操勝率", f"{w_rate:.1f}%", f"{w_cnt} 勝 / {tot_cnt} 戰")
    k4.metric("📊 總出手次數", f"{tot_cnt} 筆", f"空倉 {len(df_m) - tot_cnt} 天")

    st.markdown("---")
    weekdays = ["周一 (Mon)", "周二 (Tue)", "周三 (Wed)", "周四 (Thu)", "周五 (Fri)", "周六 (Sat)", "周日 (Sun)"]
    h_cols = st.columns(7)
    for idx, hc in enumerate(h_cols):
        hc.markdown(f"<div style='text-align:center; font-weight:bold; color:#8b949e;'>{weekdays[idx]}</div>", unsafe_allow_html=True)

    cal = calendar.monthcalendar(sel_y, sel_m)
    for week in cal:
        w_cols = st.columns(7)
        for d_idx, day in enumerate(week):
            with w_cols[d_idx]:
                if day == 0:
                    st.markdown("<div style='height:115px;'></div>", unsafe_allow_html=True)
                    continue
                cur_d = datetime.date(sel_y, sel_m, day)
                is_weekend = (d_idx >= 5)
                if is_weekend:
                    st.markdown(f"<div style='background-color:#161b22; border-radius:8px; padding:8px; height:115px; border:1px dashed #30363d; text-align:center;'><div style='font-size:13px; color:#484f58; text-align:left;'><b>{day}</b></div><div style='font-size:16px; margin-top:10px;'>💤</div><div style='font-size:11px; color:#484f58;'>周末休市</div></div>", unsafe_allow_html=True)
                else:
                    d_recs = df_m[df_m["Date_MYT_dt"] == cur_d] if not df_m.empty else pd.DataFrame()
                    if not d_recs.empty:
                        r_t = d_recs[d_recs["Signal"] != "NO_TRADE"]
                        cnt = len(r_t)
                        pts = r_t["PnL_Points"].sum() if not r_t.empty else 0.0
                        b_val = d_recs.iloc[0].get("TREND_BIAS", 0)
                        b_str = "多" if b_val == 1 else ("空" if b_val == -1 else "震盪")
                        if cnt == 0:
                            st.markdown(f"<div style='background-color:#161b22; border-radius:8px; padding:8px; height:115px; border:1px solid #30363d; text-align:center;'><div style='font-size:13px; color:#8b949e; text-align:left;'><b>{day}</b> <span style='font-size:10px; color:#58a6ff;'>({b_str})</span></div><div style='font-size:12px; color:#8b949e; margin-top:15px;'>⚪ 未達門檻</div><div style='font-size:10px; color:#484f58;'>紀律空倉</div></div>", unsafe_allow_html=True)
                        else:
                            bg = "#0d281e" if pts >= 0 else "#2d1517"
                            bd = "#00e676" if pts >= 0 else "#ff5252"
                            tc = "#00e676" if pts >= 0 else "#ff5252"
                            sgn = "+" if pts > 0 else ""
                            st.markdown(f"<div style='background-color:{bg}; border-radius:8px; padding:8px; height:115px; border:2px solid {bd}; text-align:center;'><div style='font-size:13px; color:#c9d1d9; text-align:left;'><b>{day}</b> <span style='font-size:10px; color:{bd};'>({b_str})</span></div><div style='font-size:15px; font-weight:bold; color:{tc}; margin-top:2px;'>{sgn}{pts:.2f} pt</div><div style='font-size:11px; color:#8b949e;'>{cnt} 筆交易</div></div>", unsafe_allow_html=True)
                    else:
                        st.markdown(f"<div style='background-color:#0d1117; border-radius:8px; padding:8px; height:115px; border:1px solid #21262d; text-align:center;'><div style='font-size:13px; color:#30363d; text-align:left;'><b>{day}</b></div><div style='font-size:11px; color:#30363d; margin-top:25px;'>-</div></div>", unsafe_allow_html=True)

    with st.expander("🔍 展開查看完整明細表 (Full Data Table)"):
        if not df_m.empty: st.dataframe(df_m.drop(columns=["Date_MYT_dt", "Year", "Month"], errors="ignore"), use_container_width=True)
        else: st.info("當月暫無交易明細。")

    st.markdown("---")
    st.subheader("🔍 歷史單日雙層圖表深度復盤")
    if not df_m.empty:
        recorded_dates = sorted(list(set(df_m["Date_MYT"].astype(str).values)), reverse=True)
        sel_c1, sel_c2 = st.columns([3, 1])
        with sel_c1:
            sel_hist_date_str = st.selectbox("選擇要復盤的歷史交易日 (含昨夜)", options=recorded_dates)
        with sel_c2:
            st.write("")
            st.write("")
            btn_play = st.button("🎬 載入當日走勢")
            
        if btn_play or sel_hist_date_str:
            with st.spinner(f"正在載入 {sel_hist_date_str} 的全量數據..."):
                d1h_hist, d5m_hist, _ = fetch_raw_data_with_retry(period_5m="1mo")
                if d1h_hist is not None and d5m_hist is not None:
                    target_hist_d = datetime.datetime.strptime(sel_hist_date_str, "%Y-%m-%d").date()
                    dt_hist_10pm_myt = tz_myt.localize(datetime.datetime.combine(target_hist_d, datetime.time(22, 0, 0)))
                    cutoff_hist_ny = dt_hist_10pm_myt.astimezone(tz_ny)
                    window_hist_end_ny = cutoff_hist_ny + timedelta(hours=2)
                    
                    p_hist = compute_futu_13_params(d1h_hist, d5m_hist, cutoff_hist_ny)
                    trades_hist, day_5m_hist = simulate_trades_with_2b(d5m_hist, p_hist, cutoff_hist_ny, window_hist_end_ny)
                    
                    # 顯示當日戰果摘要小卡片
                    if trades_hist:
                        t = trades_hist[0]
                        st.success(f"🎯 當日戰果：{t['Result']} ({t['PnL_Points']:+.2f} pt) | 觸發信號：{t['Signal']} | 出場原因：{t['Reason']}")
                    else:
                        st.info("⚪ 當日戰果：未觸發入場門檻，嚴格按紀律空倉休戰。")

                    render_dual_chart(
                        day_5m_hist, p_hist, trades_hist, dt_hist_10pm_myt,
                        title_text=f"歷史復盤 ({sel_hist_date_str}) | 5M 走勢與副圖 VPA 量能"
                    )
