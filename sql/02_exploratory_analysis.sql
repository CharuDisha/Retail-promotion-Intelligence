-- =====================================================
-- 1. Data Validation
-- =====================================================

-- Verify row counts after importing the data.

SELECT COUNT(*) AS weekly_sales_rows
FROM weekly_sales;

-- Result:
-- 17,730,501

SELECT COUNT(*) AS products_rows
FROM products;

-- Result:
-- 1,746

SELECT COUNT(*) AS store_demographics_rows
FROM store_demographics;

-- Result:
-- 85


-- Verify the time period covered by the dataset.
-- Result:
select MIN(week) AS first_week, MAX(week) AS last_week FROM weekly_sales;
-- first_week = 1
-- last_week = 399

-- Count the number of unique stores in the sales dataset.
SELECT COUNT(DISTINCT store) AS distinct_stores
FROM weekly_sales;
-- Result: 93
/* Observation:
 The sales dataset contains 93 unique stores, while the
 store_demographics table contains demographic information
 for only 85 stores. Therefore, not all stores have
 corresponding demographic data. 
*/


 -- Count the number of unique products sold.

SELECT COUNT(DISTINCT upc) AS distinct_products
FROM weekly_sales;

-- Result: 1,720
/* Observation:
The products table contains 1,746 products, while only
1,720 unique products appear in the sales data.
This indicates that 26 products were not sold or do not
appear in the available transaction records.
*/

-- Analyze the distribution of promotion types.

SELECT
    sale,
    COUNT(*) AS row_count
FROM weekly_sales
GROUP BY sale
ORDER BY row_count DESC;

/*
Observation:
- The majority of transactions (14,287,219) have a blank value in the sale column,
  indicating that most products were sold without a recorded promotion.
- Promotion type 'B' appears 1,666,010 times.
- Promotion type 'S' appears 1,664,212 times.
- Promotion types 'G' (73,034) and 'C' (40,026) are used much less frequently.

Business Insight:
- Most sales occur without a promotion.
- Promotional events represent a relatively small portion of total transactions,
  making it important to compare promotional and non-promotional periods when
  evaluating the effectiveness of promotions.
*/

-- Identify the top 10 stores by total units sold.

SELECT
    store,
    SUM(move) AS total_units_sold
FROM weekly_sales
GROUP BY store
ORDER BY total_units_sold DESC
LIMIT 10;

/*
Observation:
- Store 102 recorded the highest sales volume with 5,850,809 units sold.
- The top 10 stores each sold more than 4.6 million units.

Business Insight:
- A relatively small group of stores contributes a significant portion of total sales.
- Identifying the characteristics of these high-performing stores may help explain differences in sales performance across locations.
*/

-- Identify the top 10 products by total units sold.

SELECT
    upc,
    SUM(move) AS total_units_sold
FROM weekly_sales
GROUP BY upc
ORDER BY total_units_sold DESC
LIMIT 10;

/*
Observation:
- UPC 1200000230 recorded the highest sales volume with 10,176,741 units sold.
- The second highest-selling product (UPC 4900000639) sold 8,434,043 units.
- The top 10 products each sold more than 4.2 million units.

Business Insight:
- A relatively small number of products account for a significant share of total sales.
- Identifying these products will help determine whether their strong performance is driven by pricing, promotions, or customer demand.

*/

-- Calculate summary statistics for the sales dataset.

SELECT
    SUM(move) AS total_units_sold,
    ROUND(AVG(price), 2) AS average_price,
    ROUND(AVG(profit), 2) AS average_profit
FROM weekly_sales;

/*
Observation:
- Total units sold: 302,615,498
- Average selling price across all transactions: $1.43
- Average profit across all transactions: $11.81

Business Insight:
- These summary statistics provide an overall snapshot of the dataset.
- More meaningful pricing and profitability analyses should be performed at the product or promotion level.
*/