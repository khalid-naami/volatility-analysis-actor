import datetime
import logging
import math
import pandas as pd
import numpy as np
from src.data_engine import fetch_option_chain_for_expiry

logger = logging.getLogger(__name__)

def grade_volatility_environment(iv_rank: float, vrp: float) -> str:
    """Assign qualitative volatility trading environment grade."""
    if iv_rank >= 80.0:
        return "EXTREME HIGH IV 💥 (Premium Selling Heavily Favored)"
    elif iv_rank >= 50.0 and vrp > 2.0:
        return "ELEVATED IV / RICH PREMIUM 🟢 (Net Credit Strategies Favorable)"
    elif iv_rank <= 20.0 or vrp < -2.0:
        return "DEPRESSED / CHEAP VOLATILITY ❄️ (Long Vega / Debit Spreads Favored)"
    else:
        return "FAIR VALUE VOLATILITY ⚖️ (Neutral Regime)"

def calculate_volatility_dossier(
    symbol: str,
    spot_price: float,
    expirations: list,
    hist_df: pd.DataFrame,
    vix_df: pd.DataFrame,
    ticker_obj,
    proxy_ticker: str,
    include_smile: bool = True,
    include_term_structure: bool = True,
    include_hist_vol: bool = True,
    include_expected_move: bool = True,
    max_expirations_to_scan: int = 15
) -> dict:
    """
    Main quantitative volatility analysis orchestrator.
    """
    S = float(spot_price)
    now_date = datetime.date.today()
    
    # 1. 30-Day Realized Volatility
    current_rv = 20.0
    if not hist_df.empty and 'rv' in hist_df.columns:
        last_rv = hist_df['rv'].dropna()
        if not last_rv.empty:
            current_rv = round(float(last_rv.iloc[-1]), 2)
            
    # 2. VIX Proxy Metrics
    vix_current = current_rv
    vix_high = current_rv * 1.5
    vix_low = current_rv * 0.5
    iv_rank = 50.0
    iv_percentile = 50.0
    
    if not vix_df.empty and 'Close' in vix_df.columns:
        v_close = vix_df['Close'].dropna()
        if not v_close.empty:
            vix_current = round(float(v_close.iloc[-1]), 2)
            vix_high = round(float(v_close.max()), 2)
            vix_low = round(float(v_close.min()), 2)
            if vix_high > vix_low:
                iv_rank = round(float(((vix_current - vix_low) / (vix_high - vix_low)) * 100.0), 1)
            iv_percentile = round(float((v_close < vix_current).mean() * 100.0), 1)
            
    # 3. Resolve active expiration & ATM IV
    selected_expiry = expirations[0] if expirations else datetime.date.today().strftime('%Y-%m-%d')
    current_iv_pct = vix_current
    smile_data = []
    
    if expirations and ticker_obj:
        calls_df, puts_df = fetch_option_chain_for_expiry(ticker_obj, selected_expiry)
        if not calls_df.empty or not puts_df.empty:
            available_strikes = sorted(list(set(calls_df.get('strike', pd.Series()).tolist() + puts_df.get('strike', pd.Series()).tolist())))
            if available_strikes:
                atm_strike = min(available_strikes, key=lambda s: abs(s - S))
                
                atm_c = calls_df[calls_df['strike'] == atm_strike] if not calls_df.empty else pd.DataFrame()
                atm_p = puts_df[puts_df['strike'] == atm_strike] if not puts_df.empty else pd.DataFrame()
                
                c_iv = float(atm_c['impliedVolatility'].iloc[0]) if not atm_c.empty and pd.notna(atm_c['impliedVolatility'].iloc[0]) else np.nan
                p_iv = float(atm_p['impliedVolatility'].iloc[0]) if not atm_p.empty and pd.notna(atm_p['impliedVolatility'].iloc[0]) else np.nan
                
                mean_iv = np.nanmean([c_iv, p_iv])
                if not np.isnan(mean_iv) and mean_iv > 0:
                    current_iv_pct = round(float(mean_iv * 100.0), 2)
                    
                # Smile curve across strikes [0.8*S to 1.2*S]
                if include_smile:
                    s_min = S * 0.80
                    s_max = S * 1.20
                    smile_strikes = [s for s in available_strikes if s_min <= s <= s_max]
                    
                    for s in smile_strikes:
                        c_row = calls_df[calls_df['strike'] == s] if not calls_df.empty else pd.DataFrame()
                        p_row = puts_df[puts_df['strike'] == s] if not puts_df.empty else pd.DataFrame()
                        
                        s_c_iv = round(float(c_row['impliedVolatility'].iloc[0]) * 100.0, 2) if not c_row.empty and pd.notna(c_row['impliedVolatility'].iloc[0]) else None
                        s_p_iv = round(float(p_row['impliedVolatility'].iloc[0]) * 100.0, 2) if not p_row.empty and pd.notna(p_row['impliedVolatility'].iloc[0]) else None
                        
                        if s_c_iv is not None or s_p_iv is not None:
                            smile_data.append({
                                "strike": float(s),
                                "callIvPct": s_c_iv,
                                "putIvPct": s_p_iv
                            })

    # Variance Risk Premium (VRP)
    vrp = round(float(current_iv_pct - current_rv), 2)
    vol_grade = grade_volatility_environment(iv_rank, vrp)

    # 4. Term Structure & Skewness / Kurtosis Matrix
    term_structure = []
    scan_exps = expirations[:max_expirations_to_scan] if expirations else []
    
    if include_term_structure and scan_exps and ticker_obj:
        for exp in scan_exps:
            try:
                exp_dt = datetime.datetime.strptime(exp, '%Y-%m-%d').date()
                dte = max(1, (exp_dt - now_date).days)
                
                c_df, p_df = fetch_option_chain_for_expiry(ticker_obj, exp)
                if c_df.empty and p_df.empty:
                    continue
                    
                strikes = sorted(list(set(c_df.get('strike', pd.Series()).tolist() + p_df.get('strike', pd.Series()).tolist())))
                if not strikes:
                    continue
                    
                atm_s = min(strikes, key=lambda s: abs(s - S))
                c_atm = c_df[c_df['strike'] == atm_s] if not c_df.empty else pd.DataFrame()
                p_atm = p_df[p_df['strike'] == atm_s] if not p_df.empty else pd.DataFrame()
                
                c_iv_atm = float(c_atm['impliedVolatility'].iloc[0]) if not c_atm.empty and pd.notna(c_atm['impliedVolatility'].iloc[0]) else np.nan
                p_iv_atm = float(p_atm['impliedVolatility'].iloc[0]) if not p_atm.empty and pd.notna(p_atm['impliedVolatility'].iloc[0]) else np.nan
                avg_iv = np.nanmean([c_iv_atm, p_iv_atm])
                
                # 5% OTM Call and 5% OTM Put for Skewness & Kurtosis
                call_target = atm_s * 1.05
                put_target = atm_s * 0.95
                call_s = min(strikes, key=lambda s: abs(s - call_target))
                put_s = min(strikes, key=lambda s: abs(s - put_target))
                
                c_otm = c_df[c_df['strike'] == call_s] if not c_df.empty else pd.DataFrame()
                p_otm = p_df[p_df['strike'] == put_s] if not p_df.empty else pd.DataFrame()
                
                iv_c_otm = float(c_otm['impliedVolatility'].iloc[0]) if not c_otm.empty and pd.notna(c_otm['impliedVolatility'].iloc[0]) else np.nan
                iv_p_otm = float(p_otm['impliedVolatility'].iloc[0]) if not p_otm.empty and pd.notna(p_otm['impliedVolatility'].iloc[0]) else np.nan
                
                skewness = None
                kurtosis = None
                if not np.isnan(avg_iv) and avg_iv > 0 and not np.isnan(iv_c_otm) and not np.isnan(iv_p_otm):
                    skewness = round(float((iv_p_otm - iv_c_otm) / avg_iv), 4)
                    kurtosis = round(float((iv_p_otm + iv_c_otm - 2.0 * avg_iv) / avg_iv), 4)
                    
                if not np.isnan(avg_iv) and avg_iv > 0:
                    term_structure.append({
                        "expiry": exp,
                        "dte": int(dte),
                        "atmIvPct": round(float(avg_iv * 100.0), 2),
                        "skewnessRatio": skewness,
                        "kurtosisFatTail": kurtosis
                    })
            except Exception as e:
                logger.warning(f"Failed term structure for {exp}: {e}")
                
    # Determine Term Structure Regime (Contango vs Backwardation)
    term_regime = "Normal Contango 📈 (Front Month < Back Month)"
    if len(term_structure) >= 2:
        front_iv = term_structure[0]["atmIvPct"]
        back_iv = term_structure[-1]["atmIvPct"]
        if front_iv > back_iv + 1.5:
            term_regime = "Inverted Backwardation ⚠️ (Front Month Spike - Event Risk / Panic)"
        elif abs(front_iv - back_iv) <= 1.5:
            term_regime = "Flat Volatility Curve ➖ (Uniform Risk Distribution)"

    first_skew = term_structure[0].get("skewnessRatio") if term_structure else 0.12
    first_kurt = term_structure[0].get("kurtosisFatTail") if term_structure else 0.08

    # 5. Expected Move Projections across nearest 4 cycles
    expected_moves = []
    if include_expected_move and scan_exps and ticker_obj:
        for exp in scan_exps[:4]:
            exp_dt = datetime.datetime.strptime(exp, '%Y-%m-%d').date()
            t_dte = max(1, (exp_dt - now_date).days)
            t_years = max(1e-5, t_dte / 365.0)
            
            c_df, p_df = fetch_option_chain_for_expiry(ticker_obj, exp)
            straddle = 0.0
            if not c_df.empty and not p_df.empty:
                strikes = sorted(list(set(c_df.get('strike', pd.Series()).tolist() + p_df.get('strike', pd.Series()).tolist())))
                if strikes:
                    atm_s = min(strikes, key=lambda s: abs(s - S))
                    c_row = c_df[c_df['strike'] == atm_s]
                    p_row = p_df[p_df['strike'] == atm_s]
                    
                    c_mid = 0.0
                    if not c_row.empty:
                        b, a = c_row.iloc[0].get('bid', 0), c_row.iloc[0].get('ask', 0)
                        c_mid = (b + a) / 2.0 if (b > 0 and a > 0) else c_row.iloc[0].get('lastPrice', 0)
                    p_mid = 0.0
                    if not p_row.empty:
                        b, a = p_row.iloc[0].get('bid', 0), p_row.iloc[0].get('ask', 0)
                        p_mid = (b + a) / 2.0 if (b > 0 and a > 0) else p_row.iloc[0].get('lastPrice', 0)
                        
                    straddle = float(c_mid + p_mid)
                    
            if straddle <= 0:
                # Black-Scholes ATM Straddle approximation: 0.8 * S * sigma * sqrt(T)
                straddle = 0.80 * S * (current_iv_pct / 100.0) * math.sqrt(t_years)
                
            em_val = round(float(0.85 * straddle), 2)
            em_pct = round(float((em_val / S) * 100.0), 2)
            
            expected_moves.append({
                "expiry": exp,
                "dte": int(t_dte),
                "expectedMoveDollars": em_val,
                "expectedMovePct": em_pct,
                "upperBoundPrice": round(float(S + em_val), 2),
                "lowerBoundPrice": round(float(S - em_val), 2)
            })

    first_em_pct = expected_moves[0]["expectedMovePct"] if expected_moves else 2.50

    # 6. Historical IV vs RV 1-Year Timeseries
    hist_vol_series = []
    rank_history_series = []
    
    if include_hist_vol and not hist_df.empty:
        common_idx = hist_df.index
        if not vix_df.empty:
            common_idx = hist_df.index.intersection(vix_df.index)
            
        for idx in common_idx[-252:]:
            dt_str = idx.strftime('%Y-%m-%d')
            rv_pt = round(float(hist_df.loc[idx, 'rv']), 2) if 'rv' in hist_df.columns and pd.notna(hist_df.loc[idx, 'rv']) else None
            vix_pt = round(float(vix_df.loc[idx, 'Close']), 2) if not vix_df.empty and idx in vix_df.index and pd.notna(vix_df.loc[idx, 'Close']) else None
            close_pt = round(float(hist_df.loc[idx, 'Close']), 2) if pd.notna(hist_df.loc[idx, 'Close']) else None
            
            hist_vol_series.append({
                "date": dt_str,
                "realizedVol30d": rv_pt,
                "vixProxy": vix_pt,
                "underlyingClose": close_pt
            })
            
        # 252-day Rolling IV Rank and Percentile
        if not vix_df.empty:
            v_copy = vix_df.copy()
            v_copy['r_low'] = v_copy['Close'].rolling(252, min_periods=30).min()
            v_copy['r_high'] = v_copy['Close'].rolling(252, min_periods=30).max()
            v_copy['r_rank'] = ((v_copy['Close'] - v_copy['r_low']) / (v_copy['r_high'] - v_copy['r_low'])) * 100.0
            
            for idx in v_copy.index[-252:]:
                r_val = round(float(v_copy.loc[idx, 'r_rank']), 1) if pd.notna(v_copy.loc[idx, 'r_rank']) else None
                if r_val is not None:
                    rank_history_series.append({
                        "date": idx.strftime('%Y-%m-%d'),
                        "ivRank": r_val
                    })

    output_dossier = {
        "symbol": symbol,
        "underlyingPrice": S,
        "selectedExpiry": selected_expiry,
        "currentAtmIvPct": current_iv_pct,
        "currentRv30dPct": current_rv,
        "vixProxyTicker": proxy_ticker,
        "vixProxyValue": vix_current,
        "ivRank52wPct": iv_rank,
        "ivPercentile52wPct": iv_percentile,
        "vrpSpread": vrp,
        "termStructureRegime": term_regime,
        "skewnessRatio": first_skew,
        "kurtosisFatTail": first_kurt,
        "expectedMoveNearest1Pct": first_em_pct,
        "volatilityGrade": vol_grade,
        "volatilitySmileCurve": smile_data,
        "termStructureMatrix": term_structure,
        "expectedMoveProjections": expected_moves,
        "historicalVolTimeSeries": hist_vol_series,
        "ivRankTimeSeries": rank_history_series,
        "calculatedAt": datetime.datetime.now(datetime.timezone.utc).isoformat()
    }

    return output_dossier
