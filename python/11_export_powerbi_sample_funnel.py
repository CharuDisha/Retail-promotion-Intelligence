"""
Stage 11: Export the 94,831 -> 236 identification-quality funnel for Power
BI Page 4 (Methodology & Sample Integrity).

Input:  config.DB_PATH (campaign_diagnostics -- Stage 2 output, untouched)
Output: data/processed/fact_sample_funnel.csv

Display-only aggregation. This does not evaluate any threshold itself --
it only counts the `exclusion_reason` values that 02_build_intermediate_
campaigns.py already computed and stored on every one of the 94,831
candidate campaigns.

Why this is a valid sequential waterfall, not five overlapping reasons:
Stage 2's CASE expression checks the five thresholds in a fixed order and
assigns each campaign to the FIRST one it fails (SQL CASE short-circuits).
None of the five underlying metrics (n_participating_stores,
pre_weeks_available, post_weeks_available, candidate_control_pool,
treated_store_weeks) are recalculated based on which other campaigns
survive, so "removed at stage N" here means exactly "passed stages
1..N-1, failed stage N." The six exclusion_reason values partition all
94,831 campaigns with no overlap, and are read back here in the same
fixed order as the original CASE -- reconstructed from the same locked
config constants and string templates, not retyped as separate literals,
so this script cannot silently drift out of sync with Stage 2's wording.

Caveat worth surfacing on the dashboard: a campaign's exclusion_reason is
the first threshold it failed, not necessarily the only one -- a campaign
excluded for insufficient store participation may also have failed a
later check that was never evaluated once the first failure was found.
"""
import os

import duckdb

from config import (
    DB_PATH, PROCESSED_DIR,
    MIN_PARTICIPATING_STORES, MIN_PRE_TREATMENT_WEEKS, MIN_POST_TREATMENT_WEEKS,
    MIN_CANDIDATE_CONTROL_STORES, MIN_TREATED_STORE_WEEKS,
)

FUNNEL_CSV = os.path.join(PROCESSED_DIR, "fact_sample_funnel.csv")

# Same fixed order as the CASE WHEN in 02_build_intermediate_campaigns.py,
# with the exact reason strings rebuilt from the same config constants and
# templates (not hardcoded separately from Stage 2's wording).
STAGE_ORDER = [
    ("Store participation",
     f"Insufficient participating stores (<{MIN_PARTICIPATING_STORES})",
     f"Excludes campaigns with fewer than {MIN_PARTICIPATING_STORES} participating stores."),
    ("Pre-treatment history",
     f"Insufficient pre-treatment history (<{MIN_PRE_TREATMENT_WEEKS} weeks)",
     f"Excludes campaigns with fewer than {MIN_PRE_TREATMENT_WEEKS} weeks of pre-period data."),
    ("Post-treatment history",
     f"Insufficient post-treatment history (<{MIN_POST_TREATMENT_WEEKS} weeks)",
     f"Excludes campaigns with fewer than {MIN_POST_TREATMENT_WEEKS} weeks of post-period data."),
    ("Control pool size",
     f"Inadequate control pool (<{MIN_CANDIDATE_CONTROL_STORES} candidate stores)",
     f"Excludes campaigns with fewer than {MIN_CANDIDATE_CONTROL_STORES} candidate control stores."),
    ("Treated exposure",
     f"Insufficient exposure (<{MIN_TREATED_STORE_WEEKS} treated store-weeks)",
     f"Excludes campaigns below {MIN_TREATED_STORE_WEEKS} treated store-weeks of exposure."),
    ("Included in v1 sample",
     "Included in v1 analytical sample",
     "Passed all five identification-quality thresholds above."),
]


def main():
    con = duckdb.connect(DB_PATH)

    counts = dict(con.execute("""
        SELECT exclusion_reason, COUNT(*) FROM campaign_diagnostics GROUP BY exclusion_reason
    """).fetchall())
    total_candidates = con.execute("SELECT COUNT(*) FROM campaign_diagnostics").fetchone()[0]
    con.close()

    expected_reasons = {reason for _, reason, _ in STAGE_ORDER}
    actual_reasons = set(counts.keys())
    if actual_reasons != expected_reasons:
        raise ValueError(
            "campaign_diagnostics.exclusion_reason values do not match the reasons "
            "reconstructed from config.py -- Stage 2's wording or thresholds have "
            "likely changed since this script was written. Not exporting a funnel "
            "on a mismatch.\n"
            f"In data but not expected: {actual_reasons - expected_reasons}\n"
            f"Expected but not in data: {expected_reasons - actual_reasons}"
        )

    rows = [("Candidates identified", total_candidates, 0,
              "Reproducible candidate campaigns from Stage 2's gaps-and-islands construction.")]

    running_total = total_candidates
    for stage_label, reason, description in STAGE_ORDER:
        removed = counts[reason] if reason != "Included in v1 analytical sample" else 0
        running_total -= removed
        rows.append((stage_label, running_total, removed, description))

    # --- validation before export ---
    final_remaining = rows[-1][1]
    included_count = counts["Included in v1 analytical sample"]
    n_dupe_check = sum(counts.values())

    print(f"Total candidate campaigns: {total_candidates:,}")
    print(f"Sum of all exclusion_reason buckets: {n_dupe_check:,} "
          f"(should equal total candidates: {n_dupe_check == total_candidates})")
    print(f"Final funnel row remaining count: {final_remaining} "
          f"(should equal included_v1 count: {included_count}, match: {final_remaining == included_count})")

    if n_dupe_check != total_candidates or final_remaining != included_count:
        raise ValueError("Funnel counts do not reconcile against campaign_diagnostics -- not exporting.")

    import csv
    with open(FUNNEL_CSV, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["stage", "campaigns_remaining", "campaigns_removed", "description"])
        w.writerows(rows)

    print(f"Wrote {len(rows)} rows to {FUNNEL_CSV}")


if __name__ == "__main__":
    main()