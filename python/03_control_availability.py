"""
Stage 3: QA gate — verify every v1 campaign has enough eligible control UPCs
before building the matching logic. This is what caught, empirically, that
store-level control availability (checked in Stage 2) does NOT guarantee
product-level control availability, and is why the primary estimator is
within-store/cross-product rather than store-level matching.

Input:  config.DB_PATH (campaign_diagnostics, stg_sales)
Output: config.CONTROL_AVAILABILITY_CSV

Eligibility rule for a candidate control UPC (locked, Section 3):
  - present in >=6 of the 8 pre-treatment weeks in these specific stores
  - nonzero total activity in the pre-period (not a closed/inactive product)
  - nonzero variance in the pre-period (not a flat/degenerate series)
  - no recorded promotion of its own during this campaign's event window
"""
import duckdb
import pandas as pd
import numpy as np

from config import DB_PATH, CONTROL_AVAILABILITY_CSV, PRE_PERIOD_WEEKS


def main():
    con = duckdb.connect(DB_PATH)

    campaigns = con.execute("""
        SELECT campaign_id, upc AS treated_upc, event_start_week, event_end_week, participating_stores
        FROM campaign_diagnostics WHERE included_v1
    """).fetchdf()
    campaigns["pre_start"] = campaigns["event_start_week"] - PRE_PERIOD_WEEKS

    con.execute("CREATE OR REPLACE TABLE v1_campaigns AS SELECT * FROM campaigns")
    con.execute("""
        CREATE OR REPLACE TABLE v1_campaign_stores AS
        SELECT campaign_id, UNNEST(participating_stores) AS store FROM v1_campaigns
    """)
    # single bulk join across all campaigns — avoid one query per campaign, which does not scale
    con.execute("""
        CREATE OR REPLACE TABLE v1_scoped AS
        SELECT vcs.campaign_id, s.upc, s.week,
               SUM(s.units_sold) AS units,
               MAX(CASE WHEN s.is_promo_flagged THEN 1 ELSE 0 END) AS any_promo
        FROM v1_campaign_stores vcs
        JOIN v1_campaigns vc ON vcs.campaign_id = vc.campaign_id
        JOIN stg_sales s ON s.store = vcs.store AND s.week BETWEEN vc.pre_start AND vc.event_end_week
        GROUP BY 1,2,3
    """)
    scoped_all = con.execute("SELECT * FROM v1_scoped").fetchdf()
    con.close()

    records = []
    for _, camp in campaigns.iterrows():
        cid = int(camp["campaign_id"]); upc = camp["treated_upc"]
        start, end = int(camp["event_start_week"]), int(camp["event_end_week"])
        pre_weeks = list(range(start - PRE_PERIOD_WEEKS, start))

        scoped = scoped_all[scoped_all["campaign_id"] == cid]
        promoted_in_window = set(scoped.loc[(scoped["week"].between(start, end)) & (scoped["any_promo"] == 1), "upc"])
        all_upcs = set(scoped["upc"])
        candidates = all_upcs - {upc} - promoted_in_window

        presence = scoped[scoped["week"].isin(pre_weeks)].groupby("upc")["week"].nunique()
        pre = scoped[scoped["week"].isin(pre_weeks)]

        eligible = 0
        for c in candidates:
            cser = pre[pre["upc"] == c]["units"]
            if presence.get(c, 0) >= 6 and cser.sum() > 0 and cser.std() > 0:
                eligible += 1

        records.append((cid, len(candidates), eligible))

    out = pd.DataFrame(records, columns=["campaign_id", "raw_candidates", "eligible_control_upcs"])
    out.to_csv(CONTROL_AVAILABILITY_CSV, index=False)

    print(out["eligible_control_upcs"].describe())
    print(f"Campaigns with <3 eligible control UPCs: {(out['eligible_control_upcs'] < 3).sum()} / {len(out)}")


if __name__ == "__main__":
    main()