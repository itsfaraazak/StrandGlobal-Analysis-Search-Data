# Task 1: Search and web data investigation (Google Trends, Similarweb, AppGoblin)

Deliverable note: `Faraaz_search_web_data_note.docx` (same content in `note.md`).

## Folder map
| Path | What |
|---|---|
| `scripts/config.py` | Firm universe, ticker → search keyword mapping, mapping notes |
| `scripts/01_pull_trends.py` | Pulls Google Trends (US, monthly, 2016-01 → today) for each keyword, 4 pulls on 2 days |
| `scripts/02_pull_sec_revenue.py` | Pulls reported quarterly revenue from SEC EDGAR XBRL (first-reported values, filing dates) |
| `scripts/03_build_signal_and_test.py` | Builds signal, runs in-sample, out-of-sample and rank-IC tests, writes charts |
| `scripts/04_note_to_docx.py` | Rebuilds the Word note from `note.md` |
| `output/sample_DUOL_dated.csv` | Small dated sample for the worked example (Duolingo: revenue, Trends, signal) |
| `data/raw/trends_monthly_pull{1..4}.csv` | **Observed** Google Trends index, dated (`pulled_at_utc`) |
| `data/raw/trends_weekly_5y_DUOL.csv` | Weekly Trends sample for worked example (Duolingo) |
| `data/processed/revenue_quarterly.csv` | **Observed** reported revenue (SEC filings) |
| `data/processed/appgoblin_duolingo_snapshots.csv` | AppGoblin extract: the only two dated snapshots in the free GitHub repo |
| `output/results.txt` | All test statistics |
| `output/panel.csv`, `per_firm.csv`, `oos_predictions.csv`, `rank_ic_by_quarter.csv` | Intermediate results |
| `output/*.png` | Charts |
| `refs/` | Da, Engelberg & Gao (2011) PDF + text; Lind & Ramesh (2025) PDF (scanned, read manually) |
| `EXPLAINER.md` | Plain-English explanation of every concept, script and likely question |

## Reproduce
```bash
cd claude-tmp
python3 -m venv .venv.nosync && .venv.nosync/bin/pip install pandas numpy statsmodels pytrends requests matplotlib python-docx
.venv.nosync/bin/python scripts/02_pull_sec_revenue.py        # ~30 s
.venv.nosync/bin/python scripts/01_pull_trends.py 3            # ~15 min (rate limited; resumable: `01_pull_trends.py 3 2`)
.venv.nosync/bin/python scripts/03_build_signal_and_test.py
```

## Manual alternative (no code)
1. trends.google.com → Explore → type keyword (e.g. `duolingo`) → Region: United States → time: "2016 – present" (custom) → Download (CSV, top-right of chart).
2. Repeat on a different day: values differ slightly because Trends is a sample.
3. Revenue: SEC EDGAR full-text search or `https://data.sec.gov/api/xbrl/companyfacts/CIK##########.json`.

## Caveats
- `.venv.nosync`: the Desktop is iCloud-synced; iCloud evicted files from a normal `.venv` and imports hung. The `.nosync` suffix stops iCloud syncing it.
- Pulls 1-3 (13 Nov) were identical (Google caches within a day); pull 4 (14 Nov) differs by about 1.5 index points on average, correlation at least 0.986, results unchanged.
- `pytrends` is an unofficial wrapper of the public Trends website; Google can break it or rate-limit it (we hit one stall). The official Trends API (alpha, consistent scaling, 5-year window) needs an application.
- Trends values pulled today are **not** the exact values a trader would have seen at the time (sampling + Google's methodology changes). Backtest is therefore optimistic on data vintage.
- SEC revenue is first-reported value (no restatements), so the target is point-in-time.
# StrandGlobal-Analysis-Search-Data
# StrandGlobal-Analysis-Search-Data
