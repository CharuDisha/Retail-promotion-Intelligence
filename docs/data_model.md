# Data Model

## Fact Table

### wsdr

Primary Key:
- store
- week
- upc

Contains:
- Sales
- Price
- Profit
- Promotion
- Movement

---

## Product Dimension

### upcsdr

Primary Key:
- upc

Contains:
- Product description
- Brand
- Package size
- Commodity code
- Item information

---

## Store Dimension

### demographics

Primary Key:
- store

Contains:
- Income
- Education
- Household size
- Population density
- Age
- Employment



                    upcsdr
                  (Products)
                      │
                 upc  │
                      │
                      ▼
                +------------+
                |    wsdr    |
                +------------+
                      ▲
                store │
                      │
                demographics