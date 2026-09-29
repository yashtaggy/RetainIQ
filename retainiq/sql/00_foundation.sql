-- RetainIQ Foundation: Database, Warehouse, and Schemas
-- Run with: ACCOUNTADMIN role
-- Safe to re-run: uses IF NOT EXISTS

-- 1. Database
CREATE DATABASE IF NOT EXISTS RETAINIQ_DB;

-- 2. Schemas
--    RAW:     landing zone for raw/synthetic data
--    CURATED: enriched views and transformed tables
--    APP:     Streamlit app objects, action tables, audit log
CREATE SCHEMA IF NOT EXISTS RETAINIQ_DB.RAW;
CREATE SCHEMA IF NOT EXISTS RETAINIQ_DB.CURATED;
CREATE SCHEMA IF NOT EXISTS RETAINIQ_DB.APP;

-- 3. Warehouse
--    XSMALL (1 credit/hour), auto-suspend 60s, starts suspended
CREATE WAREHOUSE IF NOT EXISTS RETAINIQ_WH
    WAREHOUSE_SIZE = 'XSMALL'
    AUTO_SUSPEND = 60
    AUTO_RESUME = TRUE
    INITIALLY_SUSPENDED = TRUE;

-- 4. Set session defaults
USE DATABASE RETAINIQ_DB;
USE WAREHOUSE RETAINIQ_WH;
