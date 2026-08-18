"""
Stage 8: Export Power BI display metadata for the locked v1 campaign sample.

Input:  config.DB_PATH (campaign_diagnostics, stg_products)
Output: data/processed/dim_promotion_campaign.csv

This is a display-only lookup table for Power BI (UPC -> product name/size)
joined onto the 236 included_v1 campaigns from campaign_diagnostics. It does
not touch, recompute, or reclassify anything — no thresholds, no causal
logic, no decision classes. Stages 0-7 and their outputs are untouched.
"""
import os
import duckdb

from config import DB_PATH, PROCESSED_DIR

DIM_CAMPAIGN_CSV = os.path.join(PROCESSED_DIR, "dim_promotion_campaign.csv")


def main():
    con = duckdb.connect(DB_PATH)

    con.execute(f"""
        COPY (
            SELECT
                cd.campaign_id,
                cd.upc AS treated_upc,
                p.product_name,
                p.product_size,
                cd.promo_code,
                cd.event_start_week,
                cd.event_end_week,
                cd.n_participating_stores
            FROM campaign_diagnostics cd
            LEFT JOIN stg_products p ON p.upc = cd.upc
            WHERE cd.included_v1
            ORDER BY cd.campaign_id
        ) TO '{DIM_CAMPAIGN_CSV}' (HEADER, DELIMITER ',')
    """)

    n = con.execute(f"SELECT count(*) FROM read_csv_auto('{DIM_CAMPAIGN_CSV}')").fetchone()[0]
    print(f"Wrote {n} rows to {DIM_CAMPAIGN_CSV}")

    con.close()


if __name__ == "__main__":
    main()