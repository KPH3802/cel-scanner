# CEL Scanner (Commodity-Equity Lag)

Nightly scanner for **Commodity-Equity Lag** signals. When USO (crude oil ETF) drops 2%+ in a single session, related energy equities typically lag the move by 1-2 days Ñ creating a short opportunity.

## Signal Logic

- **Trigger**: USO daily return <= -2.0%
- **Direction**: SHORT
- **Tickers**: XOP, XLE, CVX, XOM, COP
- **Hold**: 5 trading days
- **BULL side** (USO up 2%+): FLAT Ñ not deployed

## Backtest Results

| Signal | Alpha (5d) | p-value | Notes |
|--------|-----------|---------|-------|
| USO drop >=2% ? SHORT XOP | -0.71%/trade | <0.05 | Consistent 2015-2026 |
| USO drop >=2% ? SHORT XLE | -0.55%/trade | <0.05 | Consistent 2015-2026 |
| USO drop >=2% ? SHORT CVX/XOM/COP | -0.55% to -0.71% | <0.05 | All 5 tickers validated |

## Architecture

```
cel_scanner/
??? cel_scanner.py      # Main scanner Ñ runs nightly on PythonAnywhere
??? config.py           # Credentials and thresholds (not committed)
??? config_example.py   # Template Ñ copy to config.py and fill in values
```

Runs nightly. Fetches yesterday's USO close via yfinance. If drop >= 2%, fires SHORT signals for all 5 energy tickers. Deduplication by trigger date prevents duplicate signals.

Subject line parseable by IB AutoTrader:
- `CEL BEAR: XOP, XLE, CVX, XOM, COP` ? autotrader places SHORT orders

## Setup

```bash
pip install yfinance
cp config_example.py config.py
# Edit config.py with your email credentials
python3 cel_scanner.py --test-email
python3 cel_scanner.py --dry-run
python3 cel_scanner.py --status
```

Deploy on PythonAnywhere: schedule daily at **02:00 UTC**.

## IB AutoTrader Integration

The `ib-autotrader` repo parses CEL email subjects via `query_cel_signals_from_email()`. All 5 tickers are shorted at full size, tracked in `positions.db` with 5-day time exit.

## Disclaimer

For research and educational purposes. Not investment advice.

---

MIT License
