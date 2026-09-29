-- RetainIQ: AI Enrichment of Interactions
-- Creates CURATED.INTERACTION_INSIGHTS using Cortex AI functions
-- Processes interactions in batches to avoid timeouts
-- Run after: 01_tables.sql, 02_load_data.sql
USE DATABASE RETAINIQ_DB;
USE SCHEMA CURATED;
USE WAREHOUSE RETAINIQ_WH;

-- 1. Create the insights table
CREATE TABLE IF NOT EXISTS INTERACTION_INSIGHTS (
    INTERACTION_ID     VARCHAR(15)  NOT NULL PRIMARY KEY,
    CUSTOMER_ID        VARCHAR(10)  NOT NULL,
    CHANNEL            VARCHAR(15),
    DIRECTION          VARCHAR(10),
    INTERACTION_TS     TIMESTAMP_NTZ,
    SENTIMENT_SCORE    FLOAT,
    SENTIMENT_LABEL    VARCHAR(10),
    PRIMARY_INTENT     VARCHAR(30),
    CHURN_SIGNAL       VARCHAR(50),
    COMPETITOR         VARCHAR(100),
    SUMMARY            VARCHAR(1000),
    KEY_QUOTE          VARCHAR(1000),
    RAW_LLM_OUTPUT     VARCHAR(4000),
    ENRICHED_AT        TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);

-- 2. Enrichment query (parameterised for batch processing)
-- Replace OFFSET/LIMIT values for each batch:
--   Batch 1: OFFSET 0  LIMIT 300
--   Batch 2: OFFSET 300 LIMIT 300
--   ... etc.
INSERT INTO INTERACTION_INSIGHTS
(INTERACTION_ID, CUSTOMER_ID, CHANNEL, DIRECTION, INTERACTION_TS,
 SENTIMENT_SCORE, SENTIMENT_LABEL, PRIMARY_INTENT, CHURN_SIGNAL,
 COMPETITOR, SUMMARY, KEY_QUOTE, RAW_LLM_OUTPUT)
WITH source AS (
    SELECT *
    FROM RETAINIQ_DB.RAW.INTERACTIONS
    WHERE INTERACTION_ID NOT IN (SELECT INTERACTION_ID FROM INTERACTION_INSIGHTS)
    ORDER BY INTERACTION_ID
    LIMIT 300  -- adjust per batch
),
enriched AS (
    SELECT
        s.INTERACTION_ID,
        s.CUSTOMER_ID,
        s.CHANNEL,
        s.DIRECTION,
        s.INTERACTION_TS,
        s.CONTENT,
        SNOWFLAKE.CORTEX.SENTIMENT(s.CONTENT) AS SENT_SCORE,
        SNOWFLAKE.CORTEX.SUMMARIZE(s.CONTENT) AS AI_SUMMARY,
        SNOWFLAKE.CORTEX.COMPLETE('llama3.1-8b',
            CONCAT(
                'You are an insurance call analyst. Analyze this transcript and return ONLY a valid JSON object. NO markdown, NO code fences, NO explanation — just the raw JSON.

Fields:
- "intent": the PRIMARY purpose of the interaction. Exactly one of: claim_enquiry, complaint, renewal, payment, cancellation, feedback, general
  Note: if the customer explicitly says they want to cancel, use "cancellation". If they threaten to cancel as leverage in a complaint, use "complaint".
- "churn_signal": the STRONGEST churn signal. Exactly one of: claim_delay, price_shock, missed_payment, competitor_mention, cancellation_intent, none
  Note: if cancellation is mentioned (even as a threat), use "cancellation_intent". If a competitor is named, use "competitor_mention".
- "competitor": the first competitor insurer name mentioned, or null if none. Only include actual competitor company names, not the policyholder''s own insurer.
- "key_quote": the single most important customer sentence (verbatim, max 150 chars)

Transcript:
', s.CONTENT, '

JSON:')
        ) AS LLM_RAW
    FROM source s
),
parsed AS (
    SELECT
        e.*,
        TRY_PARSE_JSON(REGEXP_REPLACE(e.LLM_RAW, '```[a-z]*\\n?|```', '')) AS J
    FROM enriched e
)
SELECT
    p.INTERACTION_ID,
    p.CUSTOMER_ID,
    p.CHANNEL,
    p.DIRECTION,
    p.INTERACTION_TS,
    p.SENT_SCORE,
    CASE
        WHEN p.SENT_SCORE >= 0.2 THEN 'positive'
        WHEN p.SENT_SCORE <= -0.2 THEN 'negative'
        ELSE 'neutral'
    END AS SENTIMENT_LABEL,
    COALESCE(p.J['intent']::VARCHAR, 'general') AS PRIMARY_INTENT,
    -- Post-processing: override churn signal for cancellation keywords
    CASE
        WHEN COALESCE(p.J['churn_signal']::VARCHAR, 'none') NOT IN ('cancellation_intent')
             AND (LOWER(p.CONTENT) LIKE '%cancel%' OR LOWER(p.CONTENT) LIKE '%cancelling%')
        THEN 'cancellation_intent'
        ELSE COALESCE(p.J['churn_signal']::VARCHAR, 'none')
    END AS CHURN_SIGNAL,
    NULLIF(p.J['competitor']::VARCHAR, 'null') AS COMPETITOR,
    p.AI_SUMMARY,
    p.J['key_quote']::VARCHAR AS KEY_QUOTE,
    p.LLM_RAW
FROM parsed p;

-- 3. Also update the RAW table with sentiment and summary
-- (for use by the churn risk view later)
UPDATE RETAINIQ_DB.RAW.INTERACTIONS raw
SET
    SENTIMENT_SCORE = ins.SENTIMENT_SCORE,
    SUMMARY = ins.SUMMARY
FROM INTERACTION_INSIGHTS ins
WHERE raw.INTERACTION_ID = ins.INTERACTION_ID
  AND raw.SENTIMENT_SCORE IS NULL;
