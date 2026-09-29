-- RetainIQ: Semantic Model Deployment
-- Deploys the YAML-based semantic model to a Snowflake stage
-- for use with Cortex Analyst
-- Run after: 04_customer_360.sql
USE DATABASE RETAINIQ_DB;
USE SCHEMA RAW;
USE WAREHOUSE RETAINIQ_WH;

-- The semantic model YAML is stored at:
-- @RETAINIQ_DB.RAW.DATA_STAGE/semantic/retainiq_customer_analytics.sv.yaml
--
-- To use with Cortex Analyst:
--   semantic_model_file: '@RETAINIQ_DB.RAW.DATA_STAGE/semantic/retainiq_customer_analytics.sv.yaml'
--
-- To refresh after YAML edits:
PUT 'file://e:/Snowflake CoCo/retainiq/semantic/retainiq_customer_analytics.sv.yaml'
    @RETAINIQ_DB.RAW.DATA_STAGE/semantic/
    AUTO_COMPRESS=FALSE
    OVERWRITE=TRUE;
