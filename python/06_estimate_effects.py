"""
Stage 6: Per-campaign event-study estimation.

Input:  config.MAIN_PANEL_PKL, config.CANN_PANEL_PKL, fs_campaigns.pkl (Stage 5 outputs)
Output: config.ESTIMATION_RESULTS_CSV

For each campaign:
  - DiD regression: units ~ is_treated * post, and margin ~ is_treated * post,
    both with store-clustered standard errors (long-format panel: treated UPC
    rows vs. mean-of-K10-controls rows, per store-week).
  - Pretrend test: same specification restricted to the pre-period only, with
    a linear time trend interacted with is_treated — a significant interaction
    means the parallel-trends assumption does not hold pre-treatment.
  - Placebo test: fake treatment date at the pre-period midpoint, same DiD
    specification restricted to pre-period data only — a significant "effect"
    here means the design detects spurious effects even with no real
    treatment.
  - Cannibalization: aggregate the same-commodity-code peer group into ONE
    series and take a single net pre-vs-post change (floored at zero). Do
    NOT sum per-product declines across the peer set — with a large peer
    group, roughly half of any set of products will show some decline from
    pure week-to-week noise, and summing only the negative ones is a
    selection bias that inflates the metric regardless of whether real
    cannibalization occurred. This was caught during validation on a 6-
    campaign sample before scaling; keep it fixed this way.
  - gross_cannibalization_rate is undefined (None) whenever incremental
    units <= 0 — the ratio has no valid interpretation without positive
    gross lift to attribute cannibalization against. Also guards against the
    ratio falling outside [0,1].

The DiD coefficient is a PER-STORE-WEEK effect; incr_units_total and
incr_margin_total scale it up by (n_participating_stores x event_length_weeks)
to report a total-across-stores figure that's on the same scale as the
cannibalization metric.
"""
import warnings

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

from config import MAIN_PANEL_PKL, CANN_PANEL_PKL, ESTIMATION_RESULTS_CSV, PRE_PERIOD_WEEKS

warnings.filterwarnings("ignore")

CAMPAIGNS_PKL = MAIN_PANEL_PKL.replace("fs_main_panel.pkl", "fs_campaigns.pkl")


def _did(panel: pd.DataFrame, outcome: str):
    try:
        m = smf.ols(f"{outcome} ~ is_treated * post", data=panel).fit(
            cov_type="cluster", cov_kwds={"groups": panel["store"]}
        )
        coef = m.params.get("is_treated:post", np.nan)
        lo, hi = m.conf_int().loc["is_treated:post"] if "is_treated:post" in m.params.index else (np.nan, np.nan)
        p = m.pvalues.get("is_treated:post", np.nan)
        return coef, lo, hi, p
    except Exception:
        return np.nan, np.nan, np.nan, np.nan


def _pretrend(panel_pre: pd.DataFrame, outcome: str):
    try:
        p2 = panel_pre.copy()
        p2["t"] = p2["week"] - p2["week"].min()
        m = smf.ols(f"{outcome} ~ is_treated * t", data=p2).fit(cov_type="cluster", cov_kwds={"groups": p2["store"]})
        p = m.pvalues.get("is_treated:t", np.nan)
        return p, (p > 0.05 if not np.isnan(p) else False)
    except Exception:
        return np.nan, False


def _placebo(panel_pre: pd.DataFrame, outcome: str):
    weeks = sorted(panel_pre["week"].unique())
    if len(weeks) < 4:
        return np.nan, False
    try:
        fake_start = weeks[len(weeks) // 2]
        p2 = panel_pre.copy()
        p2["post"] = (p2["week"] >= fake_start).astype(int)
        m = smf.ols(f"{outcome} ~ is_treated * post", data=p2).fit(cov_type="cluster", cov_kwds={"groups": p2["store"]})
        p = m.pvalues.get("is_treated:post", np.nan)
        return p, (p > 0.05 if not np.isnan(p) else False)
    except Exception:
        return np.nan, False


def main():
    main_panel = pd.read_pickle(MAIN_PANEL_PKL)
    cann_panel = pd.read_pickle(CANN_PANEL_PKL)
    campaigns = pd.read_pickle(CAMPAIGNS_PKL)

    results = []
    for _, camp in campaigns.iterrows():
        cid = int(camp["campaign_id"]); upc = camp["treated_upc"]
        start, end = int(camp["event_start_week"]), int(camp["event_end_week"])
        stores = camp["participating_stores"]; n_stores = len(stores)

        raw = main_panel[main_panel["campaign_id"] == cid]
        if raw.empty:
            continue
        treated_rows = raw[raw["upc"] == upc][["store", "week", "units", "margin"]]
        control_rows = (
            raw[raw["upc"] != upc]
            .groupby(["store", "week"], as_index=False)
            .agg(units=("units", "mean"), margin=("margin", "mean"))
        )
        if treated_rows.empty or control_rows.empty:
            continue
        treated_rows["is_treated"] = 1
        control_rows["is_treated"] = 0
        panel = pd.concat([treated_rows, control_rows], ignore_index=True)
        panel["post"] = (panel["week"] >= start).astype(int)
        panel_pre = panel[panel["week"] < start]

        u_coef, u_lo, u_hi, u_p = _did(panel, "units")
        m_coef, m_lo, m_hi, m_p = _did(panel, "margin")
        pt_p, pt_pass = _pretrend(panel_pre, "units")
        pb_p, pb_pass = _placebo(panel_pre, "units")

        incr_units_total = u_coef * n_stores * (end - start + 1) if not np.isnan(u_coef) else np.nan
        incr_margin_total = m_coef * n_stores * (end - start + 1) if not np.isnan(m_coef) else np.nan

        cp = cann_panel[cann_panel["campaign_id"] == cid]
        pre_avg = cp.loc[cp["week"] < start, "peer_units"].mean()
        post_avg = cp.loc[cp["week"] >= start, "peer_units"].mean()
        net_change = (post_avg - pre_avg) if not (np.isnan(pre_avg) or np.isnan(post_avg)) else np.nan
        cannibalized_units = max(0, -net_change) * (end - start + 1) if not np.isnan(net_change) else np.nan

        if np.isnan(incr_units_total) or incr_units_total <= 0:
            gcr = None  # undefined without positive gross lift to attribute cannibalization against
        else:
            denom = incr_units_total + (cannibalized_units if not np.isnan(cannibalized_units) else 0)
            gcr = (cannibalized_units / denom) if denom > 0 else 0.0
            gcr = gcr if (gcr is not None and 0 <= gcr <= 1.0) else None

        results.append({
            "campaign_id": cid, "treated_upc": upc, "n_stores": n_stores,
            "incr_units_total": incr_units_total, "units_ci_lo": u_lo, "units_ci_hi": u_hi, "units_p": u_p,
            "incr_margin_total": incr_margin_total, "margin_ci_lo": m_lo, "margin_ci_hi": m_hi, "margin_p": m_p,
            "pretrend_p": pt_p, "pretrend_pass": pt_pass, "placebo_p": pb_p, "placebo_pass": pb_pass,
            "cannibalized_units_total": cannibalized_units, "gross_cannibalization_rate": gcr,
        })

    out = pd.DataFrame(results)
    out.to_csv(ESTIMATION_RESULTS_CSV, index=False)
    print(f"Estimated {len(out)} / {len(campaigns)} campaigns.")
    print(f"Regression failures (NaN units coefficient): {out['incr_units_total'].isna().sum()}")


if __name__ == "__main__":
    main()