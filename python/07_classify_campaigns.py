"""
Stage 7: BH-FDR correction and upstream campaign classification.

Input:  config.ESTIMATION_RESULTS_CSV
Output: config.FINAL_FACT_CSV  ==>  fact_promotion_campaign_effects_v1.csv

Two SEPARATE Benjamini-Hochberg corrections — one for the units test family,
one for the margin test family. Do not share a single q-value across both
outcomes; they are different hypotheses and must be corrected independently
(Section 6 of the locked plan).

Classification logic (Section 9), evaluated in this order:
  1. Exclude  — pretrend or placebo validation failed. A campaign that fails
     causal validation is NEVER classified Kill — an invalid estimate is not
     evidence the promotion was bad, it is evidence the estimate can't be
     trusted.
  2. Keep     — valid, units AND margin both significant and positive
     (q <= alpha, CI entirely on the positive side), cannibalization within
     threshold.
  3. Kill     — valid, units AND margin both significant and negative.
  4. Redesign — valid but a clear economic trade-off: volume up/margin down,
     or margin positive but cannibalization exceeds the threshold. Reason
     text is branch-specific — do not use one generic string for every
     Redesign case, since "drives volume but loses margin" and "cannibalizes
     too much" call for different merchandising actions.
  5. Monitor  — valid but not statistically decisive on units and/or margin
     after FDR correction.

Power BI (or any BI tool) should only read this file's columns — filter,
rank, and visualize. No re-estimation or re-classification belongs in the
BI layer.
"""
import numpy as np
import pandas as pd
from statsmodels.stats.multitest import multipletests

from config import ESTIMATION_RESULTS_CSV, FINAL_FACT_CSV, FDR_ALPHA, KEEP_CANNIBALIZATION_MAX


def classify(row: pd.Series) -> tuple[str, str, str]:
    """Returns (decision_class, confidence_tier, decision_reason)."""
    if row["pretrend_pass"] is not True or row["placebo_pass"] is not True:
        return "Exclude", "X", "Pre-trend or placebo validation failed."

    units_sig = pd.notna(row["qvalue_units"]) and row["qvalue_units"] <= FDR_ALPHA
    margin_sig = pd.notna(row["qvalue_margin"]) and row["qvalue_margin"] <= FDR_ALPHA
    units_pos = units_sig and row["units_ci_lo"] > 0
    units_neg = units_sig and row["units_ci_hi"] < 0
    margin_pos = margin_sig and row["margin_ci_lo"] > 0
    margin_neg = margin_sig and row["margin_ci_hi"] < 0

    cann = row["gross_cannibalization_rate"]
    cann_ok = pd.isna(cann) or cann <= KEEP_CANNIBALIZATION_MAX

    if units_pos and margin_pos and cann_ok:
        return "Keep", "A", "Validated, incremental units and margin are both decisively positive with acceptable cannibalization."

    if units_neg and margin_neg:
        return "Kill", "D", "Validated and confidently negative on both units and margin."

    if units_pos and margin_neg:
        return "Redesign", "B", (
            f"Drives volume but loses margin (${row['incr_margin_total']:,.0f}) "
            f"— review discount depth, cost structure, or eligible assortment."
        )

    if units_pos and margin_pos and not cann_ok:
        return "Redesign", "B", (
            f"Positive on both metrics but cannibalization ({cann:.0%}) "
            f"exceeds threshold — narrow the product/store scope."
        )

    return "Monitor", "C", "Validated but not statistically decisive on units and/or margin after FDR correction."


def main():
    df = pd.read_csv(ESTIMATION_RESULTS_CSV)

    valid_p_units = df["units_p"].dropna()
    valid_p_margin = df["margin_p"].dropna()
    _, q_units, _, _ = multipletests(valid_p_units, method="fdr_bh")
    _, q_margin, _, _ = multipletests(valid_p_margin, method="fdr_bh")
    df.loc[valid_p_units.index, "qvalue_units"] = q_units
    df.loc[valid_p_margin.index, "qvalue_margin"] = q_margin

    df["pretrend_pass"] = df["pretrend_pass"].map({"True": True, "False": False, True: True, False: False})
    df["placebo_pass"] = df["placebo_pass"].map({"True": True, "False": False, True: True, False: False})
    df["validation_status"] = np.where(df["pretrend_pass"] & df["placebo_pass"], "Valid", "Invalid")

    df[["decision_class", "confidence_tier", "decision_reason"]] = df.apply(
        lambda r: pd.Series(classify(r)), axis=1
    )

    # transparent priority ordering — no opaque weighted composite score.
    # Sort key: decision class (Keep first, Exclude last), then margin $ desc, then units desc.
    decision_order = {"Keep": 1, "Redesign": 2, "Monitor": 3, "Kill": 4, "Exclude": 5}
    sorted_index = (
        df.assign(_order=df["decision_class"].map(decision_order))
        .sort_values(["_order", "incr_margin_total", "incr_units_total"], ascending=[True, False, False])
        .index
    )
    rank_map = {idx: rank for rank, idx in enumerate(sorted_index, start=1)}
    df["priority_rank"] = df.index.map(rank_map)

    df.to_csv(FINAL_FACT_CSV, index=False)

    print(df["validation_status"].value_counts())
    print(df["decision_class"].value_counts())
    print(f"\nWrote {FINAL_FACT_CSV}")


if __name__ == "__main__":
    main()