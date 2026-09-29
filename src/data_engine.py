import datetime
import logging
import re
import pandas as pd
import numpy as np
import yfinance as yf

logger = logging.getLogger(__name__)

VIX_PROXIES = {
    "SPY": "^VIX", "SPX": "^VIX", "^SPX": "^VIX", "^GSPC": "^VIX",
    "QQQ": "^VXN", "NDX": "^VXN", "^NDX": "^VXN",
    "IWM": "^RVX", "RUT": "^RVX", "^RUT": "^RVX",
    "DIA": "^VXD", "DJI": "^VXD",
    "AAPL": "^VXAPL",
    "GOOG": "^VXGOG", "GOOGL": "^VXGOG",
    "AMZN": "^VXAZN",
    "TSLA": "^VXTSL",
    "MSFT": "^VXMSF",
    "META": "^VXMTF",
    "NFLX": "^VXNFL",
    "NVDA": "^VXNVD"
}

def get_vix_proxy(symbol: str) -> str:
    """Resolve dedicated VIX proxy ticker for an equity or index."""
    clean = symbol.upper().replace("^", "").strip()
    return VIX_PROXIES.get(clean, "^VIX")

def fetch_ticker_data(symbol: str) -> tuple:
    """
    Fetch spot price, available options expirations, option chains, and 1-year historical data.
    """
    sym = symbol.upper().strip()
    ticker_obj = yf.Ticker(sym)
    
    # 1. Resolve Spot Price
    spot_price = None
    try:
        fast_info = getattr(ticker_obj, 'fast_info', None)
        if fast_info and hasattr(fast_info, 'last_price') and fast_info.last_price:
            spot_price = float(fast_info.last_price)
    except Exception:
        pass
        
    if spot_price is None:
        try:
            hist_1d = ticker_obj.history(period="5d")
            if not hist_1d.empty:
                spot_price = float(hist_1d['Close'].iloc[-1])
        except Exception:
            pass
            
    if spot_price is None or spot_price <= 0:
        raise ValueError(f"Could not retrieve spot price for ticker '{symbol}'.")
        
    # 2. Options Expirations
    expirations = []
    try:
        if ticker_obj.options:
            date_pattern = re.compile(r"^\d{4}-\d{2}-\d{2}$")
            expirations = [d for d in ticker_obj.options if date_pattern.match(str(d))]
    except Exception as e:
        logger.warning(f"Error fetching options expirations for {symbol}: {e}")
        
    # 3. 1-Year Historical Data for Ticker and VIX Proxy
    proxy_ticker = get_vix_proxy(sym)
    hist_df = pd.DataFrame()
    vix_df = pd.DataFrame()
    
    try:
        hist_df = ticker_obj.history(period="1y")
        if not hist_df.empty:
            if hist_df.index.tz is not None:
                hist_df.index = hist_df.index.tz_localize(None)
            hist_df['returns'] = np.log(hist_df['Close'] / hist_df['Close'].shift(1))
            hist_df['rv'] = hist_df['returns'].rolling(30).std() * np.sqrt(252) * 100.0
    except Exception as e:
        logger.warning(f"Failed to fetch 1Y history for {symbol}: {e}")
        
    try:
        v_obj = yf.Ticker(proxy_ticker)
        vix_df = v_obj.history(period="1y")
        if not vix_df.empty:
            if vix_df.index.tz is not None:
                vix_df.index = vix_df.index.tz_localize(None)
    except Exception as e:
        logger.warning(f"Failed to fetch VIX proxy history for {proxy_ticker}: {e}")
        
    return spot_price, expirations, hist_df, vix_df, ticker_obj, proxy_ticker

def fetch_option_chain_for_expiry(ticker_obj, expiry: str) -> tuple:
    """Fetch call and put option chains for a given expiration."""
    try:
        chain = ticker_obj.option_chain(expiry)
        calls = chain.calls if chain.calls is not None else pd.DataFrame()
        puts = chain.puts if chain.puts is not None else pd.DataFrame()
        return calls, puts
    except Exception as e:
        logger.warning(f"Failed to fetch option chain for {expiry}: {e}")
        return pd.DataFrame(), pd.DataFrame()
