# 文件名：futu_engine.py
# 作用：富途 13 行参数抽取与 100% 对齐富途指标的 5M 回测引擎
import datetime
from datetime import timedelta
import numpy as np
import pandas as pd
import pytz

tz_myt = pytz.timezone("Asia/Kuala_Lumpur")
tz_ny = pytz.timezone("America/New_York")

def compute_futu_13_params(df_1h, df_5m, as_of_ny_time):
    """
    计算富途牛牛 13 行战区参数
    """
    try:
        if df_1h is None: return None
        sub_1h = df_1h[df_1h.index <= as_of_ny_time].copy()
        if len(sub_1h) < 25: return None

        today_ny = as_of_ny_time.date()
        df_rth = sub_1h[(sub_1h.index.hour > 9) | ((sub_1h.index.hour == 9) & (sub_1h.index.minute >= 30))]
        df_rth = df_rth[df_rth.index.hour < 16]
        past_dates = sorted(list(set(df_rth.index.date)))
        past_dates = [d for d in past_dates if d < today_ny]

        if past_dates:
            prev_df = df_rth[df_rth.index.date == past_dates[-1]]
            pdh_idx, pdl_idx = prev_df["High"].idxmax(), prev_df["Low"].idxmin()
            pdh_val, pdl_val = float(prev_df.loc[pdh_idx, "High"]), float(prev_df.loc[pdl_idx, "Low"])
            pdh_time, pdl_time = pdh_idx.strftime("%Y-%m-%d %H:%M ET"), pdl_idx.strftime("%Y-%m-%d %H:%M ET")
        else:
            pdh_val, pdl_val = float(sub_1h["High"].iloc[-10:].max()), float(sub_1h["Low"].iloc[-10:].min())
            pdh_time, pdl_time = "Prior Session", "Prior Session"

        sub_5m_pm = df_5m[(df_5m.index.date == today_ny) & (df_5m.index.hour >= 4) & (df_5m.index < as_of_ny_time)] if df_5m is not None else None
        if sub_5m_pm is not None and not sub_5m_pm.empty:
            pmh_idx, pml_idx = sub_5m_pm["High"].idxmax(), sub_5m_pm["Low"].idxmin()
            pmh_val, pml_val = float(sub_5m_pm.loc[pmh_idx, "High"]), float(sub_5m_pm.loc[pml_idx, "Low"])
            pmh_time, pml_time = pmh_idx.strftime("%Y-%m-%d %H:%M ET"), pml_idx.strftime("%Y-%m-%d %H:%M ET")
            live_price = float(sub_5m_pm["Close"].iloc[-1])
        else:
            pmh_val, pml_val = float(sub_1h["High"].iloc[-4:].max()), float(sub_1h["Low"].iloc[-4:].min())
            pmh_time, pml_time = "Recent 1H", "Recent 1H"
            live_price = float(sub_1h["Close"].iloc[-1])

        sub_1h["EMA20"] = sub_1h["Close"].ewm(span=20, adjust=False).mean()
        sub_1h["SMA50"] = sub_1h["Close"].rolling(window=50).mean()

        tr = np.maximum(sub_1h["High"] - sub_1h["Low"], np.maximum((sub_1h["High"] - sub_1h["Close"].shift(1)).abs(), (sub_1h["Low"] - sub_1h["Close"].shift(1)).abs()))
        atr = float(tr.rolling(14).mean().iloc[-1]) if not np.isnan(tr.rolling(14).mean().iloc[-1]) else (live_price * 0.008)

        subset = sub_1h.iloc[-60:].copy()
        highs, lows, opens, closes, times = subset["High"].values, subset["Low"].values, subset["Open"].values, subset["Close"].values, subset.index

        pivots_high, pivots_low = [], []
        for i in range(2, len(subset) - 2):
            if highs[i] == max(highs[i-2:i+3]): pivots_high.append((float(highs[i]), float(max(opens[i], closes[i])), times[i].strftime("%m-%d %H:%M ET")))
            if lows[i] == min(lows[i-2:i+3]): pivots_low.append((float(min(opens[i], closes[i])), float(lows[i]), times[i].strftime("%m-%d %H:%M ET")))

        valid_highs = [p for p in pivots_high if p[0] > live_price]
        valid_highs.sort(key=lambda x: x[0])
        sbr_top, sbr_bot, sbr_time = valid_highs[0] if len(valid_highs) >= 1 else (live_price + 1.2 * atr, live_price + 0.6 * atr, "Range High")
        sbr2_top, sbr2_bot, sbr2_time = valid_highs[1] if len(valid_highs) >= 2 else (sbr_top + 1.2 * atr, sbr_top + 0.5 * atr, "Tier-2 High")

        valid_lows = [p for p in pivots_low if p[1] < live_price]
        valid_lows.sort(key=lambda x: x[1], reverse=True)
        rbs_top, rbs_bot, rbs_time = valid_lows[0] if len(valid_lows) >= 1 else (live_price - 0.6 * atr, live_price - 1.2 * atr, "Range Low")
        rbs2_top, rbs2_bot, rbs2_time = valid_lows[1] if len(valid_lows) >= 2 else (rbs_bot - 0.5 * atr, rbs_bot - 1.2 * atr, "Tier-2 Low")

        ema20_now = float(sub_1h["EMA20"].iloc[-1])
        sma50_now = float(sub_1h["SMA50"].iloc[-1]) if not np.isnan(sub_1h["SMA50"].iloc[-1]) else ema20_now
        score_ma = 1 if (live_price > ema20_now and ema20_now >= sma50_now) else (-1 if (live_price < ema20_now and ema20_now <= sma50_now) else 0)

        score_hhll = 0
        if len(pivots_high) >= 2 and len(pivots_low) >= 2:
            last_2_h, last_2_l = [p[0] for p in pivots_high[-2:]], [p[1] for p in pivots_low[-2:]]
            if last_2_h[1] > last_2_h[0] and last_2_l[1] > last_2_l[0]: score_hhll = 1
            elif last_2_h[1] < last_2_h[0] and last_2_l[1] < last_2_l[0]: score_hhll = -1

        ema20_prev = float(sub_1h["EMA20"].iloc[-5])
        ema_slope = (ema20_now - ema20_prev) / ema20_prev * 100
        score_slope = 1 if ema_slope > 0.15 else (-1 if ema_slope < -0.15 else 0)

        total_score = score_ma + score_hhll + score_slope
        trend_bias = 1 if total_score >= 2 else (-1 if total_score <= -2 else 0)
        bias_desc = "🟢 绿灯 (做多为主)" if trend_bias == 1 else ("🔴 红灯 (做空为主)" if trend_bias == -1 else "🟡 黄灯 (震荡防守)")

        return {
            "live_price": live_price, "TREND_BIAS": trend_bias, "BIAS_DESC": bias_desc,
            "EMA20_1H": round(ema20_now, 2), "ATR_1H": round(atr, 2),
            "SBR_TOP": sbr_top, "SBR_BOT": sbr_bot, "SBR_TIME": sbr_time,
            "RBS_TOP": rbs_top, "RBS_BOT": rbs_bot, "RBS_TIME": rbs_time,
            "SBR2_TOP": sbr2_top, "SBR2_BOT": sbr2_bot, "SBR2_TIME": sbr2_time,
            "RBS2_TOP": rbs2_top, "RBS2_BOT": rbs2_bot, "RBS2_TIME": rbs2_time,
            "PDH": pdh_val, "PDH_TIME": pdh_time, "PDL": pdl_val, "PDL_TIME": pdl_time,
            "PMH": pmh_val, "PMH_TIME": pmh_time, "PML": pml_val, "PML_TIME": pml_time
        }
    except Exception as e:
        print(f"计算战区参数发生异常: {str(e)}")
        return None

def simulate_trades_with_2b(df_5m, p, start_cutoff_ny, window_end_ny):
    """
    100% 对齐富途指标逻辑的 5M 回测引擎 (结构止损 / 1:2 止盈)
    """
    trades = []
    try:
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
    except Exception as e:
        print(f"回测运算发生异常: {str(e)}")
        return [], None
