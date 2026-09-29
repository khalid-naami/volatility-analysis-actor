# Options Volatility Analysis, Smile & Term Structure 📊🌊

**Options Volatility Analysis, Smile & Term Structure** is an institutional quantitative options volatility Actor on Apify. It extracts real-time options chains, models At-The-Money Implied Volatility (ATM IV), 30-Day Historical Realized Volatility (RV), 52-Week IV Rank and IV Percentile, Variance Risk Premium (VRP), strike-by-strike Volatility Smiles, forward Term Structures (Contango vs Backwardation), option Skewness & Kurtosis tail risk, and market-implied Expected Move cones.

---

## 🌟 Key Features

1. **Core Volatility 5-Pack Metrics:**
   - **ATM Implied Volatility (IV %):** Midpoint of At-The-Money Call and Put IV.
   - **30-Day Realized Volatility (RV %):** $\text{std}(\text{log returns}) \times \sqrt{252} \times 100$.
   - **VIX Benchmark Proxy:** Automated asset volatility index mapping (`SPY -> ^VIX`, `QQQ -> ^VXN`, `IWM -> ^RVX`, `AAPL -> ^VXAPL`, `NVDA -> ^VXNVD`, `TSLA -> ^VXTSL`).
   - **52-Week IV Rank & Percentile:** Relative position of current volatility within its 1-year historical range.
   - **Variance Risk Premium (VRP):** $\text{IV} - \text{RV}$ (identifies whether options are overvalued or undervalued).

2. **Strike-by-Strike Volatility Smile & Skew Curve:**
   - Detailed strike-by-strike Call IV and Put IV curve across the active expiration cycle ($0.8 \times S$ to $1.2 \times S$).

3. **IV Term Structure Matrix (Contango vs Backwardation):**
   - ATM IV curve across all future expiration dates (DTE 1 to 365+ days).
   - Automated regime classification: `Normal Contango`, `Inverted Backwardation`, or `Flat Volatility Curve`.

4. **Option Skewness & Kurtosis (Tail Risk):**
   - **Skewness Ratio:** $\frac{\text{IV}_{\text{OTM Put}} - \text{IV}_{\text{OTM Call}}}{\text{IV}_{\text{ATM}}}$.
   - **Kurtosis (Fat Tails):** $\frac{\text{IV}_{\text{OTM Put}} + \text{IV}_{\text{OTM Call}} - 2 \times \text{IV}_{\text{ATM}}}{\text{IV}_{\text{ATM}}}$.

5. **Options Market-Implied Expected Move Cone:**
   - Upper and Lower price bounds derived from ATM Straddle pricing across the nearest 4 expiration cycles: $\pm 0.85 \times (\text{Call}_{\text{mid}} + \text{Put}_{\text{mid}})$.

6. **1-Year Historical IV vs RV Timeseries:**
   - Daily 1-year time series tracking Historical Realized Volatility, Benchmark VIX, and Rolling IV Rank.

---

## 📥 Input Configuration

| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `symbols` | `array` | `["SPY", "QQQ", "AAPL", "NVDA", "TSLA"]` | List of tickers to calculate full volatility diagnostics for. |
| `includeSmileCurve` | `boolean` | `true` | Calculate strike-by-strike Call and Put Implied Volatility curves. |
| `includeTermStructure` | `boolean` | `true` | Calculate ATM IV term structure across future expiration cycles. |
| `includeHistoricalVol` | `boolean` | `true` | Include 1-year daily history of Realized Volatility and VIX proxy. |
| `includeExpectedMoveCone` | `boolean` | `true` | Compute market-implied upper/lower expected move bounds. |
| `maxExpirationsToScan` | `integer` | `15` | Maximum forward expiration cycles to scan (3–30). |

---

## 📤 Output Schema

```json
{
  "symbol": "NVDA",
  "underlyingPrice": 128.45,
  "selectedExpiry": "2026-10-16",
  "currentAtmIvPct": 46.85,
  "currentRv30dPct": 38.20,
  "vixProxyTicker": "^VXNVD",
  "vixProxyValue": 45.90,
  "ivRank52wPct": 62.4,
  "ivPercentile52wPct": 68.0,
  "vrpSpread": 8.65,
  "termStructureRegime": "Normal Contango 📈 (Front Month < Back Month)",
  "skewnessRatio": 0.1450,
  "kurtosisFatTail": 0.0920,
  "expectedMoveNearest1Pct": 4.15,
  "volatilityGrade": "ELEVATED IV / RICH PREMIUM 🟢 (Net Credit Strategies Favorable)",
  "volatilitySmileCurve": [ ... ],
  "termStructureMatrix": [ ... ],
  "expectedMoveProjections": [ ... ],
  "historicalVolTimeSeries": [ ... ]
}
```

---

## 🚀 Local Run

```bash
uv run --with apify --with pandas --with numpy --with scipy --with yfinance --with requests --with pytz --with python-dateutil python -m src.main
```
