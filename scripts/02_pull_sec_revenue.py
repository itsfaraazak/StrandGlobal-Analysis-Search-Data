"""Pull reported quarterly revenue from SEC EDGAR XBRL 'companyfacts' (free).

Output: data/processed/revenue_quarterly.csv
  ticker, period_start, period_end, revenue, filed, form, source_concept, derived_q4

Point-in-time choice: for each fiscal period we keep the FIRST filed value
(as originally reported), not later restatements, and record its filing date.
Q4 is not filed as a quarter, so Q4 = annual (10-K) minus the three 10-Q quarters
of the same fiscal year; its 'filed' date is the 10-K date.
"""
import sys, time
import pandas as pd
import requests

sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
from config import FIRMS, SEC_TICKER, SEC_UA, DATA_RAW, DATA_OUT

H = {"User-Agent": SEC_UA}
CONCEPTS = [
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "Revenues",
    "SalesRevenueNet",
    "RevenueFromContractWithCustomerIncludingAssessedTax",
]


def cik_map():
    j = requests.get("https://www.sec.gov/files/company_tickers.json", headers=H).json()
    return {v["ticker"]: int(v["cik_str"]) for v in j.values()}


def facts_for(cik):
    url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"
    r = requests.get(url, headers=H)
    r.raise_for_status()
    return r.json()


def extract(j):
    gaap = j["facts"].get("us-gaap", {})
    frames = []
    for c in CONCEPTS:
        if c not in gaap or "USD" not in gaap[c]["units"]:
            continue
        d = pd.DataFrame(gaap[c]["units"]["USD"])
        d = d[d["form"].isin(["10-Q", "10-K", "10-Q/A", "10-K/A"])]
        d["concept"] = c
        frames.append(d)
    if not frames:
        return pd.DataFrame()
    d = pd.concat(frames)
    d["start"], d["end"], d["filed"] = (pd.to_datetime(d[k]) for k in ("start", "end", "filed"))
    d["days"] = (d["end"] - d["start"]).dt.days
    # Priority to concept order, then first filed
    d["prio"] = d["concept"].map({c: i for i, c in enumerate(CONCEPTS)})
    d = d.sort_values(["start", "end", "prio", "filed"])
    # Within one period, keep best concept; within concept keep first filing
    best = d.groupby(["start", "end"])["prio"].transform("min")
    d = d[d["prio"] == best].drop_duplicates(["start", "end"], keep="first")
    return d


def quarters(d):
    q = d[d["days"].between(80, 100)].copy()
    q["derived_q4"] = False
    a = d[d["days"].between(350, 380)]
    extra = []
    for _, row in a.iterrows():
        inside = q[(q["start"] >= row["start"]) & (q["end"] <= row["end"])]
        if len(inside) == 3:
            last_end = inside["end"].max()
            if (row["end"] - last_end).days < 80:
                continue
            extra.append({
                "start": last_end + pd.Timedelta(days=1), "end": row["end"],
                "val": row["val"] - inside["val"].sum(), "filed": row["filed"],
                "form": row["form"], "concept": row["concept"], "derived_q4": True,
            })
    q = pd.concat([q, pd.DataFrame(extra)], ignore_index=True)
    q = q.sort_values("end").drop_duplicates("end", keep="first")
    return q[["start", "end", "val", "filed", "form", "concept", "derived_q4"]]


def main():
    ciks = cik_map()
    out = []
    for tic in FIRMS:
        sec_tic = SEC_TICKER.get(tic, tic)
        cik = ciks.get(sec_tic)
        if cik is None:
            print("no CIK", tic); continue
        j = facts_for(cik)
        q = quarters(extract(j))
        q.insert(0, "ticker", tic)
        out.append(q)
        print(f"{tic:5s} cik={cik} quarters={len(q)} {q['end'].min().date()}..{q['end'].max().date()}")
        time.sleep(0.3)
    df = pd.concat(out).rename(columns={"start": "period_start", "end": "period_end",
                                         "val": "revenue", "concept": "source_concept"})
    df.to_csv(DATA_OUT / "revenue_quarterly.csv", index=False)


if __name__ == "__main__":
    main()
