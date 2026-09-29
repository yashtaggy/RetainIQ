-- RetainIQ: Customer 360 View with Explainable Churn Risk Score
-- Creates CURATED.CUSTOMER_360
-- Run after: 03_ai_enrichment.sql
--
-- SCORE FORMULA (0-100):
-- ┌────────────────────────────┬─────────────┬───────────────────────────────────────────┐
-- │ Risk Factor                │ Max Points  │ Calculation                               │
-- ├────────────────────────────┼─────────────┼───────────────────────────────────────────┤
-- │ Late payments              │ 20          │ 5 per overdue/failed payment, cap 20      │
-- │ Rejected claims            │ 15          │ 7.5 per rejected claim, cap 15            │
-- │ Outstanding claims (>30d)  │ 10          │ 5 per delayed pending claim, cap 10       │
-- │ Negative sentiment         │ 15          │ abs(recent_avg_sentiment) * 20, cap 15    │
-- │ Competitor mentions        │ 10          │ 5 per mention, cap 10                     │
-- │ Cancellation intent        │ 15          │ 15 if any cancellation interaction        │
-- │ Upcoming renewal risk      │ 10          │ 10 if renewal ≤30 days AND other risks    │
-- │ Lapsed/cancelled policies  │  5          │ 5 if any policy lapsed or cancelled       │
-- ├────────────────────────────┼─────────────┼───────────────────────────────────────────┤
-- │ TOTAL                      │ 100         │                                           │
-- └────────────────────────────┴─────────────┴───────────────────────────────────────────┘
--
-- RISK LEVELS: Critical (≥60), High (≥30), Medium (≥10), Low (<10)
--
-- DYNAMIC TABLE NOTE:
-- This account supports dynamic tables. To convert for production:
--   CREATE OR REPLACE DYNAMIC TABLE RETAINIQ_DB.CURATED.CUSTOMER_360
--     TARGET_LAG = '1 hour'
--     WAREHOUSE = RETAINIQ_WH
--   AS <this query>;

USE DATABASE RETAINIQ_DB;
USE SCHEMA CURATED;
USE WAREHOUSE RETAINIQ_WH;

CREATE OR REPLACE VIEW CUSTOMER_360 AS
WITH policy_agg AS (
    SELECT
        CUSTOMER_ID,
        COUNT(*)                                                      AS TOTAL_POLICIES,
        COUNT(CASE WHEN STATUS = 'Active' THEN 1 END)                AS ACTIVE_POLICIES,
        COUNT(CASE WHEN STATUS IN ('Lapsed','Cancelled') THEN 1 END) AS LAPSED_CANCELLED_POLICIES,
        SUM(CASE WHEN STATUS = 'Active' THEN PREMIUM_AMOUNT ELSE 0 END) AS TOTAL_ACTIVE_PREMIUM,
        MIN(CASE WHEN STATUS = 'Active' AND END_DATE >= CURRENT_DATE()
                 THEN END_DATE END)                                   AS NEAREST_RENEWAL_DATE,
        DATEDIFF('day', CURRENT_DATE(),
            MIN(CASE WHEN STATUS = 'Active' AND END_DATE >= CURRENT_DATE()
                     THEN END_DATE END))                              AS DAYS_TO_RENEWAL
    FROM RETAINIQ_DB.RAW.POLICIES
    GROUP BY CUSTOMER_ID
),
claim_agg AS (
    SELECT
        CUSTOMER_ID,
        COUNT(*)                                                       AS TOTAL_CLAIMS,
        COUNT(CASE WHEN STATUS = 'Rejected' THEN 1 END)               AS REJECTED_CLAIMS,
        COUNT(CASE WHEN STATUS = 'Pending' THEN 1 END)                AS PENDING_CLAIMS,
        COUNT(CASE WHEN STATUS = 'Pending'
                    AND DATEDIFF('day', CLAIM_DATE, CURRENT_DATE()) > 30
                   THEN 1 END)                                         AS DELAYED_CLAIMS,
        COUNT(CASE WHEN STATUS IN ('Pending','Approved') THEN 1 END)  AS OUTSTANDING_CLAIMS,
        SUM(CASE WHEN STATUS IN ('Pending','Approved')
                 THEN CLAIM_AMOUNT ELSE 0 END)                        AS OUTSTANDING_CLAIM_AMOUNT,
        SUM(CASE WHEN STATUS = 'Settled'
                 THEN APPROVED_AMOUNT ELSE 0 END)                     AS TOTAL_SETTLED_AMOUNT
    FROM RETAINIQ_DB.RAW.CLAIMS
    GROUP BY CUSTOMER_ID
),
payment_agg AS (
    SELECT
        CUSTOMER_ID,
        COUNT(*)                                                       AS TOTAL_PAYMENTS,
        COUNT(CASE WHEN STATUS = 'Paid' THEN 1 END)                   AS PAID_COUNT,
        COUNT(CASE WHEN STATUS IN ('Overdue','Failed') THEN 1 END)    AS LATE_PAYMENT_COUNT,
        SUM(LATE_FEE)                                                  AS TOTAL_LATE_FEES,
        MAX(CASE WHEN STATUS = 'Paid' THEN PAID_DATE END)             AS LAST_PAID_DATE
    FROM RETAINIQ_DB.RAW.PAYMENTS
    GROUP BY CUSTOMER_ID
),
interaction_agg AS (
    SELECT
        CUSTOMER_ID,
        COUNT(*)                                                       AS TOTAL_INTERACTIONS,
        AVG(SENTIMENT_SCORE)                                           AS AVG_SENTIMENT,
        COUNT(CASE WHEN SENTIMENT_LABEL = 'negative' THEN 1 END)      AS NEGATIVE_INTERACTION_COUNT,
        COUNT(CASE WHEN COMPETITOR IS NOT NULL THEN 1 END)             AS COMPETITOR_MENTION_COUNT,
        COUNT(CASE WHEN CHURN_SIGNAL = 'cancellation_intent' THEN 1 END) AS CANCELLATION_INTENT_COUNT,
        COUNT(CASE WHEN CHURN_SIGNAL != 'none' THEN 1 END)            AS CHURN_SIGNAL_COUNT,
        LISTAGG(DISTINCT COMPETITOR, ', ') WITHIN GROUP (ORDER BY COMPETITOR) AS COMPETITORS_NAMED,
        AVG(CASE WHEN INTERACTION_TS >= DATEADD('day', -90, CURRENT_TIMESTAMP())
                 THEN SENTIMENT_SCORE END)                             AS RECENT_AVG_SENTIMENT
    FROM RETAINIQ_DB.CURATED.INTERACTION_INSIGHTS
    GROUP BY CUSTOMER_ID
),
scored AS (
    SELECT
        c.CUSTOMER_ID, c.FIRST_NAME, c.LAST_NAME, c.AGE, c.GENDER,
        c.CITY, c.STATE, c.SEGMENT, c.PREFERRED_LANGUAGE,
        COALESCE(pol.TOTAL_POLICIES, 0)              AS TOTAL_POLICIES,
        COALESCE(pol.ACTIVE_POLICIES, 0)             AS ACTIVE_POLICIES,
        COALESCE(pol.LAPSED_CANCELLED_POLICIES, 0)   AS LAPSED_CANCELLED_POLICIES,
        COALESCE(pol.TOTAL_ACTIVE_PREMIUM, 0)        AS TOTAL_ACTIVE_PREMIUM,
        pol.NEAREST_RENEWAL_DATE,
        pol.DAYS_TO_RENEWAL,
        COALESCE(cl.TOTAL_CLAIMS, 0)                 AS TOTAL_CLAIMS,
        COALESCE(cl.REJECTED_CLAIMS, 0)              AS REJECTED_CLAIMS,
        COALESCE(cl.PENDING_CLAIMS, 0)               AS PENDING_CLAIMS,
        COALESCE(cl.DELAYED_CLAIMS, 0)               AS DELAYED_CLAIMS,
        COALESCE(cl.OUTSTANDING_CLAIMS, 0)           AS OUTSTANDING_CLAIMS,
        COALESCE(cl.OUTSTANDING_CLAIM_AMOUNT, 0)     AS OUTSTANDING_CLAIM_AMOUNT,
        COALESCE(pay.TOTAL_PAYMENTS, 0)              AS TOTAL_PAYMENTS,
        COALESCE(pay.LATE_PAYMENT_COUNT, 0)          AS LATE_PAYMENT_COUNT,
        COALESCE(pay.TOTAL_LATE_FEES, 0)             AS TOTAL_LATE_FEES,
        pay.LAST_PAID_DATE,
        COALESCE(ix.TOTAL_INTERACTIONS, 0)           AS TOTAL_INTERACTIONS,
        COALESCE(ix.AVG_SENTIMENT, 0)                AS AVG_SENTIMENT,
        COALESCE(ix.RECENT_AVG_SENTIMENT, 0)         AS RECENT_AVG_SENTIMENT,
        COALESCE(ix.NEGATIVE_INTERACTION_COUNT, 0)   AS NEGATIVE_INTERACTION_COUNT,
        COALESCE(ix.COMPETITOR_MENTION_COUNT, 0)     AS COMPETITOR_MENTION_COUNT,
        COALESCE(ix.CANCELLATION_INTENT_COUNT, 0)    AS CANCELLATION_INTENT_COUNT,
        COALESCE(ix.CHURN_SIGNAL_COUNT, 0)           AS CHURN_SIGNAL_COUNT,
        ix.COMPETITORS_NAMED,
        COALESCE(pol.TOTAL_ACTIVE_PREMIUM, 0)        AS REVENUE_AT_RISK,
        -- Individual risk factor points
        LEAST(20, COALESCE(pay.LATE_PAYMENT_COUNT, 0) * 5)  AS PTS_LATE_PAYMENTS,
        LEAST(15, COALESCE(cl.REJECTED_CLAIMS, 0) * 7.5)    AS PTS_REJECTED_CLAIMS,
        LEAST(10, COALESCE(cl.DELAYED_CLAIMS, 0) * 5)       AS PTS_OUTSTANDING_CLAIMS,
        CASE WHEN COALESCE(ix.RECENT_AVG_SENTIMENT, 0) < 0
             THEN LEAST(15, ABS(COALESCE(ix.RECENT_AVG_SENTIMENT, 0)) * 20)
             ELSE 0 END                                       AS PTS_NEGATIVE_SENTIMENT,
        LEAST(10, COALESCE(ix.COMPETITOR_MENTION_COUNT, 0) * 5) AS PTS_COMPETITOR,
        CASE WHEN COALESCE(ix.CANCELLATION_INTENT_COUNT, 0) > 0
             THEN 15 ELSE 0 END                               AS PTS_CANCELLATION,
        CASE WHEN pol.DAYS_TO_RENEWAL IS NOT NULL
              AND pol.DAYS_TO_RENEWAL <= 30
             THEN 10 ELSE 0 END                               AS PTS_RENEWAL_RISK,
        CASE WHEN COALESCE(pol.LAPSED_CANCELLED_POLICIES, 0) > 0
             THEN 5 ELSE 0 END                                AS PTS_LAPSED
    FROM RETAINIQ_DB.RAW.CUSTOMERS c
    LEFT JOIN policy_agg pol       ON c.CUSTOMER_ID = pol.CUSTOMER_ID
    LEFT JOIN claim_agg cl         ON c.CUSTOMER_ID = cl.CUSTOMER_ID
    LEFT JOIN payment_agg pay      ON c.CUSTOMER_ID = pay.CUSTOMER_ID
    LEFT JOIN interaction_agg ix   ON c.CUSTOMER_ID = ix.CUSTOMER_ID
)
SELECT
    s.*,
    LEAST(100, GREATEST(0, ROUND(
        s.PTS_LATE_PAYMENTS + s.PTS_REJECTED_CLAIMS + s.PTS_OUTSTANDING_CLAIMS
      + s.PTS_NEGATIVE_SENTIMENT + s.PTS_COMPETITOR + s.PTS_CANCELLATION
      + s.PTS_RENEWAL_RISK + s.PTS_LAPSED
    ))) AS CHURN_RISK_SCORE,
    CASE
        WHEN LEAST(100, GREATEST(0, ROUND(
            s.PTS_LATE_PAYMENTS + s.PTS_REJECTED_CLAIMS + s.PTS_OUTSTANDING_CLAIMS
          + s.PTS_NEGATIVE_SENTIMENT + s.PTS_COMPETITOR + s.PTS_CANCELLATION
          + s.PTS_RENEWAL_RISK + s.PTS_LAPSED))) >= 60 THEN 'Critical'
        WHEN LEAST(100, GREATEST(0, ROUND(
            s.PTS_LATE_PAYMENTS + s.PTS_REJECTED_CLAIMS + s.PTS_OUTSTANDING_CLAIMS
          + s.PTS_NEGATIVE_SENTIMENT + s.PTS_COMPETITOR + s.PTS_CANCELLATION
          + s.PTS_RENEWAL_RISK + s.PTS_LAPSED))) >= 30 THEN 'High'
        WHEN LEAST(100, GREATEST(0, ROUND(
            s.PTS_LATE_PAYMENTS + s.PTS_REJECTED_CLAIMS + s.PTS_OUTSTANDING_CLAIMS
          + s.PTS_NEGATIVE_SENTIMENT + s.PTS_COMPETITOR + s.PTS_CANCELLATION
          + s.PTS_RENEWAL_RISK + s.PTS_LAPSED))) >= 10 THEN 'Medium'
        ELSE 'Low'
    END AS RISK_LEVEL,
    ARRAY_TO_STRING(ARRAY_COMPACT(ARRAY_CONSTRUCT(
        CASE WHEN s.PTS_LATE_PAYMENTS > 0
             THEN s.LATE_PAYMENT_COUNT || ' late payment(s) [+' || s.PTS_LATE_PAYMENTS || 'pts]' END,
        CASE WHEN s.PTS_REJECTED_CLAIMS > 0
             THEN s.REJECTED_CLAIMS || ' rejected claim(s) [+' || ROUND(s.PTS_REJECTED_CLAIMS) || 'pts]' END,
        CASE WHEN s.PTS_OUTSTANDING_CLAIMS > 0
             THEN s.DELAYED_CLAIMS || ' claim(s) pending >30 days [+' || s.PTS_OUTSTANDING_CLAIMS || 'pts]' END,
        CASE WHEN s.PTS_NEGATIVE_SENTIMENT > 0
             THEN 'Negative sentiment (avg ' || ROUND(s.RECENT_AVG_SENTIMENT, 2) || ') [+' || ROUND(s.PTS_NEGATIVE_SENTIMENT) || 'pts]' END,
        CASE WHEN s.PTS_COMPETITOR > 0
             THEN s.COMPETITOR_MENTION_COUNT || ' competitor mention(s): ' || s.COMPETITORS_NAMED || ' [+' || s.PTS_COMPETITOR || 'pts]' END,
        CASE WHEN s.PTS_CANCELLATION > 0
             THEN 'Cancellation intent expressed [+15pts]' END,
        CASE WHEN s.PTS_RENEWAL_RISK > 0
             THEN 'Renewal in ' || s.DAYS_TO_RENEWAL || ' days [+10pts]' END,
        CASE WHEN s.PTS_LAPSED > 0
             THEN s.LAPSED_CANCELLED_POLICIES || ' lapsed/cancelled policy(ies) [+5pts]' END
    )), ' | ') AS RISK_FACTORS
FROM scored s;
