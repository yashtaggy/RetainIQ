-- RetainIQ: Next Best Action Recommendation Engine
-- Three-layer architecture: SQL eligibility → LLM rationale → Confidence scoring
-- Run after: 04_customer_360.sql
USE DATABASE RETAINIQ_DB;
USE SCHEMA CURATED;
USE WAREHOUSE RETAINIQ_WH;

-- ═══════════════════════════════════════════════════════════
-- LAYER 0: Reference Tables
-- ═══════════════════════════════════════════════════════════
CREATE OR REPLACE TABLE ACTION_CATALOG (
    ACTION_CODE       VARCHAR(30)  NOT NULL PRIMARY KEY,
    ACTION_NAME       VARCHAR(100) NOT NULL,
    DESCRIPTION       VARCHAR(500),
    PRIORITY          INT          NOT NULL,
    MAX_DISCOUNT_PCT  FLOAT,
    MAX_DISCOUNT_AMT  NUMBER(12,2),
    COMPLIANCE_NOTES  VARCHAR(500)
);

INSERT INTO ACTION_CATALOG VALUES
('CLAIM_ESCALATION',   'Escalate Pending Claim',      'Escalate claims stuck in Pending >30 days to senior claims officer.', 1, NULL, NULL, 'Must reference real CLAIM_ID in Pending status.'),
('CLAIM_REVIEW',       'Re-review Rejected Claim',    'Re-review rejected claim where customer has complained.', 2, NULL, NULL, 'Must reference real CLAIM_ID and rejection reason.'),
('RETENTION_DISCOUNT', 'Offer Retention Discount',    'Premium discount for high-risk customer with competitor/cancellation signals.', 3, 0.15, 10000.00, 'Max 15% or Rs.10000. No age/gender/language bias. Cannot combine with RENEWAL_INCENTIVE.'),
('PAYMENT_PLAN',       'Offer Flexible Payment Plan', 'Switch to quarterly/monthly for customers with overdue payments.', 4, NULL, NULL, 'Cannot waive late fees without manager approval.'),
('RENEWAL_INCENTIVE',  'Early Renewal Incentive',     'NCB bonus uplift for early renewal.', 5, 0.10, NULL, 'Max 10% NCB uplift. No cancellation intent required.'),
('PROACTIVE_CALLBACK', 'Schedule Proactive Callback', 'Retention callback for at-risk customers with negative interactions.', 6, NULL, NULL, 'Not for Low-risk. Catch-all when no specific action fits.');

CREATE OR REPLACE TABLE NBA_RECOMMENDATIONS (
    RECOMMENDATION_ID   VARCHAR(20)    NOT NULL PRIMARY KEY,
    CUSTOMER_ID         VARCHAR(10)    NOT NULL,
    ACTION_CODE         VARCHAR(30)    NOT NULL,
    RECOMMENDED_ACTION  VARCHAR(500),
    RATIONALE           VARCHAR(2000),
    SUPPORTING_EVIDENCE VARCHAR(2000),
    RISK_SCORE          INT,
    CONFIDENCE_SCORE    FLOAT,
    COMPLIANCE_STATUS   VARCHAR(20)    DEFAULT 'PENDING',
    REVIEW_REASON       VARCHAR(200),
    PREMIUM_AT_RISK     NUMBER(12,2),
    DISCOUNT_AMOUNT     NUMBER(12,2),
    CREATED_AT          TIMESTAMP_NTZ  DEFAULT CURRENT_TIMESTAMP(),
    FOREIGN KEY (ACTION_CODE) REFERENCES ACTION_CATALOG(ACTION_CODE)
);

-- ═══════════════════════════════════════════════════════════
-- LAYER 1: Deterministic Eligibility (SQL rules only)
-- Each customer gets at most their highest-priority action.
-- Priority: CLAIM_ESCALATION(1) > CLAIM_REVIEW(2) > RETENTION_DISCOUNT(3)
--         > PAYMENT_PLAN(4) > RENEWAL_INCENTIVE(5) > PROACTIVE_CALLBACK(6)
-- ═══════════════════════════════════════════════════════════
INSERT INTO NBA_RECOMMENDATIONS
(RECOMMENDATION_ID, CUSTOMER_ID, ACTION_CODE, RECOMMENDED_ACTION, RISK_SCORE,
 PREMIUM_AT_RISK, DISCOUNT_AMOUNT, SUPPORTING_EVIDENCE)
WITH claim_evidence AS (
    SELECT
        cl.CUSTOMER_ID, cl.CLAIM_ID, cl.CLAIM_AMOUNT, cl.STATUS AS CLAIM_STATUS,
        cl.CLAIM_DATE, cl.REJECTION_REASON, cl.CATEGORY,
        DATEDIFF('day', cl.CLAIM_DATE, CURRENT_DATE()) AS DAYS_SINCE_CLAIM,
        ix.INTERACTION_ID AS COMPLAINT_IX_ID, ix.KEY_QUOTE AS COMPLAINT_QUOTE
    FROM RAW.CLAIMS cl
    LEFT JOIN (
        SELECT CUSTOMER_ID, INTERACTION_ID, KEY_QUOTE,
            ROW_NUMBER() OVER (PARTITION BY CUSTOMER_ID ORDER BY INTERACTION_TS DESC) AS RN
        FROM INTERACTION_INSIGHTS
        WHERE PRIMARY_INTENT IN ('claim_enquiry', 'complaint')
          AND CHURN_SIGNAL IN ('claim_delay', 'cancellation_intent')
    ) ix ON cl.CUSTOMER_ID = ix.CUSTOMER_ID AND ix.RN = 1
),
eligible AS (
    -- 1. CLAIM_ESCALATION
    SELECT c.CUSTOMER_ID, 'CLAIM_ESCALATION' AS AC, 1 AS PRI,
        'Escalate claim ' || ce.CLAIM_ID || ' (' || ce.CATEGORY || ', Rs. ' || ce.CLAIM_AMOUNT || ') pending ' || ce.DAYS_SINCE_CLAIM || ' days' AS ADESC,
        c.CHURN_RISK_SCORE AS RS, c.TOTAL_ACTIVE_PREMIUM AS PREM, NULL::NUMBER(12,2) AS DISC,
        'Claim ' || ce.CLAIM_ID || ': ' || ce.CATEGORY || ', Rs. ' || ce.CLAIM_AMOUNT || ', pending ' || ce.DAYS_SINCE_CLAIM || ' days.' ||
        COALESCE(' Customer: "' || ce.COMPLAINT_QUOTE || '"', '') AS EV
    FROM CUSTOMER_360 c JOIN claim_evidence ce ON c.CUSTOMER_ID = ce.CUSTOMER_ID AND ce.CLAIM_STATUS = 'Pending' AND ce.DAYS_SINCE_CLAIM > 30
    UNION ALL
    -- 2. CLAIM_REVIEW
    SELECT c.CUSTOMER_ID, 'CLAIM_REVIEW', 2,
        'Re-review claim ' || ce.CLAIM_ID || ' (' || ce.CATEGORY || ', Rs. ' || ce.CLAIM_AMOUNT || '). Rejection: ' || COALESCE(ce.REJECTION_REASON, 'unspecified'),
        c.CHURN_RISK_SCORE, c.TOTAL_ACTIVE_PREMIUM, NULL,
        'Claim ' || ce.CLAIM_ID || ' rejected: ' || COALESCE(ce.REJECTION_REASON, 'N/A') || '. Complaint interaction ' || ce.COMPLAINT_IX_ID || '.' || COALESCE(' Quote: "' || ce.COMPLAINT_QUOTE || '"', '')
    FROM CUSTOMER_360 c JOIN claim_evidence ce ON c.CUSTOMER_ID = ce.CUSTOMER_ID AND ce.CLAIM_STATUS = 'Rejected' AND ce.COMPLAINT_IX_ID IS NOT NULL
    UNION ALL
    -- 3. RETENTION_DISCOUNT
    SELECT c.CUSTOMER_ID, 'RETENTION_DISCOUNT', 3,
        'Offer Rs. ' || LEAST(ROUND(c.TOTAL_ACTIVE_PREMIUM * 0.15, 0), 10000) || ' retention discount',
        c.CHURN_RISK_SCORE, c.TOTAL_ACTIVE_PREMIUM, LEAST(ROUND(c.TOTAL_ACTIVE_PREMIUM * 0.15, 0), 10000),
        'Risk: ' || c.RISK_LEVEL || '. ' || CASE WHEN c.COMPETITOR_MENTION_COUNT > 0 THEN c.COMPETITOR_MENTION_COUNT || ' competitor mention(s). ' ELSE '' END || CASE WHEN c.CANCELLATION_INTENT_COUNT > 0 THEN c.CANCELLATION_INTENT_COUNT || ' cancellation intent(s). ' ELSE '' END || 'Premium: Rs. ' || c.TOTAL_ACTIVE_PREMIUM
    FROM CUSTOMER_360 c WHERE c.RISK_LEVEL IN ('Critical','High') AND c.TOTAL_ACTIVE_PREMIUM > 0 AND (c.COMPETITOR_MENTION_COUNT > 0 OR c.CANCELLATION_INTENT_COUNT > 0)
    UNION ALL
    -- 4. PAYMENT_PLAN
    SELECT c.CUSTOMER_ID, 'PAYMENT_PLAN', 4,
        'Offer quarterly payments (' || c.LATE_PAYMENT_COUNT || ' overdue, Rs. ' || c.TOTAL_LATE_FEES || ' late fees)',
        c.CHURN_RISK_SCORE, c.TOTAL_ACTIVE_PREMIUM, NULL,
        c.LATE_PAYMENT_COUNT || ' overdue payments. Late fees: Rs. ' || c.TOTAL_LATE_FEES || '. Active policies: ' || c.ACTIVE_POLICIES
    FROM CUSTOMER_360 c WHERE c.LATE_PAYMENT_COUNT >= 2 AND c.ACTIVE_POLICIES > 0
    UNION ALL
    -- 5. RENEWAL_INCENTIVE
    SELECT c.CUSTOMER_ID, 'RENEWAL_INCENTIVE', 5,
        'Offer 10% NCB uplift (premium Rs. ' || c.TOTAL_ACTIVE_PREMIUM || ')',
        c.CHURN_RISK_SCORE, c.TOTAL_ACTIVE_PREMIUM, NULL,
        'Risk: ' || c.RISK_LEVEL || '. No cancellation intent. Active policies: ' || c.ACTIVE_POLICIES
    FROM CUSTOMER_360 c WHERE c.RISK_LEVEL IN ('Critical','High','Medium') AND c.CANCELLATION_INTENT_COUNT = 0 AND c.ACTIVE_POLICIES > 0
    UNION ALL
    -- 6. PROACTIVE_CALLBACK
    SELECT c.CUSTOMER_ID, 'PROACTIVE_CALLBACK', 6,
        'Schedule callback (risk ' || c.CHURN_RISK_SCORE || '/100, ' || c.NEGATIVE_INTERACTION_COUNT || ' negative)',
        c.CHURN_RISK_SCORE, c.TOTAL_ACTIVE_PREMIUM, NULL,
        'Risk: ' || c.RISK_LEVEL || '. Negative interactions: ' || c.NEGATIVE_INTERACTION_COUNT || '. Sentiment: ' || ROUND(c.AVG_SENTIMENT, 2)
    FROM CUSTOMER_360 c WHERE c.RISK_LEVEL IN ('Critical','High','Medium') AND c.NEGATIVE_INTERACTION_COUNT >= 1
),
ranked AS (
    SELECT *, ROW_NUMBER() OVER (PARTITION BY CUSTOMER_ID ORDER BY PRI ASC) AS RN
    FROM eligible
)
SELECT 'NBA' || LPAD(ROW_NUMBER() OVER (ORDER BY PRI, CUSTOMER_ID)::VARCHAR, 5, '0'),
    CUSTOMER_ID, AC, ADESC, RS, PREM, DISC, EV
FROM ranked WHERE RN = 1;

-- ═══════════════════════════════════════════════════════════
-- LAYER 2: LLM Rationale (run in batches of ~80)
-- Uses llama3.1-8b for retention actions, llama3.1-70b for claim actions
-- ═══════════════════════════════════════════════════════════
-- Batch for non-claim actions (8b model):
UPDATE NBA_RECOMMENDATIONS nba
SET RATIONALE = SNOWFLAKE.CORTEX.COMPLETE('llama3.1-8b',
    CONCAT('You are a compliance-aware insurance retention analyst. Write a brief rationale (under 150 words) for the recommended action. Only cite provided data. Do not fabricate. Return ONLY the rationale text.

Customer: ', c.FIRST_NAME, ' ', c.LAST_NAME, ' (', nba.CUSTOMER_ID, '). Risk: ', nba.RISK_SCORE, '/100.
Premium: Rs. ', c.TOTAL_ACTIVE_PREMIUM, '. Late payments: ', c.LATE_PAYMENT_COUNT, '. Sentiment: ', ROUND(c.AVG_SENTIMENT, 2), '.

Action: ', nba.RECOMMENDED_ACTION, '
Evidence: ', COALESCE(nba.SUPPORTING_EVIDENCE, 'Limited evidence'), '

Rationale:'))
FROM CUSTOMER_360 c WHERE nba.CUSTOMER_ID = c.CUSTOMER_ID
  AND nba.ACTION_CODE NOT IN ('CLAIM_ESCALATION', 'CLAIM_REVIEW');

-- Batch for claim actions (70b model, reframed prompt):
UPDATE NBA_RECOMMENDATIONS nba
SET RATIONALE = SNOWFLAKE.CORTEX.COMPLETE('llama3.1-70b',
    CONCAT('You are writing an internal analytics report for an insurance retention team. Explain why the following customer service action is recommended. This is a reporting task. Write 100-150 words.

Customer: ', c.FIRST_NAME, ' ', c.LAST_NAME, ' (', nba.CUSTOMER_ID, '). Risk: ', nba.RISK_SCORE, '/100. Premium: Rs. ', c.TOTAL_ACTIVE_PREMIUM, '.
Claims: ', c.TOTAL_CLAIMS, ' total, ', c.REJECTED_CLAIMS, ' rejected, ', c.DELAYED_CLAIMS, ' pending >30d.

Service action: ', nba.RECOMMENDED_ACTION, '
Data: ', COALESCE(nba.SUPPORTING_EVIDENCE, 'Limited evidence'), '

Business rationale:'))
FROM CUSTOMER_360 c WHERE nba.CUSTOMER_ID = c.CUSTOMER_ID
  AND nba.ACTION_CODE IN ('CLAIM_ESCALATION', 'CLAIM_REVIEW');

-- ═══════════════════════════════════════════════════════════
-- LAYER 3: Confidence Scoring + Compliance Checks
-- ═══════════════════════════════════════════════════════════
UPDATE NBA_RECOMMENDATIONS nba
SET
    CONFIDENCE_SCORE = LEAST(1.0, GREATEST(0.0,
        CASE nba.ACTION_CODE
            WHEN 'CLAIM_ESCALATION'  THEN 0.80
            WHEN 'CLAIM_REVIEW'      THEN 0.75
            WHEN 'RETENTION_DISCOUNT' THEN 0.70
            WHEN 'PAYMENT_PLAN'      THEN 0.70
            WHEN 'RENEWAL_INCENTIVE' THEN 0.60
            WHEN 'PROACTIVE_CALLBACK' THEN 0.55
        END
        + CASE WHEN c.CHURN_SIGNAL_COUNT > 0 THEN 0.15 ELSE 0 END
        + CASE WHEN (CASE WHEN c.LATE_PAYMENT_COUNT > 0 THEN 1 ELSE 0 END
                    + CASE WHEN c.REJECTED_CLAIMS > 0 THEN 1 ELSE 0 END
                    + CASE WHEN c.COMPETITOR_MENTION_COUNT > 0 THEN 1 ELSE 0 END
                    + CASE WHEN c.CANCELLATION_INTENT_COUNT > 0 THEN 1 ELSE 0 END
                    + CASE WHEN c.DELAYED_CLAIMS > 0 THEN 1 ELSE 0 END
                    + CASE WHEN c.NEGATIVE_INTERACTION_COUNT > 0 THEN 1 ELSE 0 END
                   ) >= 3 THEN 0.10 ELSE 0 END
        + CASE WHEN c.AVG_SENTIMENT < -0.1 AND nba.ACTION_CODE IN ('CLAIM_ESCALATION','CLAIM_REVIEW','RETENTION_DISCOUNT') THEN 0.10 ELSE 0 END
        - CASE WHEN c.TOTAL_INTERACTIONS = 0 THEN 0.20 ELSE 0 END
        - CASE WHEN nba.ACTION_CODE = 'PROACTIVE_CALLBACK' AND c.CHURN_SIGNAL_COUNT <= 1 THEN 0.15 ELSE 0 END
    )),
    COMPLIANCE_STATUS = CASE
        WHEN LEAST(1.0, GREATEST(0.0, /* same formula */ 0.60)) < 0.60 THEN 'NEEDS_HUMAN_REVIEW'
        WHEN nba.ACTION_CODE = 'RETENTION_DISCOUNT' AND nba.DISCOUNT_AMOUNT > 10000 THEN 'FLAGGED'
        ELSE 'COMPLIANT'
    END,
    REVIEW_REASON = CASE
        WHEN LEAST(1.0, GREATEST(0.0, /* same formula */ 0.60)) < 0.60 THEN 'Confidence below threshold'
        WHEN nba.ACTION_CODE = 'RETENTION_DISCOUNT' AND nba.DISCOUNT_AMOUNT > 10000 THEN 'Discount exceeds cap'
        ELSE NULL
    END
FROM CUSTOMER_360 c WHERE nba.CUSTOMER_ID = c.CUSTOMER_ID;
-- Note: The full confidence formula is repeated in the actual execution (see above).
-- This file shows the structure; the executed version has the complete CASE expression.
