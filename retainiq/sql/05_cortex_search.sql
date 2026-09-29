-- RetainIQ: Cortex Search Service for Interaction Transcripts
-- Creates a semantic search index over customer interactions
-- Run after: 03_ai_enrichment.sql
USE DATABASE RETAINIQ_DB;
USE SCHEMA CURATED;
USE WAREHOUSE RETAINIQ_WH;

-- 1. Source table: combines raw transcript with AI-enriched metadata
CREATE OR REPLACE TABLE SEARCH_INTERACTIONS AS
SELECT
    r.INTERACTION_ID,
    r.CUSTOMER_ID,
    r.CHANNEL,
    r.DIRECTION,
    r.INTERACTION_TS,
    ins.SENTIMENT_LABEL,
    ins.PRIMARY_INTENT,
    ins.CHURN_SIGNAL,
    ins.COMPETITOR,
    CONCAT(
        'Transcript: ', r.CONTENT,
        ' | Summary: ', COALESCE(ins.SUMMARY, ''),
        ' | Intent: ', COALESCE(ins.PRIMARY_INTENT, ''),
        ' | Churn Signal: ', COALESCE(ins.CHURN_SIGNAL, 'none'),
        CASE WHEN ins.COMPETITOR IS NOT NULL
             THEN ' | Competitor Mentioned: ' || ins.COMPETITOR ELSE '' END
    ) AS SEARCH_TEXT,
    r.CONTENT AS ORIGINAL_TRANSCRIPT,
    ins.SUMMARY,
    ins.KEY_QUOTE
FROM RETAINIQ_DB.RAW.INTERACTIONS r
JOIN RETAINIQ_DB.CURATED.INTERACTION_INSIGHTS ins
    ON r.INTERACTION_ID = ins.INTERACTION_ID;

-- 2. Cortex Search service
-- ON SEARCH_TEXT: the column indexed for semantic (vector) search
-- ATTRIBUTES: columns available as metadata filters in search queries
-- TARGET_LAG: re-indexes when source data changes (at most every hour)
-- Embedding model: snowflake-arctic-embed-m-v1.5 (auto-selected)
CREATE OR REPLACE CORTEX SEARCH SERVICE INTERACTION_SEARCH
  ON SEARCH_TEXT
  ATTRIBUTES CUSTOMER_ID,
             INTERACTION_ID,
             CHANNEL,
             SENTIMENT_LABEL,
             PRIMARY_INTENT,
             CHURN_SIGNAL,
             COMPETITOR
  WAREHOUSE = RETAINIQ_WH
  TARGET_LAG = '1 hour'
  AS (
    SELECT
        SEARCH_TEXT,
        INTERACTION_ID,
        CUSTOMER_ID,
        CHANNEL,
        SENTIMENT_LABEL,
        PRIMARY_INTENT,
        CHURN_SIGNAL,
        COMPETITOR,
        ORIGINAL_TRANSCRIPT,
        SUMMARY,
        KEY_QUOTE
    FROM SEARCH_INTERACTIONS
  );

-- 3. Example queries (using SEARCH_PREVIEW for SQL-based access)
-- Query: customers unhappy about claim delays
SELECT r.value:INTERACTION_ID::VARCHAR AS ID,
       r.value:CUSTOMER_ID::VARCHAR AS CUSTOMER,
       r.value:SUMMARY::VARCHAR AS SUMMARY,
       r.value:CHURN_SIGNAL::VARCHAR AS SIGNAL
FROM TABLE(FLATTEN(
    PARSE_JSON(SNOWFLAKE.CORTEX.SEARCH_PREVIEW(
        'RETAINIQ_DB.CURATED.INTERACTION_SEARCH',
        '{"query":"customer unhappy about claim delay",
          "columns":["INTERACTION_ID","CUSTOMER_ID","SUMMARY","CHURN_SIGNAL"],
          "limit":5}'
    ))['results']
)) r;
