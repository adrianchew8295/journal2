# 文件：futu_engine.py 裡面的 simulate_trades_with_2b 核心邏輯修正

def simulate_trades_with_2b(df_5m, p, start_cutoff_ny, window_end_ny):
    trades = []
    if p is None or df_5m is None: return trades, None

    day_5m = df_5m[(df_5m.index >= start_cutoff_ny - timedelta(hours=3)) & (df_5m.index <= window_end_ny + timedelta(minutes=15))].copy()
    if len(day_5m) < 25: return trades, None

    weights = np.arange(1, 21)
    day_5m["LWMA20"] = day_5m["Close"].rolling(20).apply(lambda prices: np.dot(prices, weights) / weights.sum(), raw=True)
    
    tr = np.maximum(day_5m["High"] - day_5m["Low"], np.maximum((day_5m["High"] - day_5m["Close"].shift(1)).abs(), (day_5m["Low"] - day_5m["Close"].shift(1)).abs()))
    day_5m["ATR14"] = tr.rolling(14).mean()
    day_5m["VOL_MA"] = day_5m["Volume"].rolling(20).mean()
    day_5m["VOL_HEAVY"] = day_5m["Volume"] >= 1.25 * day_5m["VOL_MA"]

    rbs_top, rbs_bot = p["RBS_TOP"], p["RBS_BOT"]
    rbs2_top, rbs2_bot = p["RBS2_TOP"], p["RBS2_BOT"]
    sbr_top, sbr_bot = p["SBR_TOP"], p["SBR_BOT"]
    sbr2_top, sbr2_bot = p["SBR2_TOP"], p["SBR2_BOT"]
    pdl_line, pdh_line = p["PDL"], p["PDH"]
    pml_line, pmh_line = p["PML"], p["PMH"]
    bias = p["TREND_BIAS"]

    in_rbs1 = (day_5m["Low"] <= rbs_top) & (day_5m["Close"] >= rbs_bot)
    in_rbs2 = (rbs2_top > 0) & (day_5m["Low"] <= rbs2_top) & (day_5m["Close"] >= rbs2_bot)
    in_sbr1 = (day_5m["High"] >= sbr_bot) & (day_5m["Close"] <= sbr_top)
    in_sbr2 = (sbr2_top > 0) & (day_5m["High"] >= sbr2_bot) & (day_5m["Close"] <= sbr2_top)

    buy_zone = in_rbs1 | in_rbs2 | ((day_5m["Low"] <= pdl_line) & (day_5m["Close"] > pdl_line)) | ((day_5m["Low"] <= pml_line) & (day_5m["Close"] > pml_line))
    sell_zone = in_sbr1 | in_sbr2 | ((day_5m["High"] >= pdh_line) & (day_5m["Close"] < pdh_line)) | ((day_5m["High"] >= pmh_line) & (day_5m["Close"] < pmh_line))

    llv5_ref1 = day_5m["Low"].rolling(5).min().shift(1)
    hhv5_ref1 = day_5m["High"].rolling(5).max().shift(1)

    bull_2b_raw = ((day_5m["Low"] < llv5_ref1) | (day_5m["Low"] < pdl_line) | (day_5m["Low"] < pml_line)) & (day_5m["Close"] > llv5_ref1) & (day_5m["Close"] > day_5m["Open"])
    bear_2b_raw = ((day_5m["High"] > hhv5_ref1) | (day_5m["High"] > pdh_line) | (day_5m["High"] > pmh_line)) & (day_5m["Close"] < hhv5_ref1) & (day_5m["Close"] < day_5m["Open"])

    bull_engulf_raw = buy_zone & (day_5m["Close"] > day_5m["Open"]) & (day_5m["Close"].shift(1) < day_5m["Open"].shift(1)) & (day_5m["Close"] >= day_5m["Open"].shift(1)) & (day_5m["Open"] <= day_5m["Close"].shift(1))
    bear_engulf_raw = sell_zone & (day_5m["Close"] < day_5m["Open"]) & (day_5m["Close"].shift(1) > day_5m["Open"].shift(1)) & (day_5m["Close"] <= day_5m["Open"].shift(1)) & (day_5m["Open"] >= day_5m["Close"].shift(1))

    bull_star_raw = buy_zone & (day_5m["Close"].shift(2) < day_5m["Open"].shift(2)) & ((day_5m["Close"].shift(1) - day_5m["Open"].shift(1)).abs() <= 0.35 * (day_5m["High"].shift(1) - day_5m["Low"].shift(1))) & (day_5m["Close"] > day_5m["Open"]) & (day_5m["Close"] >= (day_5m["Open"].shift(2) + day_5m["Close"].shift(2)) / 2)
    bear_star_raw = sell_zone & (day_5m["Close"].shift(2) > day_5m["Open"].shift(2)) & ((day_5m["Close"].shift(1) - day_5m["Open"].shift(1)).abs() <= 0.35 * (day_5m["High"].shift(1) - day_5m["Low"].shift(1))) & (day_5m["Close"] < day_5m["Open"]) & (day_5m["Close"] <= (day_5m["Open"].shift(2) + day_5m["Close"].shift(2)) / 2)

    bull_123_raw = buy_zone & (day_5m["Close"] > day_5m["LWMA20"]) & (day_5m["Close"].shift(1) <= day_5m["LWMA20"].shift(1)) & (day_5m["Low"] > llv5_ref1) & (day_5m["Close"] > day_5m["Open"])
    bear_123_raw = sell_zone & (day_5m["Close"] < day_5m["LWMA20"]) & (day_5m["Close"].shift(1) >= day_5m["LWMA20"].shift(1)) & (day_5m["High"] < hhv5_ref1) & (day_5m["Close"] < day_5m["Open"])

    std_buy_setup = bull_engulf_raw | bull_star_raw | bull_123_raw
    std_sell_setup = bear_engulf_raw | bear_star_raw | bear_123_raw

    vol_heavy_or_ref1 = day_5m["VOL_HEAVY"] | day_5m["VOL_HEAVY"].shift(1)
    
    buy_2b_confirmed = bull_2b_raw.shift(1) & (day_5m["High"] > day_5m["High"].shift(1)) & (day_5m["Close"] > day_5m["Open"]) & vol_heavy_or_ref1
    sell_2b_confirmed = bear_2b_raw.shift(1) & (day_5m["Low"] < day_5m["Low"].shift(1)) & (day_5m["Close"] < day_5m["Open"]) & vol_heavy_or_ref1

    buy_std_confirmed = std_buy_setup.shift(1) & (day_5m["High"] > day_5m["High"].shift(1)) & (day_5m["Close"] > day_5m["Open"]) & (day_5m["Close"] > day_5m["LWMA20"]) & vol_heavy_or_ref1
    sell_std_confirmed = std_sell_setup.shift(1) & (day_5m["Low"] < day_5m["Low"].shift(1)) & (day_5m["Close"] < day_5m["Open"]) & (day_5m["Close"] < day_5m["LWMA20"]) & vol_heavy_or_ref1

    day_5m["BUY_2B_SIG"] = (bias >= 0) & buy_2b_confirmed & (buy_2b_confirmed.rolling(5).sum() == 1)
    day_5m["SELL_2B_SIG"] = (bias <= 0) & sell_2b_confirmed & (sell_2b_confirmed.rolling(5).sum() == 1)
    day_5m["BUY_STD_SIG"] = (bias >= 0) & buy_std_confirmed & (buy_std_confirmed.rolling(5).sum() == 1) & (~day_5m["BUY_2B_SIG"])
    day_5m["SELL_STD_SIG"] = (bias <= 0) & sell_std_confirmed & (sell_std_confirmed.rolling(5).sum() == 1) & (~day_5m["SELL_2B_SIG"])

    in_pos, pos_type = False, 0
    entry_p, sl_p, tp_p = 0.0, 0.0, 0.0
    entry_time_ny = None
    daily_trade_count = 0
    futu_signal_tag = ""

    start_idx = 0
    for idx_i, t_idx in enumerate(day_5m.index):
        if t_idx >= start_cutoff_ny:
            start_idx = idx_i
            break

    for i in range(start_idx, len(day_5m)):
        cur_t_ny = day_5m.index[i]
        c, h, l = day_5m["Close"].iloc[i], day_5m["High"].iloc[i], day_5m["Low"].iloc[i]
        atr_v = day_5m["ATR14"].iloc[i] if not np.isnan(day_5m["ATR14"].iloc[i]) else 0.8
        is_window_close = (cur_t_ny >= window_end_ny - timedelta(minutes=5))

        if in_pos:
            exit_flag, reason, exit_p = False, "", 0.0
            exit_time_ny = cur_t_ny
            
            if pos_type == 1:
                if is_window_close: exit_flag, reason, exit_p = True, "24:00 纪律清仓", c
                elif l <= sl_p: exit_flag, reason, exit_p = True, "SL (结构止损)", sl_p
                elif h >= tp_p: exit_flag, reason, exit_p = True, "TP (1:2 止盈)", tp_p
            elif pos_type == -1:
                if is_window_close: exit_flag, reason, exit_p = True, "24:00 纪律清仓", c
                elif h >= sl_p: exit_flag, reason, exit_p = True, "SL (结构止损)", sl_p
                elif l <= tp_p: exit_flag, reason, exit_p = True, "TP (1:2 止盈)", tp_p

            if exit_flag:
                pnl = (exit_p - entry_p) if pos_type == 1 else (entry_p - exit_p)
                trades.append({
                    "Signal": futu_signal_tag,
                    "Entry_MYT": entry_time_ny.astimezone(tz_myt).strftime("%H:%M"), "Entry_ET": entry_time_ny.strftime("%H:%M"),
                    "Exit_MYT": exit_time_ny.astimezone(tz_myt).strftime("%H:%M"), "Exit_ET": exit_time_ny.strftime("%H:%M"),
                    "Entry_Price": round(entry_p, 2), "Exit_Price": round(exit_p, 2),
                    "SL": round(sl_p, 2), "TP": round(tp_p, 2), "PnL_Points": round(pnl, 2),
                    "Reason": reason, "Result": "盈利" if pnl > 0 else ("保本" if pnl == 0 else "亏损"),
                    "Entry_DT_NY": entry_time_ny, "Exit_DT_NY": exit_time_ny
                })
                in_pos = False
                daily_trade_count += 1
                break

        if not in_pos and daily_trade_count == 0 and cur_t_ny < (window_end_ny - timedelta(minutes=15)):
            is_b2b = bool(day_5m["BUY_2B_SIG"].iloc[i])
            is_s2b = bool(day_5m["SELL_2B_SIG"].iloc[i])
            is_bstd = bool(day_5m["BUY_STD_SIG"].iloc[i])
            is_sstd = bool(day_5m["SELL_STD_SIG"].iloc[i])

            # 100% 对齐富途牛牛公式的结构止损与 1:2 止盈
            if is_b2b or is_bstd:
                in_pos, pos_type = True, 1
                entry_p = c
                sl_p = l - 0.5 * atr_v
                tp_p = c + 2.0 * (c - sl_p)
                entry_time_ny = cur_t_ny
                futu_signal_tag = "▲▲ 2B 多" if is_b2b else "▲ CALL 多"
            elif is_s2b or is_sstd:
                in_pos, pos_type = True, -1
                entry_p = c
                sl_p = h + 0.5 * atr_v
                tp_p = c - 2.0 * (sl_p - c)
                entry_time_ny = cur_t_ny
                futu_signal_tag = "▼▼ 2B 空" if is_s2b else "▼ PUT 空"

    return trades, day_5m
