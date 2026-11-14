"""Build the Google Trends revenue signal and test it against a naive baseline.

Signal (per firm i, fiscal quarter q), using ONLY Trends data dated inside the
fiscal quarter, i.e. known ~2 days after quarter end and weeks before earnings:

    svi_yoy[i,q]  = log(1+SVI[i,q]) - log(1+SVI[i,q-4])        (seasonally adjusted)
    dsig[i,q]     = svi_yoy[i,q] - svi_yoy[i,q-1]               (acceleration)

Target:
    g[i,q]        = log(Rev[i,q] / Rev[i,q-4])                  (reported YoY growth)
    baseline      = g[i,q-1]   (last reported YoY growth: "growth persists")
    surprise      = g[i,q] - g[i,q-1]                           (vs baseline)

Question: does dsig predict the surprise, i.e. add information beyond the baseline?

Outputs in output/: panel.csv, results.txt, per_firm.csv, charts.
"""
import sys, glob
import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
from config import FIRMS, DATA_RAW, DATA_OUT, OUTPUT

LOG = []
def log(*a):
    s = " ".join(str(x) for x in a)
    print(s); LOG.append(s)


# ---------- load Trends (average across repeated pulls) ----------
pulls = sorted(glob.glob(str(DATA_RAW / "trends_monthly_pull*.csv")))
tr = []
for k, f in enumerate(pulls, 1):
    d = pd.read_csv(f, parse_dates=["date"])
    d = d[~d["is_partial"]]
    d["pull"] = k
    tr.append(d)
tr = pd.concat(tr)
wide = tr.pivot_table(index=["ticker", "date"], columns="pull", values="svi")
svi = wide.mean(axis=1).rename("svi").reset_index()

# Sampling noise across pulls
if wide.shape[1] > 1:
    lw = np.log1p(wide)
    corr = lw.groupby(level=0).apply(lambda x: x.corr().values[np.triu_indices(x.shape[1], 1)].mean())
    mad = (wide.max(axis=1) - wide.min(axis=1)).groupby(level=0).mean()
    log(f"Trends pulls: {len(pulls)}. Mean pairwise corr of log(1+SVI) across pulls by firm:")
    log(pd.DataFrame({"corr": corr.round(3), "mean_range_pts": mad.round(2)}).to_string())

# ---------- load revenue ----------
rv = pd.read_csv(DATA_OUT / "revenue_quarterly.csv", parse_dates=["period_start", "period_end", "filed"])
rv = rv.sort_values(["ticker", "period_end"])
# drop near-duplicate quarters (52/53-week calendars giving ends 1 day apart)
rv["gap"] = rv.groupby("ticker")["period_end"].diff().dt.days
rv = rv[~(rv["gap"] < 20)].drop(columns="gap")


def build_panel(svi, rv):
    def quarter_svi(row):
        """Mean monthly SVI for months whose mid-point falls inside the fiscal quarter."""
        s = svi[svi["ticker"] == row.ticker]
        mid = s["date"] + pd.Timedelta(days=14)
        m = s[(mid >= row.period_start) & (mid <= row.period_end)]
        return m["svi"].mean() if len(m) >= 2 else np.nan

    def lagk(df, col, k):
        """Lag by k quarters, requiring the lagged quarter to end ~k*91 days earlier."""
        out = df.groupby("ticker")[col].shift(k)
        days = (df["period_end"] - df.groupby("ticker")["period_end"].shift(k)).dt.days
        return out.where(days.between(91 * k - 20, 91 * k + 20))

    p = rv.copy()
    p["svi_q"] = p.apply(quarter_svi, axis=1)
    p = p.dropna(subset=["svi_q"]).sort_values(["ticker", "period_end"]).reset_index(drop=True)
    p["g"] = np.log(p["revenue"] / lagk(p, "revenue", 4))
    p["svi_yoy"] = np.log1p(p["svi_q"]) - np.log1p(lagk(p, "svi_q", 4))
    p["g_prev"] = lagk(p, "g", 1)
    p["svi_yoy_prev"] = lagk(p, "svi_yoy", 1)
    p["surprise"] = p["g"] - p["g_prev"]
    p["dsig"] = p["svi_yoy"] - p["svi_yoy_prev"]
    p["covid"] = p["period_end"].between("2020-03-01", "2021-12-31")
    p["pod"] = p["ticker"].map({k: v[1] for k, v in FIRMS.items()})
    p["qid"] = p["period_end"].dt.to_period("Q").astype(str)
    return p


p = build_panel(svi, rv)
p.to_csv(OUTPUT / "panel.csv", index=False)

m = p.dropna(subset=["surprise", "dsig", "g_prev", "svi_yoy"]).copy()
# winsorise at 1/99% to limit influence of e.g. Peloton 2020-21
for c in ["surprise", "dsig", "g", "g_prev", "svi_yoy"]:
    lo, hi = m[c].quantile([0.01, 0.99])
    m[c + "_w"] = m[c].clip(lo, hi)
log(f"\nPanel: {len(m)} firm-quarters, {m['ticker'].nunique()} firms, "
    f"{m['period_end'].min().date()} to {m['period_end'].max().date()}")


def fit(formula, data, label):
    groups = pd.factorize(data["ticker"])[0]
    r1 = smf.ols(formula, data).fit(cov_type="cluster", cov_kwds={"groups": groups})
    g2 = np.column_stack([groups, pd.factorize(data["qid"])[0]])
    r2 = smf.ols(formula, data).fit(cov_type="cluster", cov_kwds={"groups": g2})
    v = [x for x in r1.params.index if "dsig" in x or "svi_yoy" in x][0]
    log(f"{label:55s} n={int(r1.nobs):4d} beta={r1.params[v]: .3f} "
        f"t(firm)={r1.tvalues[v]: .2f} t(firm+qtr)={r2.tvalues[v]: .2f} R2={r1.rsquared:.3f}")
    return r1


log("\n=== In-sample: does the Trends signal predict revenue growth vs. baseline? ===")
fit("surprise_w ~ dsig_w", m, "A. surprise ~ dsig (all)")
fit("surprise_w ~ dsig_w", m[~m.covid], "B. surprise ~ dsig (ex Covid 2020-21)")
fit("surprise_w ~ dsig_w + C(qid)", m, "C. surprise ~ dsig + quarter FE (cross-sectional)")
fit("g_w ~ g_prev_w + svi_yoy_w", m, "D. g ~ g_prev + svi_yoy (levels)")
fit("g_w ~ g_prev_w + svi_yoy_w + C(ticker)", m, "E. g ~ g_prev + svi_yoy + firm FE")
for pod in ["Consumer", "TMT"]:
    fit("surprise_w ~ dsig_w", m[m.pod == pod], f"F. surprise ~ dsig, {pod} only")

# ---------- out-of-sample, expanding window ----------
log("\n=== Out-of-sample (expanding window, refit each quarter) ===")
m = m.sort_values("period_end")
dates = sorted(m.loc[m.period_end >= "2021-01-01", "qid"].unique())
preds = []
for q in dates:
    test = m[m.qid == q]
    cutoff = test["period_end"].min() - pd.Timedelta(days=80)  # train only on quarters already reported
    train = m[m.period_end <= cutoff]
    if len(train) < 40:
        continue
    r = smf.ols("surprise_w ~ dsig_w", train).fit()
    t = test.copy()
    t["pred_surprise"] = r.predict(t)
    preds.append(t)
oos = pd.concat(preds)
oos["err_base"] = oos["surprise"]                       # baseline predicts surprise = 0
oos["err_model"] = oos["surprise"] - oos["pred_surprise"]
d = oos["err_base"] ** 2 - oos["err_model"] ** 2
rmse_b, rmse_m = np.sqrt((oos.err_base ** 2).mean()), np.sqrt((oos.err_model ** 2).mean())
mae_b, mae_m = oos.err_base.abs().mean(), oos.err_model.abs().mean()
# Diebold-Mariano style: cluster the loss differential by quarter
dm = smf.ols("d ~ 1", pd.DataFrame({"d": d, "q": oos.qid})).fit(
    cov_type="cluster", cov_kwds={"groups": pd.factorize(oos.qid)[0]})
hit = (np.sign(oos.dsig) == np.sign(oos.surprise)).mean()
log(f"OOS firm-quarters: {len(oos)} ({oos.qid.min()} to {oos.qid.max()})")
log(f"RMSE baseline {rmse_b:.4f} | baseline+Trends {rmse_m:.4f} | improvement {(1-rmse_m/rmse_b)*100:.1f}%")
log(f"MAE  baseline {mae_b:.4f} | baseline+Trends {mae_m:.4f} | improvement {(1-mae_m/mae_b)*100:.1f}%")
log(f"Loss-differential t-stat (quarter-clustered): {dm.tvalues['Intercept']:.2f}")
log(f"Directional hit rate sign(dsig)==sign(surprise): {hit:.1%} (50% = coin flip)")

oos_x = oos[~oos.covid]
hit_x = (np.sign(oos_x.dsig) == np.sign(oos_x.surprise)).mean()
r_b = np.sqrt((oos_x.err_base**2).mean()); r_m = np.sqrt((oos_x.err_model**2).mean())
log(f"Ex-Covid OOS ({len(oos_x)}): RMSE improvement {(1-r_m/r_b)*100:.1f}%, hit rate {hit_x:.1%}")
oos.to_csv(OUTPUT / "oos_predictions.csv", index=False)

# Robustness 1: same OOS, but never train on Covid quarters, evaluate ex-Covid
preds = []
for q in dates:
    test = m[(m.qid == q) & (~m.covid)]
    if test.empty:
        continue
    cutoff = test["period_end"].min() - pd.Timedelta(days=80)
    train = m[(m.period_end <= cutoff) & (~m.covid)]
    if len(train) < 40:
        continue
    r = smf.ols("surprise_w ~ dsig_w", train).fit()
    t = test.copy(); t["pred_surprise"] = r.predict(t); preds.append(t)
o2 = pd.concat(preds)
e_b, e_m = o2.surprise, o2.surprise - o2.pred_surprise
dd = e_b**2 - e_m**2
dm2 = smf.ols("d ~ 1", pd.DataFrame({"d": dd, "q": o2.qid})).fit(
    cov_type="cluster", cov_kwds={"groups": pd.factorize(o2.qid)[0]})
log(f"Robustness - train & test ex-Covid ({len(o2)}, {o2.qid.min()}-{o2.qid.max()}): "
    f"RMSE improvement {(1-np.sqrt((e_m**2).mean())/np.sqrt((e_b**2).mean()))*100:.1f}%, "
    f"MAE improvement {(1-e_m.abs().mean()/e_b.abs().mean())*100:.1f}%, DM t={dm2.tvalues['Intercept']:.2f}")

# Robustness 2: cross-sectional rank IC per quarter (no parameters fitted at all)
ics = []
for q, g in m.groupby("qid"):
    if len(g) >= 8:
        ics.append({"qid": q, "ic": g["dsig"].rank().corr(g["surprise"].rank()), "n": len(g),
                    "covid": g["covid"].any()})
ic = pd.DataFrame(ics)
for lab, sub in [("all", ic), ("ex-Covid", ic[~ic.covid])]:
    tstat = sub.ic.mean() / (sub.ic.std(ddof=1) / np.sqrt(len(sub)))
    log(f"Rank IC (Spearman dsig vs surprise, per quarter, {lab}): mean {sub.ic.mean():.3f}, "
        f"t={tstat:.2f}, quarters={len(sub)}, share>0 {(sub.ic>0).mean():.0%}")
ic.to_csv(OUTPUT / "rank_ic_by_quarter.csv", index=False)


def mean_ic(df):
    v = [g["dsig"].rank().corr(g["surprise"].rank()) for _, g in df.groupby("qid") if len(g) >= 8]
    return np.mean(v), np.mean(v) / (np.std(v, ddof=1) / np.sqrt(len(v)))


mx = m[~m.covid]
loo = {t: mean_ic(mx[mx.ticker != t])[0] for t in mx.ticker.unique()}
log(f"Leave-one-firm-out ex-Covid rank IC: min {min(loo.values()):.3f} (drop {min(loo, key=loo.get)}), "
    f"max {max(loo.values()):.3f}")
ic3, t3 = mean_ic(mx[~mx.ticker.isin(["ETSY", "WAYF", "PTON"])])
log(f"Ex-Covid rank IC without ETSY, WAYF, PTON (Covid e-com winners): {ic3:.3f}, t={t3:.2f}")
ic4, t4 = mean_ic(m[m.period_end >= "2023-01-01"])
log(f"Rank IC 2023+ only: {ic4:.3f}, t={t4:.2f}")

# ---------- per-firm ----------
rows = []
for tic, g in m.groupby("ticker"):
    rows.append({"ticker": tic, "keyword": FIRMS[tic][0], "pod": FIRMS[tic][1], "n": len(g),
                 "corr_level(svi_yoy,g)": round(g["svi_yoy"].corr(g["g"]), 2),
                 "corr_change(dsig,surprise)": round(g["dsig"].corr(g["surprise"]), 2),
                 "hit_rate": round((np.sign(g.dsig) == np.sign(g.surprise)).mean(), 2),
                 "mapping_note": FIRMS[tic][2]})
pf = pd.DataFrame(rows).sort_values("corr_change(dsig,surprise)", ascending=False)
pf.to_csv(OUTPUT / "per_firm.csv", index=False)
log("\n=== Per firm ===")
log(pf.drop(columns="mapping_note").to_string(index=False))

log("\n=== Sampling-noise robustness: rerun on each Trends pull separately ===")
for k in sorted(tr["pull"].unique()):
    sk = tr[tr["pull"] == k][["ticker", "date", "svi"]]
    pk = build_panel(sk, rv).dropna(subset=["surprise", "dsig"])
    pk = pk[~pk.covid]
    rk = smf.ols("surprise ~ dsig", pk).fit(cov_type="cluster", cov_kwds={"groups": pd.factorize(pk.ticker)[0]})
    ick = [g["dsig"].rank().corr(g["surprise"].rank()) for _, g in pk.groupby("qid") if len(g) >= 8]
    log(f"pull {k}: ex-Covid n={len(pk)} beta={rk.params['dsig']:.3f} t={rk.tvalues['dsig']:.2f} "
        f"mean rank IC={np.mean(ick):.3f}")

(OUTPUT / "results.txt").write_text("\n".join(LOG))

# ---------- charts ----------
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ex = p[p.ticker == "DUOL"].dropna(subset=["g", "svi_yoy"])
fig, ax = plt.subplots(figsize=(8, 4))
ax.plot(ex.period_end, ex.g * 100, marker="o", label="Reported revenue growth YoY (SEC)")
ax.plot(ex.period_end, ex.svi_yoy * 100, marker="s", label="Google Trends 'duolingo' YoY (US)")
ax.axhline(0, color="grey", lw=0.5)
ax.set_ylabel("log change x100 (~%)"); ax.set_title("Duolingo: search interest vs reported revenue growth")
ax.legend(); fig.autofmt_xdate(); fig.tight_layout()
fig.savefig(OUTPUT / "duol_trends_vs_revenue.png", dpi=150)

fig, ax = plt.subplots(figsize=(5, 4))
ax.scatter(m.dsig_w, m.surprise_w, s=10, alpha=0.5)
b = np.polyfit(m.dsig_w, m.surprise_w, 1)
xs = np.linspace(m.dsig_w.min(), m.dsig_w.max(), 10)
ax.plot(xs, np.polyval(b, xs), color="C1")
ax.set_xlabel("Change in Trends YoY (dsig)"); ax.set_ylabel("Revenue growth surprise vs baseline")
ax.set_title(f"All firms, n={len(m)}"); fig.tight_layout()
fig.savefig(OUTPUT / "pooled_scatter.png", dpi=150)
print("charts saved")
