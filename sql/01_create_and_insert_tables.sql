-- =====================================================
-- Retail Promotion Intelligence
-- Database Schema
-- Author: Charudisha
-- Description:
-- Creates tables for the retail promotion analytics project.
-- =====================================================

-- ==========================================
-- Products Dimension Table
-- ==========================================

CREATE TABLE products (
    com_code INTEGER,
    upc BIGINT PRIMARY KEY,
    case_qty INTEGER,
    nitem INTEGER,
    description TEXT,
    size TEXT
);

-- ==========================================
-- Store Demographics Dimension Table
-- ==========================================

CREATE TABLE store_demographics (
    store INTEGER PRIMARY KEY,
    city TEXT,
    zip INTEGER,
    income NUMERIC,
    educ NUMERIC,
    age9 NUMERIC,
    age60 NUMERIC,
    hsizeavg NUMERIC,
    density NUMERIC,
    unemp NUMERIC,
    retired NUMERIC,
    mortgage NUMERIC
);

-- ==========================================
-- Weekly Sales Fact Table
-- ==========================================

CREATE TABLE weekly_sales (
    store INTEGER NOT NULL,
    upc BIGINT NOT NULL,
    week INTEGER NOT NULL,
    move INTEGER,
    qty INTEGER,
    price NUMERIC,
    sale VARCHAR(20),
    profit NUMERIC,
    ok INTEGER,

    PRIMARY KEY (store, upc, week)
);