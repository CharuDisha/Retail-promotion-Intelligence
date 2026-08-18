"""
Stage 4: Select matched control UPCs per campaign.

Input:  config.DB_PATH (campaign_diagnostics, stg_sales)
Output: config.CONTROL_SETS_CSV       (campaign_id, variant, n_controls, control_upcs)
        config.CONTROL_DIAGNOSTICS_CSV (per-candidate similarity diagnostics, for QA)

Composite similarity blends five pre-treatment features: correlation, level,
trend, volatility, price. Each feature is normalized against the POOLED
spread across that campaign's eligible candidates (not against the treated
product's own value) — dividing by the treated product's own value blows up
for low-baseline products (e.g. a $0.50 product with any price gap in dollar
terms produces a nonsensical similarity ratio). This is a fix to an earlier
version of this script; keep it as pooled normalization.

Four control sets are produced per campaign (Section 3 + the mandatory
sensitivity test): K=5, K=10 (locked primary), K=20, and a "lower cross
elasticity" set that excludes the closest 30% of matches before selecting
K=10 from what remains — this is the sensitivity check for the
counterfactual/cannibalization circularity concern, not a second estimator.
"""
import duckdb
import pandas as pd
import numpy as np

from config import (
    DB_PATH, CONTROL_SETS_CSV, CONTROL_DIAGNOSTICS_CSV,
    PRE_PERIOD_WEEKS, K_PRIMARY, K_SENSITIVITY, LOWCROSS_EXCLUDE_FRACTION,
)


def vec_corr(matrix: np.ndarray, vec: np.ndarray) -> np.ndarray:
    """Vectorized Pearson correlation of each row in `matrix` against `vec`."""
    mc = matrix - matrix.mean(axis=1, keepdims=True)
    vc = vec - vec.mean()
    num = mc @ vc
    denom = np.sqrt((mc ** 2).sum(axis=1)) * np.sqrt((vc ** 2).sum())
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(denom > 0, num / denom, np.nan)


def main():
    con = duckdb.connect(DB_PATH)
    campaigns = con.execute("""
        SELECT campaign_id, upc AS treated_upc, event_start_week, event_end_week, participating_stores
        FROM campaign_diagnostics WHERE included_v1
    """).fetchdf()
    campaigns["pre_start"] = campaigns["event_start_week"] - PRE_PERIOD_WEEKS

    diag_records, control_sets = [], []

    # bulk-pull every candidate UPC's units/price within each campaign's own participating
    # stores and pre+event window in one join (avoids one query per campaign, which does not scale)
    con.execute("CREATE OR REPLACE TABLE cm_campaigns AS SELECT * FROM campaigns")
    con.execute("""
        CREATE OR REPLACE TABLE cm_campaign_stores AS
        SELECT campaign_id, UNNEST(participating_stores) AS store FROM cm_campaigns
    """)
    con.execute("""
        CREATE OR REPLACE TABLE cm_scoped AS
        SELECT cs.campaign_id, s.upc, s.week,
               SUM(s.units_sold) AS units,
               AVG(NULLIF(s.unit_price,0)) AS avg_price,
               MAX(CASE WHEN s.is_promo_flagged THEN 1 ELSE 0 END) AS any_promo
        FROM cm_campaign_stores cs
        JOIN cm_campaigns c ON cs.campaign_id = c.campaign_id
        JOIN stg_sales s ON s.store = cs.store AND s.week BETWEEN c.pre_start AND c.event_end_week
        GROUP BY 1,2,3
    """)
    scoped_all = con.execute("SELECT * FROM cm_scoped").fetchdf()
    con.close()

    for _, camp in campaigns.iterrows():
        cid = int(camp["campaign_id"]); upc = camp["treated_upc"]
        start, end = int(camp["event_start_week"]), int(camp["event_end_week"])
        pre_weeks = list(range(start - PRE_PERIOD_WEEKS, start))

        scoped = scoped_all[scoped_all["campaign_id"] == cid]
        promoted_in_window = set(scoped.loc[(scoped["week"].between(start, end)) & (scoped["any_promo"] == 1), "upc"])
        candidates = sorted(set(scoped["upc"]) - {upc} - promoted_in_window)

        pre = scoped[scoped["week"].isin(pre_weeks)]
        piv = pre.pivot_table(index="upc", columns="week", values="units", fill_value=0).reindex(columns=pre_weeks, fill_value=0)
        price_piv = pre.pivot_table(index="upc", columns="week", values="avg_price", fill_value=np.nan).reindex(columns=pre_weeks)
        presence = pre.groupby("upc")["week"].nunique()

        eligible = [c for c in candidates if c in piv.index and presence.get(c, 0) >= 6
                    and piv.loc[c].sum() > 0 and piv.loc[c].std() > 0]
        if upc not in piv.index or len(eligible) < 3:
            continue

        treated_vec = piv.loc[upc].values.astype(float)
        treated_price = price_piv.loc[upc].mean() if upc in price_piv.index else np.nan
        treated_level = treated_vec.mean()
        treated_vol = treated_vec.std()
        treated_trend = np.polyfit(range(len(pre_weeks)), treated_vec, 1)[0]

        cand_matrix = piv.loc[eligible].values.astype(float)
        corrs = vec_corr(cand_matrix, treated_vec)
        levels = cand_matrix.mean(axis=1)
        vols = cand_matrix.std(axis=1)
        trends = np.array([np.polyfit(range(len(pre_weeks)), row, 1)[0] for row in cand_matrix])
        prices = np.array([price_piv.loc[c].mean() if c in price_piv.index else np.nan for c in eligible])

        # pooled normalization (the fix): scale by spread across treated + candidates, not treated's own value
        pool_levels = np.append(levels, treated_level)
        pool_vols = np.append(vols, treated_vol)
        pool_trends = np.append(trends, treated_trend)
        pool_prices = np.append(prices[~np.isnan(prices)], treated_price) if not np.isnan(treated_price) else prices

        level_scale = max(pool_levels.std(), 1e-6)
        vol_scale = max(pool_vols.std(), 1e-6)
        trend_scale = max(pool_trends.std(), 1e-6)
        price_scale = max(np.nanstd(pool_prices), 1e-6) if len(pool_prices) > 1 else 1e-6

        level_sim = 1 - np.abs(levels - treated_level) / level_scale
        vol_sim = 1 - np.abs(vols - treated_vol) / vol_scale
        trend_sim = 1 - np.abs(trends - treated_trend) / trend_scale
        price_sim = (1 - np.abs(prices - treated_price) / price_scale) if not np.isnan(treated_price) else np.full(len(eligible), np.nan)

        corr_component = (corrs + 1) / 2
        components = np.vstack([corr_component, np.clip(level_sim, 0, 1), np.clip(vol_sim, 0, 1), np.clip(trend_sim, 0, 1)])
        if not np.all(np.isnan(price_sim)):
            components = np.vstack([components, np.clip(np.nan_to_num(price_sim, nan=0.5), 0, 1)])
        composite = np.nanmean(components, axis=0)

        diag = pd.DataFrame({
            "campaign_id": cid, "control_upc": eligible, "correlation": corrs,
            "level_similarity": level_sim, "volatility_similarity": vol_sim,
            "trend_similarity": trend_sim, "price_similarity": price_sim,
            "composite_score": composite,
        })
        diag_records.append(diag)

        ranked = diag.sort_values("composite_score", ascending=False).reset_index(drop=True)
        variants = {"K5": ranked.head(5), "K10_primary": ranked.head(K_PRIMARY), "K20": ranked.head(20)}
        n_exclude = max(1, int(round(LOWCROSS_EXCLUDE_FRACTION * len(ranked))))
        variants["lowcross_K10"] = ranked.iloc[n_exclude:].head(K_PRIMARY)

        for name, sel in variants.items():
            upcs = sel["control_upc"].tolist()
            control_sets.append((cid, name, len(upcs), ",".join(map(str, upcs))))

    pd.concat(diag_records, ignore_index=True).to_csv(CONTROL_DIAGNOSTICS_CSV, index=False)
    pd.DataFrame(control_sets, columns=["campaign_id", "variant", "n_controls", "control_upcs"]).to_csv(CONTROL_SETS_CSV, index=False)
    print(f"Wrote control sets for {campaigns['campaign_id'].nunique()} campaigns.")


if __name__ == "__main__":
    main()