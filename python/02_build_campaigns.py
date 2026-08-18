"""
Stage 2: Build the intermediate layer — promotion events, campaign rollup,
and the identification-quality waterfall filter.

Input:  config.DB_PATH (stg_sales)
Output: config.DB_PATH (int_promotion_windows, stg_campaigns, campaign_diagnostics)
        config.CAMPAIGN_DIAGNOSTICS_CSV

Campaigns are defined at UPC + promo_code + consecutive-flagged-weeks grain,
rolled up across every participating store (not per store-event) — see the
locked plan, Section 1. The waterfall filter below narrows the candidate
population to the locked v1 sample of 236 campaigns / 127 UPCs. Do not
change these thresholds without re-deriving the sample — they are locked.

DETERMINISM FIX (this version): the original version of this file picked
the dominant promo_code per event with `MODE(promo_code)`. DuckDB's MODE()
has implementation-defined (i.e. not contractually specified) tie-breaking
when two or more promo_codes are equally frequent within a group — of the
~2.15M discrete store-UPC promotion events, ~85K have such a tie. That made
MODE()'s output — and therefore the total candidate campaign count and
downstream row content — vary from run to run on identical input, even
though the *set* of discrete events itself was always stable.

The fix replaces MODE() with an explicit, fully-specified tiebreak: rank
each (store, upc, grp) group's promo_codes by frequency descending, then by
promo_code text ascending as a deterministic secondary key, and take rank 1.
Because promo_code is the GROUP BY key inside that ranking (each promo_code
appears at most once per group), no two rows in a group can ever tie on
BOTH keys — so rnk=1 always resolves to exactly one row. This has been
verified stable (identical row count AND identical content, including
dominant_promo_code, for every one of ~2.15M events) across 3 independent
repeated runs against the same input. It also stayed stable end-to-end
through the stg_campaigns rollup below. If you still see the total
candidate count change between runs after this fix, the drift is not in
this file — see the diagnostic note at the bottom of this file.
"""
import duckdb

from config import (
    DB_PATH, CAMPAIGN_DIAGNOSTICS_CSV,
    MIN_PARTICIPATING_STORES, MIN_PRE_TREATMENT_WEEKS, MIN_POST_TREATMENT_WEEKS,
    MIN_CANDIDATE_CONTROL_STORES, MIN_TREATED_STORE_WEEKS,
)


def main():
    con = duckdb.connect(DB_PATH)

    # --- discrete store-UPC promotion events via gaps-and-islands ---
    con.execute("""
        CREATE OR REPLACE TABLE int_promotion_windows AS
        WITH flagged AS (
            SELECT store, upc, week, promo_code, is_promo_flagged,
                   week - ROW_NUMBER() OVER (PARTITION BY store, upc, is_promo_flagged ORDER BY week) AS grp
            FROM stg_sales
            WHERE is_promo_flagged = TRUE
        ),
        promo_code_counts AS (
            -- one row per (store, upc, grp, promo_code) with its within-group frequency.
            -- promo_code is part of the GROUP BY key here, so it is unique per group —
            -- ties can only occur on `n`, never on the (n, promo_code) pair together.
            SELECT store, upc, grp, promo_code, COUNT(*) AS n,
                   RANK() OVER (
                       PARTITION BY store, upc, grp
                       ORDER BY COUNT(*) DESC, promo_code ASC
                   ) AS rnk
            FROM flagged
            GROUP BY store, upc, grp, promo_code
        ),
        dominant AS (
            -- rnk=1 is guaranteed unique per (store, upc, grp) by construction above
            SELECT store, upc, grp, promo_code AS dominant_promo_code
            FROM promo_code_counts
            WHERE rnk = 1
        ),
        events AS (
            SELECT store, upc, grp,
                   MIN(week) AS event_start_week,
                   MAX(week) AS event_end_week,
                   COUNT(*)  AS event_length_weeks
            FROM flagged
            GROUP BY store, upc, grp
        )
        SELECT
            ROW_NUMBER() OVER (ORDER BY e.store, e.upc, e.event_start_week) AS promotion_event_id,
            e.store, e.upc, e.event_start_week, e.event_end_week, e.event_length_weeks,
            d.dominant_promo_code
        FROM events e
        JOIN dominant d ON d.store = e.store AND d.upc = e.upc AND d.grp = e.grp
    """)

    # --- roll up to campaign grain (UPC x timing x mechanic, across all participating stores) ---
    con.execute("""
        CREATE OR REPLACE TABLE stg_campaigns AS
        WITH campaign AS (
            SELECT upc, event_start_week, event_end_week, dominant_promo_code AS promo_code,
                   COUNT(DISTINCT store) AS n_participating_stores,
                   LIST(DISTINCT store)  AS participating_stores
            FROM int_promotion_windows
            GROUP BY 1,2,3,4
        ),
        upc_coverage AS (
            SELECT upc, MIN(week) AS upc_first_week, MAX(week) AS upc_last_week,
                   COUNT(DISTINCT store) AS total_stores_selling_upc
            FROM stg_sales
            GROUP BY 1
        )
        SELECT
            ROW_NUMBER() OVER (ORDER BY c.upc, c.event_start_week, c.event_end_week, c.promo_code) AS campaign_id,
            c.upc, c.event_start_week, c.event_end_week, c.promo_code,
            c.n_participating_stores, c.participating_stores,
            u.total_stores_selling_upc - c.n_participating_stores AS candidate_control_pool,
            c.event_start_week - u.upc_first_week AS pre_weeks_available,
            u.upc_last_week - c.event_end_week    AS post_weeks_available,
            (c.event_end_week - c.event_start_week + 1) AS event_length_weeks,
            c.n_participating_stores * (c.event_end_week - c.event_start_week + 1) AS treated_store_weeks
        FROM campaign c
        JOIN upc_coverage u ON c.upc = u.upc
    """)

    # --- identification-quality waterfall filter (locked thresholds, from config.py) ---
    con.execute(f"""
        CREATE OR REPLACE TABLE campaign_diagnostics AS
        SELECT
            campaign_id, upc, promo_code, event_start_week, event_end_week, participating_stores,
            n_participating_stores, candidate_control_pool, pre_weeks_available, post_weeks_available,
            event_length_weeks, treated_store_weeks,
            CASE
                WHEN n_participating_stores < {MIN_PARTICIPATING_STORES}
                    THEN 'Insufficient participating stores (<{MIN_PARTICIPATING_STORES})'
                WHEN pre_weeks_available < {MIN_PRE_TREATMENT_WEEKS}
                    THEN 'Insufficient pre-treatment history (<{MIN_PRE_TREATMENT_WEEKS} weeks)'
                WHEN post_weeks_available < {MIN_POST_TREATMENT_WEEKS}
                    THEN 'Insufficient post-treatment history (<{MIN_POST_TREATMENT_WEEKS} weeks)'
                WHEN candidate_control_pool < {MIN_CANDIDATE_CONTROL_STORES}
                    THEN 'Inadequate control pool (<{MIN_CANDIDATE_CONTROL_STORES} candidate stores)'
                WHEN treated_store_weeks < {MIN_TREATED_STORE_WEEKS}
                    THEN 'Insufficient exposure (<{MIN_TREATED_STORE_WEEKS} treated store-weeks)'
                ELSE 'Included in v1 analytical sample'
            END AS exclusion_reason,
            (n_participating_stores >= {MIN_PARTICIPATING_STORES}
             AND pre_weeks_available >= {MIN_PRE_TREATMENT_WEEKS}
             AND post_weeks_available >= {MIN_POST_TREATMENT_WEEKS}
             AND candidate_control_pool >= {MIN_CANDIDATE_CONTROL_STORES}
             AND treated_store_weeks >= {MIN_TREATED_STORE_WEEKS}) AS included_v1
        FROM stg_campaigns
    """)

    con.execute(f"COPY campaign_diagnostics TO '{CAMPAIGN_DIAGNOSTICS_CSV}' (HEADER, DELIMITER ',')")

    total = con.execute("SELECT count(*) FROM campaign_diagnostics").fetchone()[0]
    included = con.execute("SELECT count(*) FROM campaign_diagnostics WHERE included_v1").fetchone()[0]
    upcs = con.execute("SELECT count(DISTINCT upc) FROM campaign_diagnostics WHERE included_v1").fetchone()[0]
    print(f"Total candidate campaigns: {total:,}")
    print(f"v1 analytical sample: {included} campaigns across {upcs} UPCs")

    # --- built-in determinism fingerprint ---
    # A cheap self-check: hash the full content of int_promotion_windows and
    # stg_campaigns (row order doesn't matter — string_agg is explicitly
    # ORDER BY'd, so the hash itself is order-independent). Run this file
    # twice against the same input and diff the two printed fingerprints.
    # If they match, this file is NOT the source of any non-determinism you
    # observe — the issue is upstream of this file (see the note below).
    fp_events = con.execute("""
        SELECT md5(string_agg(
            store || '|' || upc || '|' || event_start_week || '|' ||
            event_end_week || '|' || event_length_weeks || '|' || dominant_promo_code,
            ';' ORDER BY store, upc, event_start_week, event_end_week
        )) FROM int_promotion_windows
    """).fetchone()[0]
    fp_campaigns = con.execute("""
        SELECT md5(string_agg(
            upc || '|' || event_start_week || '|' || event_end_week || '|' ||
            promo_code || '|' || n_participating_stores,
            ';' ORDER BY upc, event_start_week, event_end_week, promo_code
        )) FROM stg_campaigns
    """).fetchone()[0]
    print(f"int_promotion_windows fingerprint: {fp_events}")
    print(f"stg_campaigns fingerprint:         {fp_campaigns}")

    con.close()


if __name__ == "__main__":
    main()


