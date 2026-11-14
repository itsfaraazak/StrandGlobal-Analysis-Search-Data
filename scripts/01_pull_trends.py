"""Pull Google Trends search interest (US) for each firm keyword.

Output: data/raw/trends_monthly_pull{N}.csv  (long format, one row per month x keyword)
        data/raw/trends_weekly_5y_DUOL.csv  (weekly example series)

Notes
- Uses pytrends (unofficial wrapper of the public Trends website endpoint).
  The official Trends API is alpha / application-only (see note).
- Each keyword is pulled ALONE, so each series is scaled 0-100 to its own peak.
  This is fine because the signal only uses log changes within a series.
- A window longer than ~5 years returns MONTHLY data; we use 2016-01 -> today.
- Trends values are a sample of searches, so repeated pulls can differ.
  We pull N times to measure that sampling noise.
"""
import sys, time, random, datetime as dt
import pandas as pd
from pytrends.request import TrendReq

sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
from config import FIRMS, GEO, TRENDS_START, DATA_RAW

N_PULLS = int(sys.argv[1]) if len(sys.argv) > 1 else 3
START = int(sys.argv[2]) if len(sys.argv) > 2 else 1  # resume from pull number
today = dt.date.today().isoformat()
timeframe = f"{TRENDS_START} {today}"


def pull(pt, kw, tf):
    for attempt in range(6):
        try:
            pt.build_payload([kw], timeframe=tf, geo=GEO)
            df = pt.interest_over_time()
            if df.empty:
                raise RuntimeError("empty response")
            return df
        except Exception as e:  # 429s are common; back off
            wait = 20 * (attempt + 1) + random.uniform(0, 10)
            print(f"  {kw}: {e!r}; retry in {wait:.0f}s", flush=True)
            time.sleep(wait)
    raise RuntimeError(f"failed: {kw}")


def main():
    pt = TrendReq(hl="en-US", tz=0, timeout=(10, 30))
    for n in range(START, N_PULLS + 1):
        rows = []
        for tic, (kw, _, _) in FIRMS.items():
            df = pull(pt, kw, timeframe)
            out = df[[kw]].rename(columns={kw: "svi"}).reset_index()
            out["ticker"], out["keyword"] = tic, kw
            out["is_partial"] = df["isPartial"].values
            out["pulled_at_utc"] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
            rows.append(out)
            print(f"pull {n} {tic:5s} {kw:15s} {len(out)} rows", flush=True)
            time.sleep(random.uniform(6, 12))
        pd.concat(rows).to_csv(DATA_RAW / f"trends_monthly_pull{n}.csv", index=False)
        if n < N_PULLS:
            time.sleep(60)

    # Weekly example series for the worked example company
    df = pull(pt, "duolingo", "today 5-y")
    df.reset_index().to_csv(DATA_RAW / "trends_weekly_5y_DUOL.csv", index=False)
    print("done", flush=True)


if __name__ == "__main__":
    main()
