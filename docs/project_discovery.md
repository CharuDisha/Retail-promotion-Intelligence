# Project Discovery

## 1. Project Goal

### Business Problem
Determine which soft-drink promotion campaigns create genuine incremental unit sales and incremental gross margin, versus promotions that mainly shift purchase timing or cannibalize other products.

### Business Decision
Recommend whether each promotion campaign should be:
- Keep
- Redesign
- Monitor
- Kill
- Exclude

### Intended User
Retail pricing / promotions / merchandising teams.

### Analytical Goal
Estimate causal promotion effects rather than simply comparing sales during promotion weeks with sales during non-promotion weeks.

---

## 2. Dataset

### Source
Dominick's Finer Foods scanner dataset from the Kilts Center, University of Chicago Booth School of Business.

### Category
Soft drinks (`sdr`).

### Raw Weekly Sales Data
File: `weekly_sales.csv`

One row represents a:
- store
- UPC
- week

Important fields:
- `STORE`
- `UPC`
- `WEEK`
- `MOVE` — units sold
- `PRICE`
- `QTY` — bundle quantity
- `SALE` — recorded promotion flag
- `PROFIT` — gross margin percentage
- `OK` — data validity flag

### Product Data
File: `products.csv`

Provides UPC-level product information, including:
- UPC
- commodity code
- product description
- size
- case-pack information
- discontinued-product indicator

### Store Demographics
Files:
- `store_demographics.csv`
- `store_demographics.dta`

These contain store-level demographic information. They are retained for reference / potential secondary analysis but are not required for the core causal promotion estimator.

### Manual / Codebook
The Dominick's manual provides:
- week-number → calendar-date mapping
- special-event / holiday information
- coding definitions
- data-construction guidance
- important interpretation caveats

---

## 3. Data Quality Notes

### Validity
Core analysis uses records where:
- `OK = 1`

This leaves approximately 17.48M valid weekly store-UPC observations.

### Promotion Flag
`SALE` is recorded inconsistently.

A blank / NULL `SALE` value means that a promotion was not recorded, but it does **not** guarantee that no promotion occurred.

Recorded codes:
- `B` = bonus buy
- `S` = price reduction
- `C` = coupon

This creates potential treatment/control contamination and is treated as a limitation.

### Revenue
Revenue is calculated using the codebook-consistent formula:

`PRICE × MOVE / QTY`

rather than simply `PRICE × MOVE`, because some UPCs represent multi-unit / bundle pricing.

### Margin
`PROFIT` represents gross margin percentage based on average acquisition cost.

Gross margin dollars are derived from sales dollars and gross margin percentage.

This is gross margin, not fully loaded net profit.

### Price Data
Rows with:
- `MOVE > 0`
- `PRICE = 0`

are flagged as potentially problematic price observations.

### Control Contamination
Candidate control UPCs are screened for:
- sufficient pre-treatment presence
- nonzero activity
- non-degenerate variation
- recorded promotions during the campaign window

---

## 4. Business Scope

### Time Period
Approximately 1989–1997, covering roughly 400 weeks in the scanner data.

### Analytical Unit
Promotion campaign, defined by:
- UPC
- promotion code
- campaign start week
- campaign end week

Campaigns are rolled across participating stores rather than treating each store's promotion as a separate campaign.

### Candidate Campaigns
Approximately 94.8K campaign records are generated after campaign construction.

### Version 1 Analytical Sample
236 campaigns across 127 UPCs.

Campaigns enter the v1 sample only when they satisfy predefined identification-quality requirements, including:
- sufficient participating stores
- sufficient treated store-week exposure
- sufficient pre-treatment history
- sufficient post-treatment history
- initial control-pool availability

### Primary Causal Design
Within-store, cross-product Difference-in-Differences using matched non-promoted UPCs within participating stores.

Primary control specification:
- K = 10 matched UPCs

Sensitivity checks:
- K = 5
- K = 20
- lower-cross-elasticity control set

Store-level matched controls are retained only as a robustness check where sufficient untreated stores exist.

### Validation
Campaign estimates are evaluated using:
- pretrend validation
- placebo tests
- BH-FDR correction separately for unit and margin outcomes

### Final Analytical Results
From the 236 campaign estimation sample:
- 62 campaigns pass causal validation
- 174 are excluded from decision-making because the causal design does not pass validation

Among valid campaigns:
- 21 Keep
- 23 Redesign
- 14 Monitor
- 4 Kill

### Cannibalization
Cannibalization is measured at the category / peer-product level.

Customer-level substitution cannot be identified because the scanner data is store-aggregate rather than basket- or customer-level.

---

## 5. Out of Scope / Limitations

- Customer-level substitution
- Basket-level cannibalization
- Fully loaded promotion ROI
- Promotion media / trade-spend costs not observed in the dataset
- Generalizing causal conclusions to every promotion in the category

Findings apply to campaigns that satisfy the project's predefined identification requirements.

---

## 6. Current Pipeline

1. Extract week/calendar lookup from the Dominick's codebook
2. Load raw files into DuckDB
3. Build clean staging tables
4. Construct promotion campaigns
5. Apply identification-quality scope filters
6. Verify product-control availability
7. Match control UPCs
8. Build estimation panels
9. Estimate campaign-level DiD effects
10. Validate pretrends and placebos
11. Apply BH-FDR correction
12. Assign Keep / Redesign / Monitor / Kill / Exclude decisions
13. Visualize final results in Power BI

---

## 7. Key Project Questions

- Which promotions create incremental unit sales?
- Which promotions create incremental gross margin?
- Which promotions increase volume but destroy margin?
- Which promotions show evidence of category-level cannibalization?
- Which promotion campaigns should be kept, redesigned, monitored, killed, or excluded?
- How sensitive are the conclusions to control-product selection?