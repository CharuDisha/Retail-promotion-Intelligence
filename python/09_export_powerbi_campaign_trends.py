"""
Stage 9: Export a compact, display-only weekly trend table for Power BI
Page 2 (Campaign Deep Dive).

Input:  config.MAIN_PANEL_PKL (fs_main_panel.pkl), fs_campaigns.pkl
        (both Stage 5 outputs — not re-pulled, not re-derived)
Output: data/processed/fact_campaign_weekly_trends.csv

For each of the 236 locked v1 campaigns, this reduces the store-week
estimation panel down to two weekly series per campaign:

  Treated         = mean(units) of the treated UPC, across participating
                    stores, per week.
  Matched Control = Stage 6's exact two-stage average — first the K=10
                    control UPCs are averaged within each (store, week)
                    [reproducing 06_event_study_estimation.py's
                    `control_rows` construction exactly], then those
                    per-store-week control averages are averaged again
                    across stores, per week.

This is NOT a re-estimation. No DiD coefficient, no significance test, no
confidence interval, no cannibalization, no decision class is computed or
touched here — it exists only so Power BI can draw the observed treated
vs. matched-control weekly trajectory for a campaign the user selects.
Stages 0-8 and their outputs are untouched.

The output only contains weeks already present in fs_main_panel, i.e. each
campaign's pre_start (event_start_week - PRE_PERIOD_WEEKS) through
event_end_week window — the same pre-treatment + campaign window Stage 5
pulled. No new week range is invented here.
"""
import os

import pandas as pd

from config import MAIN_PANEL_PKL, PROCESSED_DIR

CAMPAIGNS_PKL = MAIN_PANEL_PKL.replace("fs_main_panel.pkl", "fs_campaigns.pkl")
TRENDS_CSV = os.path.join(PROCESSED_DIR, "fact_campaign_weekly_trends.csv")


def build_campaign_trend(raw: pd.DataFrame, cid: int, upc, start: int, end: int) -> pd.DataFrame:
    """Reproduce Stage 6's treated/control construction, then reduce to
    one row per (week, series) for display. `raw` is fs_main_panel already
    filtered to this campaign_id."""
    treated = raw[raw["upc"] == upc][["store", "week", "units"]]
    treated_weekly = (
        treated.groupby("week", as_index=False)["units"].mean()
        .rename(columns={"units": "avg_units"})
    )
    treated_weekly["series"] = "Treated"

    # Stage 6 control construction, unchanged: average the K=10 control
    # UPCs within each (store, week) first.
    control_store_week = (
        raw[raw["upc"] != upc]
        .groupby(["store", "week"], as_index=False)["units"].mean()
    )
    # Display-only second stage: average those store-week control values
    # across stores, per week.
    control_weekly = (
        control_store_week.groupby("week", as_index=False)["units"].mean()
        .rename(columns={"units": "avg_units"})
    )
    control_weekly["series"] = "Matched Control"

    out = pd.concat([treated_weekly, control_weekly], ignore_index=True)
    if out.empty:
        return out

    out["campaign_id"] = cid
    out["relative_week"] = out["week"] - start
    out["is_promotion_week"] = out["week"].between(start, end)
    return out[["campaign_id", "week", "relative_week", "series", "avg_units", "is_promotion_week"]]


def main():
    main_panel = pd.read_pickle(MAIN_PANEL_PKL)
    campaigns = pd.read_pickle(CAMPAIGNS_PKL)

    frames = []
    for _, camp in campaigns.iterrows():
        cid = int(camp["campaign_id"])
        upc = camp["treated_upc"]
        start, end = int(camp["event_start_week"]), int(camp["event_end_week"])

        raw = main_panel[main_panel["campaign_id"] == cid]
        if raw.empty:
            continue

        trend = build_campaign_trend(raw, cid, upc, start, end)
        if not trend.empty:
            frames.append(trend)

    out = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(
        columns=["campaign_id", "week", "relative_week", "series", "avg_units", "is_promotion_week"]
    )
    out = out.sort_values(["campaign_id", "series", "week"]).reset_index(drop=True)

    # --- validation before export ---
    n_rows = len(out)
    campaigns_represented = out["campaign_id"].nunique()
    n_total_campaigns = campaigns["campaign_id"].nunique()
    missing_campaigns = sorted(set(campaigns["campaign_id"]) - set(out["campaign_id"]))

    dupe_mask = out.duplicated(subset=["campaign_id", "week", "series"], keep=False)
    n_dupes = int(dupe_mask.sum())

    series_per_campaign = out.groupby("campaign_id")["series"].nunique()
    incomplete_series = series_per_campaign[series_per_campaign != 2]

    print(f"Rows written: {n_rows:,}")
    print(f"Distinct campaigns represented: {campaigns_represented} / {n_total_campaigns}")
    print(f"Duplicate campaign_id+week+series rows: {n_dupes}")
    if missing_campaigns:
        print(f"WARNING: {len(missing_campaigns)} campaign(s) have no rows at all "
              f"(no fs_main_panel data): {missing_campaigns}")
    if len(incomplete_series):
        print(f"WARNING: {len(incomplete_series)} campaign(s) do not have exactly two series "
              f"(Treated + Matched Control): {incomplete_series.to_dict()}")

    out.to_csv(TRENDS_CSV, index=False)
    print(f"Wrote {TRENDS_CSV}")


if __name__ == "__main__":
    main()