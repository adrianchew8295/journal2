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
        if st.button("⚡ 一键回溯/刷新当月所有交易日 (Force Backfill)"):
            with st.spinner("正在用最新严格风控规则重新回溯整月..."):
                d1h, d5m, _ = fetch_raw_data_with_retry(period_5m="1mo")
                if d1h is not None and d5m is not None:
                    if os.path.exists("monthly_trade_records.csv"):
                        os.remove("monthly_trade_records.csv")
                    
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
                            ok, _ = append_to_journal(d.strftime("%Y-%m-%d"), p_day, trades_day, overwrite=True)
                            if ok: added_cnt += 1
                    
                    st.success(f"🎉 整月回溯完成，共重新生成 {added_cnt} 个交易日！")
                    st.rerun()

    with col_btn3:
        if st.button("🗑️ 清空历史账本重新生成"):
            if os.path.exists("monthly_trade_records.csv"):
                os.remove("monthly_trade_records.csv")
                st.success("账本已清空！")
                st.rerun()

    st.markdown("---")
    
    # 核心修复：选择年月
    c_y, c_m, c_exp = st.columns([1, 1, 2])
    with c_y:
        sel_y = st.selectbox("年份选择", [2026, 2025, 2024], index=0, key="sel_y_box")
    with c_m:
        sel_m = st.selectbox("月份选择", list(range(1, 13)), index=now_myt.month - 1, key="sel_m_box")

    df_journal = load_journal()

    # 核心修复：严格按选中的 sel_y 和 sel_m 过滤账本数据
    if not df_journal.empty and "Date_MYT" in df_journal.columns:
        df_journal["DT_OBJ"] = pd.to_datetime(df_journal["Date_MYT"])
        df_month = df_journal[(df_journal["DT_OBJ"].dt.year == sel_y) & (df_journal["DT_OBJ"].dt.month == sel_m)].copy()
    else:
        df_month = pd.DataFrame()

    # 统计卡片指标
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

    # 4 大战绩卡片动态绑定选中的年月
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("🗓️ 统计月份", f"{sel_y} 年 {sel_m} 月")
    k2.metric("💰 窗口净盈亏", f"{net_pnl:+.2f} pt", f"{'正向收益' if net_pnl >= 0 else '回撤亏损'}")
    k3.metric("🎯 实操胜率", f"{win_rate:.1f}%", f"↑ {win_trades} 胜 / {total_trades} 战")
    k4.metric("📊 总出手次数", f"{total_trades} 笔", f"↑ 空仓 {empty_days} 天")

    st.markdown("---")

    # 动态渲染选定月份的月历
    cal = calendar.monthcalendar(sel_y, sel_m)
    cols_header = st.columns(7)
    days_name = ["周一 (Mon)", "周二 (Tue)", "周三 (Wed)", "周四 (Thu)", "周五 (Fri)", "周六 (Sat)", "周日 (Sun)"]
    for idx, d_name in enumerate(days_name):
        cols_header[idx].markdown(f"**{d_name}**")

    # 交易记录映射字典
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
