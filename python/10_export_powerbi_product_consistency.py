"""
Stage 10: Export a product-level repeatability rollup for Power BI
Page 3 (Portfolio Patterns).

Input:  config.FINAL_FACT_CSV (fact_promotion_campaign_effects_v1.csv)
        data/processed/dim_promotion_campaign.csv (Stage 8 output)
Output: data/processed/fact_product_promotion_consistency.csv

Display-only aggregation. No causal estimate, validation result, FDR
correction, control match, threshold, or decision class is recomputed or
touched here -- this only counts and sums what Stage 7 already produced,
restricted to validation_status == "Valid" rows and grouped by
treated_upc, keeping only products with 2 or more valid campaigns.

The upstream decision_class values are relabeled for display only
(Keep -> Repeat, Kill -> Stop; Redesign and Monitor pass through
unchanged) so this table uses the same vocabulary as Pages 1-2. No new
consistency classification or business rule is introduced -- the table
exposes the raw per-product recommendation history so the viewer judges
repeatability directly.
"""
import os

import pandas as pd

from config import FINAL_FACT_CSV, PROCESSED_DIR

DIM_CAMPAIGN_CSV = os.path.join(PROCESSED_DIR, "dim_promotion_campaign.csv")
CONSISTENCY_CSV = os.path.join(PROCESSED_DIR, "fact_product_promotion_consistency.csv")

DECISION_LABEL = {
    "Keep": "Repeat",
    "Redesign": "Redesign",
    "Monitor": "Monitor",
    "Kill": "Stop",
}


def main():
    fact = pd.read_csv(FINAL_FACT_CSV)
    dim = pd.read_csv(DIM_CAMPAIGN_CSV)

    valid = fact[fact["validation_status"] == "Valid"].copy()
    valid = valid.merge(
        dim[["campaign_id", "product_name", "product_size"]],
        on="campaign_id", how="left",
    )
    valid["display_decision"] = valid["decision_class"].map(DECISION_LABEL)

    n_unmapped = int(valid["display_decision"].isna().sum())
    if n_unmapped:
        print(f"WARNING: {n_unmapped} valid campaign(s) have a decision_class outside "
              f"Keep/Redesign/Monitor/Kill and were not counted in any bucket.")

    agg = (
        valid.groupby(["treated_upc", "product_name", "product_size"])
        .agg(
            n_valid_campaigns=("campaign_id", "count"),
            n_repeat=("display_decision", lambda s: (s == "Repeat").sum()),
            n_redesign=("display_decision", lambda s: (s == "Redesign").sum()),
            n_monitor=("display_decision", lambda s: (s == "Monitor").sum()),
            n_stop=("display_decision", lambda s: (s == "Stop").sum()),
            total_incremental_margin=("incr_margin_total", "sum"),
            total_incremental_units=("incr_units_total", "sum"),
        )
        .reset_index()
    )

    out = agg[agg["n_valid_campaigns"] >= 2].copy()
    out = out.sort_values(
        ["n_valid_campaigns", "total_incremental_margin"], ascending=[False, False]
    ).reset_index(drop=True)

    out = out[[
        "treated_upc", "product_name", "product_size", "n_valid_campaigns",
        "n_repeat", "n_redesign", "n_monitor", "n_stop",
        "total_incremental_margin", "total_incremental_units",
    ]]

    # --- validation before export ---
    n_products = len(out)
    total_campaigns_represented = int(out["n_valid_campaigns"].sum())
    max_campaigns = int(out["n_valid_campaigns"].max()) if n_products else 0

    check_sum = out["n_repeat"] + out["n_redesign"] + out["n_monitor"] + out["n_stop"]
    n_failing = int((check_sum != out["n_valid_campaigns"]).sum())

    print(f"Products with 2+ valid campaigns: {n_products}")
    print(f"Total valid campaigns represented in this subset: {total_campaigns_represented}")
    print(f"Maximum valid campaigns for any one product: {max_campaigns}")
    print(f"Rows failing n_repeat+n_redesign+n_monitor+n_stop == n_valid_campaigns: {n_failing}")

    out.to_csv(CONSISTENCY_CSV, index=False)
    print(f"Wrote {CONSISTENCY_CSV}")


if __name__ == "__main__":
    main()