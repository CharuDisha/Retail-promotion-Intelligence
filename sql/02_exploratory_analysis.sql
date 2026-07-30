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

-- Identify the top 10 products by total units sold.
select p.description, sum(ws.move) as total_units_sold from products p 
join weekly_sales ws on p.upc = ws.upc 
group by p.description 
order by total_units_sold desc 
limit 10; 

/*
Observation:
- PEPSI COLA N/R recorded the highest sales volume with 10,176,741 units sold.
- Pepsi and Coca-Cola products dominate the list of top-selling products.
- Several Dominick's private-label (DOM) products also appear among the top-selling products.

Business Insight:
- Carbonated soft drinks account for a significant portion of total unit sales.
- Both national brands and private-label products demonstrate strong customer demand.
- The next step is to analyze whether promotions contributed to the high sales volumes of these products.
*/

-- =====================================================
-- Which promotion type is associated with the highest total units sold?
-- =====================================================

select sale, sum(move) as total_units_sold
from weekly_sales
group by sale
order by total_units_sold desc;

/*
Observation:
- Transactions without a promotion recorded the highest total sales volume (137,832,256 units).
- Promotion type S generated 82,989,234 units sold.
- Promotion type B generated 74,826,413 units sold.
- Promotion types G and C contributed substantially fewer total units sold.

Business Insight:
- Most units sold were not associated with a promotion.
- Among the recorded promotion types, S and B account for the largest share of promoted unit sales.
- Total units sold alone cannot determine which promotion type is most effective because each promotion type is used a different number of times.
*/

-- =====================================================
-- On average, how many units are sold for each promotion type?
-- =====================================================

select sale, round(avg(move), 2) as avg_units_sold
from weekly_sales
group by sale
order by avg_units_sold desc;

/*
Observation:
- Promotion type G recorded the highest average units sold (66.17 units).
- Promotion type C recorded the second highest average units sold (53.35 units).
- Promotion types S and B averaged 49.87 and 44.91 units sold, respectively.
- Transactions without a promotion recorded the lowest average units sold (9.65 units).

Business Insight:
- Transactions with promotions are associated with higher average unit sales than transactions without promotions.
- Promotion type G has the highest average units sold, although it is used much less frequently than promotion types S and B.
- Additional analysis is needed to determine whether these promotions also improve profitability.
*/

-- =====================================================
-- Business Question:
-- Which products are promoted most frequently?
-- =====================================================

select p.description, count(ws.sale) as promotion_frequency
from products p
join weekly_sales ws on p.upc = ws.upc
where ws.sale != ''
group by p.description
order by promotion_frequency desc
limit 10;

/*
Observation:
- CANADA DRY GINGER ALE was promoted most frequently (63,543 promotional transactions).
- DIET PEPSI CAFFEINE and DIET MOUNTAIN DEW were also among the most frequently promoted products.
- The top 10 list includes products from multiple brands, including Pepsi, Sprite, Sunkist, Barq's, Schweppes, and Lipton.

Business Insight:
- Promotions are concentrated on a subset of products rather than being distributed evenly across the product catalog.
- Frequently promoted products may represent high-priority products targeted to drive customer demand.
- Further analysis is needed to determine whether these frequently promoted products also experience higher average unit sales and profitability during promotions.
*/

-- =====================================================
-- Business Question:
-- Do products sell more units when they are on promotion?
-- =====================================================

select
case
    when sale != '' then 'Promotion'
    else 'No Promotion Code'
end as promoted,
round(avg(move), 2) as avg_units_sold
from weekly_sales
group by
case
    when sale != '' then 'Promotion'
    else 'No Promotion Code'
end;

/*
Observation:
- Transactions with promotions sold an average of 47.86 units.
- Transactions without promotions sold an average of 9.65 units.

Business Insight:
- Promotional transactions are associated with substantially higher average unit sales than non-promotional transactions.
- This analysis identifies a strong association between promotions and unit sales.
- However, this result does not establish that promotions cause higher sales because other factors, such as product popularity, store location, and seasonality, have not yet been controlled for.
*/

-- =====================================================
-- business question:
-- which products experience the greatest increase in average units sold during promotions?
-- =====================================================

select
    p.description,
    round(avg(case
        when sale != '' then ws.move
    end), 2) as avg_units_promotion,
    round(avg(case
        when sale = '' then ws.move
    end), 2) as avg_units_no_promotion,
    round(avg(case
        when sale != '' then ws.move
    end), 2) -
    round(avg(case
        when sale = '' then ws.move
    end), 2) as promotion_lift
from weekly_sales ws
join products p on ws.upc = p.upc
group by p.description
order by promotion_lift desc nulls last
limit 10;

/*
observation:
- ibc root beer trial recorded the highest promotion lift at 915.30 units.
- pepsi cola n/r, starbucks mocha frappaccino, pepsi single serv 20, and pepsi-cola cans also show large positive lifts.
- several pepsi and coca-cola products appear among the products with the highest promotion lift.
- some products have null lift values, which means they do not have both promotion and non-promotion records in the data.

business insight:
- promotions appear to be associated with higher average unit sales for several products.
- products with the highest promotion lift may be strong candidates for future promotions.
- products with unusually large lift should be reviewed carefully because the result may be driven by a small number of promotional observations rather than a consistent pattern.
*/

-- =====================================================
-- Business Question:
-- Which products experience the greatest increase in average units sold during promotions?
-- =====================================================

select
    p.description,
    round(avg(case
        when sale != '' then ws.move
    end), 2) as avg_units_promotion,
    round(avg(case
        when sale = '' then ws.move
    end), 2) as avg_units_no_promotion,
    round(avg(case
        when sale != '' then ws.move
    end), 2) -
    round(avg(case
        when sale = '' then ws.move
    end), 2) as promotion_lift,
    count(case
        when sale != '' then 1
    end) as promotion_transactions
from weekly_sales ws
join products p on ws.upc = p.upc
group by p.description
order by promotion_lift desc nulls last
limit 10;

/*
Observation:
- IBC ROOT BEER TRIAL recorded the highest promotion lift (915.30 units) based on 563 promotional transactions.
- PEPSI COLA N/R and COCA-COLA CLASSIC also recorded substantial promotion lifts, each supported by more than 14,000 promotional transactions.
- Several Pepsi and Coca-Cola products appear among the products with the highest promotion lift.

Business Insight:
- Promotions are associated with higher average unit sales for several products.
- Products with large promotion lifts and a high number of promotional transactions provide stronger evidence of consistent promotional performance.
- Products with high promotion lift but relatively few promotional transactions should be interpreted with caution because the estimates may be less reliable.
*/


-- =====================================================
-- Business Question:
-- How does the average gross margin (%) vary across promotion codes?
-- =====================================================

select
case
    when sale = '' then 'No Promotion Code'
    else sale
end as promotion_code,
round(avg(profit), 2) as avg_gross_margin_pct
from weekly_sales
group by
case
    when sale = '' then 'No Promotion Code'
    else sale
end
order by avg_gross_margin_pct desc;

/*
Observation:
- Coupon (C) promotions recorded the highest average gross margin (18.35%).
- Bonus Buy (B) promotions recorded an average gross margin of 15.24%.
- Transactions without a recorded promotion code averaged an 11.91% gross margin.
- Simple Price Reduction (S) promotions averaged a 7.87% gross margin.
- Promotion code G recorded a negative average gross margin (-0.25%).

Business Insight:
- Different promotion types are associated with different gross margin percentages.
- Coupon (C) and Bonus Buy (B) promotions are associated with higher average gross margins than the other promotion codes.
- Promotion code G is associated with a negative average gross margin and should be investigated further.
- Since the promotion variable is not consistently recorded, the "No Promotion Code" category should be interpreted with caution.
*/