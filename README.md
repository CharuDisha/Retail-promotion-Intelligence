## Data Import

--- =====================================================
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