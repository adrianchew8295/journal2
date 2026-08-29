# 文件 5：app.py
# 作用：主界面調度與視覺化看盤座艙
import calendar
import datetime
from datetime import timedelta
import os
import pandas as pd
import plotly.graph_objects as go
import pytz
import streamlit as st

from data_fetcher import fetch_raw_data_with_retry
from futu_engine import compute_futu_13_params, simulate_trades_with_2b
from journal_manager import CSV_FILE, append_to_journal, load_journal

st.set_page_config(page_title="QQQ 2B与战区同频座舱", page_icon="🎯", layout="wide")

tz_myt = pytz.timezone("Asia/Kuala_Lumpur")
tz_ny = pytz.timezone("America/New_York")

now_myt = datetime.datetime.now(tz_myt)
now_ny = datetime.datetime.now(tz_ny)

df_j = load_journal()
yesterday_d = now_myt.date() - timedelta(days=1)
yesterday_myt_str = yesterday_d.strftime("%Y-%m-%d")
has_10pm_p = (now_myt.hour >= 22 or now_myt.hour < 5)
has_8am_report = yesterday_myt_str in df_j["Date_MYT"].astype(str).values if not df_j.empty else False

s1, s2, s3, s4 = st.columns(4)
s1.success("✅ 10:00 PM 战区引擎已就绪" if has_10pm_p else "⏳ 10:00 PM 战区引擎等待中")
s2.success(f"✅ 战报已交付 ({yesterday_myt_str})" if has_8am_report else f"⏳ 战报待更新 ({yesterday_myt_str})")
s3.info("🎯 纪律窗口：22:00 - 24:00 (MYT) | 0.5 ATR 止损 / 1:2 TP")

with s4:
    if st.button("🧪 执行系统全链路测试"):
        with st.spinner("正在自检..."):
            d1, d5, errs = fetch_raw_data_with_retry(period_5m="5d")
            if errs: st.error("异常: " + "; ".join(errs))
            else: st.success("自检通过：接口正常。")

st.markdown("---")
tab1, tab2, tab3 = st.tabs(["🎯 QQQ 战区座舱 (13行富途参数复制)", "📅 QQQ 2B同频月历账本", "⚡ 昨夜 22:00-24:00 信号核验与 5M 战场 (0.5 ATR)"])

with tab1:
    st.subheader("🎯 QQQ 5M 战区座舱 (含 SBR/SBR2/RBS/RBS2 & 2B)")
    c_t1, c_t2 = st.columns(2)
    c_t1.info("🕒 大马时间 (MYT): " + now_myt.strftime("%Y-%m-%d %H:%M:%S"))
    c_t2.info("🇺🇸 美东时间 (ET): " + now_ny.strftime("%Y-%m-%d %H:%M:%S"))

    if not has_10pm_p:
        st.warning("🔒 处于日间准备期。大马时间 22:00 准时解锁并生成今晚 13 行战区代码。")
    else:
        if st.button("🔄 刷新最新点位"): st.cache_data.clear(); st.rerun()
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
                st.markdown("#### 📋 复制到富途指标顶部 13 行代码 (点右上角复制):")
                st.code("\n".join(out_lines), language="pascal")

with tab2:
    st.subheader("📅 QQQ 2B 同频月历账本 (22:00 - 24:00 MYT)")
    col_btn1, col_btn2, col_btn3 = st.columns([1.5, 2, 1.5])
    with col_btn1:
        if st.button("🛠️ 结算昨夜 22:00-24:00 账本"):
            with st.spinner("正在结算..."):
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
        if st.button("⚡ 一键回溯补录当月所有历史交易日 (Backfill)"):
            with st.spinner("正在回溯运算..."):
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
                    st.success(f"🎉 回溯完成，新增 {added_cnt} 个交易日记录！")
                    st.rerun()
    with col_btn3:
        if st.button("🗑️ 清空历史账本重新生成"):
            if os.path.exists(CSV_FILE): os.remove(CSV_FILE); st.success("账本已重置！"); st.rerun()

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
            label=f"📥 导出 {sel_y}年{sel_m}月 完整账本 (.csv)",
            data=csv_bytes, file_name=f"Futu_Full_Journal_{sel_y}_{str(sel_m).zfill(2)}.csv", mime="text/csv", disabled=df_m.empty
        )

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("🗓️ 选定月份", f"{sel_y} 年 {sel_m} 月")
    k2.metric("💰 窗口盈亏", f"{tot_pts:+.2f} pt")
    k3.metric("🎯 窗口胜率", f"{w_rate:.1f}%", f"{w_cnt}/{tot_cnt} 胜")
    k4.metric("📊 开仓总笔数", f"{tot_cnt} 笔")

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
                    st.markdown(f"<div style='background-color:#edf2f7; border-radius:8px; padding:8px; height:120px; border:1px dashed #cbd5e0; text-align:center;'><div style='font-size:13px; color:#a0aec0; text-align:left;'><b>{day}</b></div><div style='font-size:18px; margin-top:10px;'>❌</div><div style='font-size:11px; color:#a0aec0;'>周末休市</div></div>", unsafe_allow_html=True)
                else:
                    d_recs = df_m[df_m["Date_MYT_dt"] == cur_d] if not df_m.empty else pd.DataFrame()
                    if not d_recs.empty:
                        r_t = d_recs[d_recs["Signal"] != "NO_TRADE"]
                        cnt = len(r_t); pts = r_t["PnL_Points"].sum() if not r_t.empty else 0.0
                        b_val = d_recs.iloc[0].get("TREND_BIAS", 0)
                        b_str = "多" if b_val == 1 else ("空" if b_val == -1 else "黄灯")
                        if cnt == 0:
                            st.markdown(f"<div style='background-color:#f7fafc; border-radius:8px; padding:8px; height:120px; border:1px solid #e2e8f0; text-align:center;'><div style='font-size:13px; color:#718096; text-align:left;'><b>{day}</b> <span style='font-size:10px; color:#a0aec0;'>({b_str})</span></div><div style='font-size:12px; color:#718096; margin-top:15px;'>⚪ 未触及战区</div><div style='font-size:10px; color:#a0aec0;'>空仓休战</div></div>", unsafe_allow_html=True)
                        else:
                            bg = "#e6fffa" if pts >= 0 else "#fff5f5"
                            bd = "#38b2ac" if pts >= 0 else "#e53e3e"
                            tc = "#234e52" if pts >= 0 else "#742a2a"
                            sgn = "+" if pts > 0 else ""
                            st.markdown(f"<div style='background-color:{bg}; border-radius:8px; padding:8px; height:120px; border:2px solid {bd}; text-align:center;'><div style='font-size:13px; color:{tc}; text-align:left;'><b>{day}</b> <span style='font-size:10px; color:{bd};'>({b_str})</span></div><div style='font-size:15px; font-weight:bold; color:{bd}; margin-top:2px;'>{sgn}{pts:.2f} pt</div><div style='font-size:11px; color:{tc};'>{cnt} 笔交易 (22-24点)</div></div>", unsafe_allow_html=True)
                    else:
                        st.markdown(f"<div style='background-color:#ffffff; border-radius:8px; padding:8px; height:120px; border:1px solid #edf2f7; text-align:center;'><div style='font-size:13px; color:#cbd5e0; text-align:left;'><b>{day}</b></div><div style='font-size:11px; color:#cbd5e0; margin-top:25px;'>-</div></div>", unsafe_allow_html=True)

    with st.expander("🔍 展开查看完整明细表 (Full Data Table)"):
        if not df_m.empty: st.dataframe(df_m.drop(columns=["Date_MYT_dt", "Year", "Month"], errors="ignore"), use_container_width=True)
        else: st.info("当月暂无交易明细。")

with tab3:
    st.subheader(f"⚡ 昨夜 ({yesterday_myt_str}) 22:00 - 24:00 信号核验与 5M 战场")
    
    col_t3_btn, _ = st.columns([1.5, 3])
    with col_t3_btn:
        if st.button("🔄 重新核验昨夜执行信号"):
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
            tc1.metric("🚦 昨夜三灯方向", p["BIAS_DESC"])
            tc2.metric("📈 1H EMA20 战区", f"${p['EMA20_1H']:.2f}")
            tc3.metric("📊 1H ATR 基准", f"${p['ATR_1H']:.2f}")
            
            if trades:
                t = trades[0]
                tc4.metric(
                    "🎯 昨夜战果",
                    f"{t['Result']} ({t['PnL_Points']:+.2f} pt)",
                    f"信号: {t['Signal']}"
                )
            else:
                tc4.metric("🎯 昨夜战果", "⚪ 未触发信号", "空仓观望")

            st.markdown("#### 📋 昨夜执行明细核验 (0.5 ATR 止损 / 1:2 止盈)")
            if trades:
                t_df = pd.DataFrame(trades)
                show_cols = [c for c in t_df.columns if not c.endswith("_DT_NY")]
                st.table(t_df[show_cols])
            else:
                st.info("昨夜 22:00 - 24:00 (MYT) 价格未触及战区准入条件或未形成标准 2B / 吞没形态，按纪律未开仓。")

            st.markdown("#### 📊 5M 战场执行结构全景图 (含 CALL / PUT / 2B 信号标记)")
            
            dt_view_start = dt_10pm_myt - timedelta(minutes=30)
            dt_view_end = dt_10pm_myt + timedelta(hours=2, minutes=15)
            start_ny_view = dt_view_start.astimezone(tz_ny)
            end_ny_view = dt_view_end.astimezone(tz_ny)
            
            if day_5m is not None:
                chart_df = day_5m[(day_5m.index >= start_ny_view) & (day_5m.index <= end_ny_view)].copy()
                
                if not chart_df.empty:
                    chart_df["MYT_Time"] = chart_df.index.tz_convert(tz_myt)
                    
                    fig = go.Figure()
                    
                    # 1. 5M K线
                    fig.add_trace(go.Candlestick(
                        x=chart_df["MYT_Time"],
                        open=chart_df['Open'], high=chart_df['High'],
                        low=chart_df['Low'], close=chart_df['Close'],
                        name="5M K线"
                    ))
                    
                    # 2. 均线
                    fig.add_trace(go.Scatter(
                        x=chart_df["MYT_Time"], y=chart_df["LWMA20"],
                        line=dict(color="orange", width=1.2),
                        name="LWMA 20"
                    ))

                    # 3. 扫描到的 CALL / PUT / 2B 信号点打在图上
                    annotations = []

                    # 扫描多头 2B 信号
                    b2b_df = chart_df[chart_df["BUY_2B_SIG"] == True]
                    for idx_row, row in b2b_df.iterrows():
                        annotations.append(dict(
                            x=row["MYT_Time"], y=row["Low"],
                            xref="x", yref="y",
                            text="▲▲ 2B 多 (CALL)",
                            showarrow=True, arrowhead=2, arrowsize=1.2, arrowwidth=2,
                            arrowcolor="#00e676",
                            ax=0, ay=35,
                            font=dict(color="#00e676", size=11, family="Arial Black")
                        ))

                    # 扫描标准 CALL 多头信号 (吞没/孕线/123)
                    bstd_df = chart_df[chart_df["BUY_STD_SIG"] == True]
                    for idx_row, row in bstd_df.iterrows():
                        annotations.append(dict(
                            x=row["MYT_Time"], y=row["Low"],
                            xref="x", yref="y",
                            text="▲ CALL 多",
                            showarrow=True, arrowhead=2, arrowsize=1, arrowwidth=1.5,
                            arrowcolor="#69f0ae",
                            ax=0, ay=30,
                            font=dict(color="#69f0ae", size=10)
                        ))

                    # 扫描空头 2B 信号
                    s2b_df = chart_df[chart_df["SELL_2B_SIG"] == True]
                    for idx_row, row in s2b_df.iterrows():
                        annotations.append(dict(
                            x=row["MYT_Time"], y=row["High"],
                            xref="x", yref="y",
                            text="▼▼ 2B 空 (PUT)",
                            showarrow=True, arrowhead=2, arrowsize=1.2, arrowwidth=2,
                            arrowcolor="#ff5252",
                            ax=0, ay=-35,
                            font=dict(color="#ff5252", size=11, family="Arial Black")
                        ))

                    # 扫描标准 PUT 空头信号
                    sstd_df = chart_df[chart_df["SELL_STD_SIG"] == True]
                    for idx_row, row in sstd_df.iterrows():
                        annotations.append(dict(
                            x=row["MYT_Time"], y=row["High"],
                            xref="x", yref="y",
                            text="▼ PUT 空",
                            showarrow=True, arrowhead=2, arrowsize=1, arrowwidth=1.5,
                            arrowcolor="#ff8a80",
                            ax=0, ay=-30,
                            font=dict(color="#ff8a80", size=10)
                        ))

                    # 4. 实际成交入场与平仓标记 (带框大标)
                    if trades:
                        tr = trades[0]
                        ep = tr["Entry_Price"]
                        xp = tr["Exit_Price"]
                        sl = tr["SL"]
                        tp = tr["TP"]
                        en_myt = tr["Entry_DT_NY"].astimezone(tz_myt)
                        ex_myt = tr["Exit_DT_NY"].astimezone(tz_myt)

                        # 入场大标
                        is_buy = "多" in tr["Signal"] or "CALL" in tr["Signal"]
                        annotations.append(dict(
                            x=en_myt, y=ep,
                            xref="x", yref="y",
                            text=f"🚀 开仓入场: {ep}",
                            showarrow=True, arrowhead=3, arrowsize=1.5, arrowwidth=2.5,
                            arrowcolor="#ffd700",
                            ax=0, ay=45 if is_buy else -45,
                            bordercolor="#ffd700", borderwidth=1.5, borderpad=3,
                            bgcolor="#1a202c",
                            font=dict(color="#ffd700", size=11, family="Arial Black")
                        ))

                        # 离场大标
                        annotations.append(dict(
                            x=ex_myt, y=xp,
                            xref="x", yref="y",
                            text=f"🏁 平仓 ({tr['Reason']}): {xp}",
                            showarrow=True, arrowhead=3, arrowsize=1.5, arrowwidth=2.5,
                            arrowcolor="#ffffff",
                            ax=0, ay=-45 if is_buy else 45,
                            bordercolor="#ffffff", borderwidth=1.5, borderpad=3,
                            bgcolor="#1a202c",
                            font=dict(color="#ffffff", size=11, family="Arial Black")
                        ))

                        fig.add_hline(y=ep, line_color="#ffd700", line_width=2, annotation_text=f"进场金线: {ep}")
                        fig.add_hline(y=sl, line_dash="dash", line_color="#ff5252", annotation_text=f"止损 (0.5 ATR): {sl}")
                        fig.add_hline(y=tp, line_dash="dash", line_color="#00e676", annotation_text=f"目标 TP (1:2): {tp}")

                    # 5. 战区线
                    if p["SBR_BOT"] > 0:
                        fig.add_hline(y=p["SBR_BOT"], line_dash="dash", line_color="#f56565", annotation_text=f"SBR 阻力底: {p['SBR_BOT']:.2f}")
                    if p["RBS_TOP"] > 0:
                        fig.add_hline(y=p["RBS_TOP"], line_dash="dash", line_color="#48bb78", annotation_text=f"RBS 支撑顶: {p['RBS_TOP']:.2f}")
                    if p["PDH"] > 0:
                        fig.add_hline(y=p["PDH"], line_dash="dot", line_color="#ed8936", annotation_text=f"昨日高 PDH: {p['PDH']:.2f}")
                    if p["PDL"] > 0:
                        fig.add_hline(y=p["PDL"], line_dash="dot", line_color="#4299e1", annotation_text=f"昨日低 PDL: {p['PDL']:.2f}")

                    fig.update_layout(
                        title="昨夜 5M 战场回放 | CALL/PUT 信号扫描与实际执行",
                        xaxis_rangeslider_visible=False,
                        height=560,
                        margin=dict(l=10, r=10, t=40, b=10),
                        template="plotly_dark",
                        annotations=annotations
                    )
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.warning("暂未获取到昨夜窗口期的 5M K线数据。")
        else:
            st.error("计算昨夜 13 行战区参数失败，请检查数据完整性。")
    else:
        st.warning("正在获取数据，请稍后刷新。")
