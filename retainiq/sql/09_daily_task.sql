-- RetainIQ: Daily Pipeline Task
-- Processes new interactions, enriches with AI, generates NBA recommendations
-- Run after: all other SQL scripts
USE DATABASE RETAINIQ_DB;
USE SCHEMA APP;
USE WAREHOUSE RETAINIQ_WH;

-- ═══════════════════════════════════════════════════════════
-- 1. Task Run Log
-- ═══════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS TASK_RUN_LOG (
    RUN_ID              VARCHAR(30)   NOT NULL PRIMARY KEY,
    RUN_START           TIMESTAMP_NTZ NOT NULL,
    RUN_END             TIMESTAMP_NTZ,
    STATUS              VARCHAR(15)   NOT NULL DEFAULT 'RUNNING',
    NEW_INTERACTIONS    INT           DEFAULT 0,
    ENRICHED_COUNT      INT           DEFAULT 0,
    NBA_GENERATED       INT           DEFAULT 0,
    ERROR_MESSAGE       VARCHAR(2000),
    DETAILS             VARCHAR(4000)
);

-- ═══════════════════════════════════════════════════════════
-- 2. Pipeline Stored Procedure
-- Steps:
--   1. Find unprocessed interactions (NOT IN INTERACTION_INSIGHTS)
--   2. Enrich with SENTIMENT + SUMMARIZE + COMPLETE (skip if 0 new)
--   3. CUSTOMER_360 auto-refreshes (it is a view)
--   4. Generate NBA for new customers without existing recommendations
--   5. Log results to TASK_RUN_LOG
-- ═══════════════════════════════════════════════════════════
CREATE OR REPLACE PROCEDURE SP_DAILY_PIPELINE()
RETURNS VARCHAR
LANGUAGE SQL
AS
$$
DECLARE
    v_run_id VARCHAR DEFAULT 'RUN_' || TO_VARCHAR(CURRENT_TIMESTAMP(), 'YYYYMMDD_HH24MISS');
    v_new_count INT DEFAULT 0;
    v_enriched INT DEFAULT 0;
    v_nba_count INT DEFAULT 0;
    v_error VARCHAR DEFAULT NULL;
    v_details VARCHAR DEFAULT '';
BEGIN
    INSERT INTO RETAINIQ_DB.APP.TASK_RUN_LOG (RUN_ID, RUN_START, STATUS)
    VALUES (:v_run_id, CURRENT_TIMESTAMP(), 'RUNNING');

    SELECT COUNT(*) INTO :v_new_count
    FROM RETAINIQ_DB.RAW.INTERACTIONS
    WHERE INTERACTION_ID NOT IN (SELECT INTERACTION_ID FROM RETAINIQ_DB.CURATED.INTERACTION_INSIGHTS);

    IF (v_new_count = 0) THEN
        UPDATE RETAINIQ_DB.APP.TASK_RUN_LOG
        SET STATUS = 'COMPLETED', RUN_END = CURRENT_TIMESTAMP(),
            NEW_INTERACTIONS = 0, DETAILS = 'No new interactions. Skipped.'
        WHERE RUN_ID = :v_run_id;
        RETURN 'No new interactions. Skipped.';
    END IF;

    v_details := v_new_count || ' new interactions. ';

    BEGIN
        INSERT INTO RETAINIQ_DB.CURATED.INTERACTION_INSIGHTS
        (INTERACTION_ID, CUSTOMER_ID, CHANNEL, DIRECTION, INTERACTION_TS,
         SENTIMENT_SCORE, SENTIMENT_LABEL, PRIMARY_INTENT, CHURN_SIGNAL,
         COMPETITOR, SUMMARY, KEY_QUOTE, RAW_LLM_OUTPUT)
        WITH src AS (
            SELECT * FROM RETAINIQ_DB.RAW.INTERACTIONS
            WHERE INTERACTION_ID NOT IN (SELECT INTERACTION_ID FROM RETAINIQ_DB.CURATED.INTERACTION_INSIGHTS)
              AND CONTENT IS NOT NULL AND TRIM(CONTENT) != ''
        ),
        enr AS (
            SELECT s.INTERACTION_ID, s.CUSTOMER_ID, s.CHANNEL, s.DIRECTION, s.INTERACTION_TS, s.CONTENT,
                SNOWFLAKE.CORTEX.SENTIMENT(s.CONTENT) AS SC,
                SNOWFLAKE.CORTEX.SUMMARIZE(s.CONTENT) AS SM,
                SNOWFLAKE.CORTEX.COMPLETE('llama3.1-8b', CONCAT(
                    'Insurance analyst. Return ONLY valid JSON, no markdown: {"intent":"<claim_enquiry|complaint|renewal|payment|cancellation|feedback|general>","churn_signal":"<claim_delay|price_shock|missed_payment|competitor_mention|cancellation_intent|none>","competitor":"<name or null>","key_quote":"<verbatim max 150 chars>"} Transcript: ', s.CONTENT, ' JSON:')) AS LR
            FROM src s
        ),
        prs AS (
            SELECT e.*, TRY_PARSE_JSON(REGEXP_REPLACE(e.LR, '```[a-z]*\\n?|```', '')) AS J FROM enr e
        )
        SELECT p.INTERACTION_ID, p.CUSTOMER_ID, p.CHANNEL, p.DIRECTION, p.INTERACTION_TS, p.SC,
            CASE WHEN p.SC >= 0.2 THEN 'positive' WHEN p.SC <= -0.2 THEN 'negative' ELSE 'neutral' END,
            COALESCE(p.J['intent']::VARCHAR, 'general'),
            CASE WHEN COALESCE(p.J['churn_signal']::VARCHAR, 'none') NOT IN ('cancellation_intent')
                      AND (LOWER(p.CONTENT) LIKE '%cancel%' OR LOWER(p.CONTENT) LIKE '%cancelling%')
                 THEN 'cancellation_intent' ELSE COALESCE(p.J['churn_signal']::VARCHAR, 'none') END,
            NULLIF(p.J['competitor']::VARCHAR, 'null'), p.SM, p.J['key_quote']::VARCHAR, p.LR
        FROM prs p;

        v_enriched := v_new_count;
        v_details := v_details || v_enriched || ' enriched. ';

        UPDATE RETAINIQ_DB.RAW.INTERACTIONS raw
        SET SENTIMENT_SCORE = ins.SENTIMENT_SCORE, SUMMARY = ins.SUMMARY
        FROM RETAINIQ_DB.CURATED.INTERACTION_INSIGHTS ins
        WHERE raw.INTERACTION_ID = ins.INTERACTION_ID AND raw.SENTIMENT_SCORE IS NULL;
    EXCEPTION
        WHEN OTHER THEN
            v_error := 'Enrichment: ' || SQLERRM;
            v_details := v_details || 'ENRICHMENT ERROR. ';
    END;

    v_details := v_details || 'C360 live. ';

    BEGIN
        LET v_max_id INT := (SELECT COALESCE(MAX(REPLACE(RECOMMENDATION_ID, 'NBA', '')::INT), 0) FROM RETAINIQ_DB.CURATED.NBA_RECOMMENDATIONS);
        INSERT INTO RETAINIQ_DB.CURATED.NBA_RECOMMENDATIONS
        (RECOMMENDATION_ID, CUSTOMER_ID, ACTION_CODE, RECOMMENDED_ACTION,
         RISK_SCORE, PREMIUM_AT_RISK, SUPPORTING_EVIDENCE, CONFIDENCE_SCORE, COMPLIANCE_STATUS)
        WITH new_custs AS (
            SELECT DISTINCT i.CUSTOMER_ID FROM RETAINIQ_DB.CURATED.INTERACTION_INSIGHTS i
            WHERE i.CUSTOMER_ID NOT IN (SELECT CUSTOMER_ID FROM RETAINIQ_DB.CURATED.NBA_RECOMMENDATIONS)
        )
        SELECT 'NBA' || LPAD((:v_max_id + ROW_NUMBER() OVER (ORDER BY c.CHURN_RISK_SCORE DESC))::VARCHAR, 5, '0'),
            c.CUSTOMER_ID, 'PROACTIVE_CALLBACK',
            'Schedule callback (risk ' || c.CHURN_RISK_SCORE || ', new data)',
            c.CHURN_RISK_SCORE, c.TOTAL_ACTIVE_PREMIUM,
            'New interactions. Risk: ' || c.RISK_LEVEL, 0.65, 'COMPLIANT'
        FROM RETAINIQ_DB.CURATED.CUSTOMER_360 c
        WHERE c.CUSTOMER_ID IN (SELECT CUSTOMER_ID FROM new_custs)
          AND c.RISK_LEVEL IN ('Critical', 'High', 'Medium')
          AND c.NEGATIVE_INTERACTION_COUNT >= 1;
        v_nba_count := SQLROWCOUNT;
        v_details := v_details || v_nba_count || ' new NBAs. ';
    EXCEPTION
        WHEN OTHER THEN
            v_error := COALESCE(v_error || ' | ', '') || 'NBA: ' || SQLERRM;
            v_details := v_details || 'NBA ERROR. ';
    END;

    UPDATE RETAINIQ_DB.APP.TASK_RUN_LOG
    SET STATUS = CASE WHEN :v_error IS NOT NULL THEN 'PARTIAL_FAIL' ELSE 'COMPLETED' END,
        RUN_END = CURRENT_TIMESTAMP(), NEW_INTERACTIONS = :v_new_count,
        ENRICHED_COUNT = :v_enriched, NBA_GENERATED = :v_nba_count,
        ERROR_MESSAGE = :v_error, DETAILS = :v_details
    WHERE RUN_ID = :v_run_id;

    RETURN CASE WHEN v_error IS NOT NULL THEN 'Partial: ' || v_error ELSE 'OK: ' || v_details END;
END;
$$;

-- ═══════════════════════════════════════════════════════════
-- 3. Scheduled Task (created SUSPENDED)
-- Schedule: Daily at 2:00 AM IST
-- Timeout: 10 minutes
-- To start: ALTER TASK RETAINIQ_DAILY_PIPELINE RESUME;
-- To stop:  ALTER TASK RETAINIQ_DAILY_PIPELINE SUSPEND;
-- To test:  EXECUTE TASK RETAINIQ_DAILY_PIPELINE;
-- ═══════════════════════════════════════════════════════════
CREATE OR REPLACE TASK RETAINIQ_DAILY_PIPELINE
    WAREHOUSE = RETAINIQ_WH
    SCHEDULE = 'USING CRON 0 2 * * * Asia/Kolkata'
    COMMENT = 'RetainIQ: Daily AI enrichment + NBA pipeline'
    USER_TASK_TIMEOUT_MS = 600000
AS
    CALL RETAINIQ_DB.APP.SP_DAILY_PIPELINE();

-- To resume (start scheduling): ALTER TASK RETAINIQ_DAILY_PIPELINE RESUME;
-- To manually run once:         EXECUTE TASK RETAINIQ_DAILY_PIPELINE;
-- To check history:
-- SELECT * FROM TABLE(INFORMATION_SCHEMA.TASK_HISTORY(TASK_NAME => 'RETAINIQ_DAILY_PIPELINE'))
-- ORDER BY SCHEDULED_TIME DESC LIMIT 10;
