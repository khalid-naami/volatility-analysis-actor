import asyncio
import logging
from apify import Actor
from src.data_engine import fetch_ticker_data
from src.volatility_engine import calculate_volatility_dossier

logger = logging.getLogger(__name__)

async def main():
    async with Actor:
        actor_input = await Actor.get_input() or {}
        
        symbols = actor_input.get("symbols", ["SPY", "QQQ", "AAPL", "NVDA", "TSLA"])
        include_smile = bool(actor_input.get("includeSmileCurve", True))
        include_term = bool(actor_input.get("includeTermStructure", True))
        include_hist_vol = bool(actor_input.get("includeHistoricalVol", True))
        include_em = bool(actor_input.get("includeExpectedMoveCone", True))
        max_expiries = int(actor_input.get("maxExpirationsToScan", 15))
        
        if isinstance(symbols, str):
            symbols = [s.strip() for s in symbols.split(",") if s.strip()]
            
        Actor.log.info("📊 Starting Options Volatility Analysis & Smile Intelligence Actor...")
        Actor.log.info(f"Target Assets: {symbols} | Max Expiries: {max_expiries}")
        
        results = []
        
        for symbol in symbols:
            try:
                Actor.log.info(f"Analyzing volatility structure, skew, and expected move for {symbol}...")
                spot_price, expirations, hist_df, vix_df, ticker_obj, proxy_ticker = fetch_ticker_data(symbol)
                
                dossier = calculate_volatility_dossier(
                    symbol=symbol,
                    spot_price=spot_price,
                    expirations=expirations,
                    hist_df=hist_df,
                    vix_df=vix_df,
                    ticker_obj=ticker_obj,
                    proxy_ticker=proxy_ticker,
                    include_smile=include_smile,
                    include_term_structure=include_term,
                    include_hist_vol=include_hist_vol,
                    include_expected_move=include_em,
                    max_expirations_to_scan=max_expiries
                )
                
                await Actor.push_data(dossier)
                results.append(dossier)
                
            except Exception as e:
                Actor.log.error(f"Failed volatility analysis for {symbol}: {str(e)}")
                
        # Store executive summary in default Key-Value store
        summary_payload = {
            "totalAnalyzed": len(results),
            "symbols": [r["symbol"] for r in results],
            "summaries": [
                {
                    "symbol": r["symbol"],
                    "price": r["underlyingPrice"],
                    "atmIvPct": r["currentAtmIvPct"],
                    "rv30dPct": r["currentRv30dPct"],
                    "vrp": r["vrpSpread"],
                    "ivRank52wPct": r["ivRank52wPct"],
                    "termStructure": r["termStructureRegime"],
                    "expectedMoveNearest1Pct": r["expectedMoveNearest1Pct"],
                    "volatilityGrade": r["volatilityGrade"]
                }
                for r in results
            ]
        }
        await Actor.set_value("OUTPUT", summary_payload)
        
        Actor.log.info(f"✅ Volatility Analysis Actor completed! {len(results)} asset dossiers pushed to Apify Dataset.")

if __name__ == "__main__":
    asyncio.run(main())
