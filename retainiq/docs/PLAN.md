# RetainIQ — Development Plan

RetainIQ is a customer-retention copilot for an Indian insurance company,
built entirely on Snowflake with a Streamlit-in-Snowflake frontend.

**Account:** DAAALVW-IS38545  
**Role:** ACCOUNTADMIN  
**Database:** RETAINIQ_DB  
**Schemas:** RAW (raw data), CURATED (enriched views), APP (Streamlit objects + audit)  
**Warehouse:** RETAINIQ_WH (X-Small, auto-suspend 60s)  
**Confirmed Cortex features:** COMPLETE (llama3.1-8b, llama3.1-70b),
SENTIMENT, SUMMARIZE, EXTRACT_ANSWER  
**Milestone 0 status:** COMPLETE

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────┐
│                   Streamlit App                      │
│  (Retention Dashboard + Copilot Chat + Action Panel) │
└──────────────┬──────────────────────┬───────────────┘
               │                      │
       SQL / Python           Cortex COMPLETE
               │                      │
┌──────────────▼──────────────────────▼───────────────┐
│                  Snowflake                           │
│                                                      │
│  ┌────────────┐  ┌──────────────┐  ┌─────────────┐ │
│  │ Base Tables │  │  Views       │  │ Cortex AI   │ │
│  │ customers   │  │ v_churn_risk │  │ SENTIMENT   │ │
│  │ policies    │  │ v_360        │  │ SUMMARIZE   │ │
│  │ claims      │  │              │  │ COMPLETE    │ │
│  │ payments    │  │              │  │             │ │
│  │ interactions│  │              │  │             │ │
│  └────────────┘  └──────────────┘  └─────────────┘ │
│                                                      │
│  ┌──────────────────────────────────────────────┐   │
│  │ Audit Tables: actions, audit_log             │   │
│  └──────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────┘
```

---

## Milestone 0 — Snowflake Foundation

**Goal:** Create the database, schema, and warehouse configuration so every
later milestone has a home.

### Files to Create

| File | Purpose |
|---|---|
| `sql/00_foundation.sql` | DDL for database, schema, warehouse config |

### Snowflake Objects

| Object | Type | Notes |
|---|---|---|
| `RETAINIQ` | Database | Project database |
| `RETAINIQ.PUBLIC` | Schema | Default schema (auto-created) |
| `RETAINIQ.CORE` | Schema | All application tables and views |

### Dependencies

- Active Snowflake connection with ACCOUNTADMIN role.
- Warehouse `COMPUTE_WH` exists (confirmed).

### SQL to Execute

```sql
-- 00_foundation.sql
CREATE DATABASE IF NOT EXISTS RETAINIQ;
CREATE SCHEMA IF NOT EXISTS RETAINIQ.CORE;

-- Set session defaults
USE DATABASE RETAINIQ;
USE SCHEMA CORE;
USE WAREHOUSE COMPUTE_WH;
```

### Verification

```sql
SHOW SCHEMAS IN DATABASE RETAINIQ;
-- Expected: CORE, INFORMATION_SCHEMA, PUBLIC
SELECT CURRENT_DATABASE(), CURRENT_SCHEMA();
-- Expected: RETAINIQ, CORE
```

### Potential Errors

| Error | Cause | Fix |
|---|---|---|
| `Insufficient privileges` | Not using ACCOUNTADMIN | `USE ROLE ACCOUNTADMIN;` |
| `Warehouse does not exist` | Typo in warehouse name | Check with `SHOW WAREHOUSES;` |

---

## Milestone 1 — Base Tables + Synthetic Data

**Goal:** Create the five core tables and populate them with realistic
synthetic data for an Indian insurance company.

### Files to Create

| File | Purpose |
|---|---|
| `sql/01_tables.sql` | DDL for all five base tables |
| `sql/02_seed_data.sql` | INSERT statements with synthetic data |

### Snowflake Objects

| Object | Type | Key Columns |
|---|---|---|
| `CORE.CUSTOMERS` | Table | customer_id, name, age, city, segment, phone, email, created_at |
| `CORE.POLICIES` | Table | policy_id, customer_id, product_type, premium_amount, start_date, end_date, status |
| `CORE.CLAIMS` | Table | claim_id, policy_id, customer_id, claim_date, claim_amount, status, resolution_date |
| `CORE.PAYMENTS` | Table | payment_id, policy_id, customer_id, due_date, paid_date, amount, status |
| `CORE.INTERACTIONS` | Table | interaction_id, customer_id, channel, direction, timestamp, content, summary |

### Dependencies

- Milestone 0 completed (database and schema exist).

### SQL to Execute

```sql
-- 01_tables.sql
USE DATABASE RETAINIQ;
USE SCHEMA CORE;

CREATE OR REPLACE TABLE CUSTOMERS (
    CUSTOMER_ID     VARCHAR(20)   PRIMARY KEY,
    NAME            VARCHAR(100)  NOT NULL,
    AGE             INT,
    GENDER          VARCHAR(10),
    CITY            VARCHAR(50),
    STATE           VARCHAR(50),
    SEGMENT         VARCHAR(20),  -- 'Individual', 'Family', 'Corporate'
    PHONE           VARCHAR(15),
    EMAIL           VARCHAR(100),
    PREFERRED_LANGUAGE VARCHAR(20) DEFAULT 'English',
    CREATED_AT      TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);

CREATE OR REPLACE TABLE POLICIES (
    POLICY_ID       VARCHAR(20)   PRIMARY KEY,
    CUSTOMER_ID     VARCHAR(20)   NOT NULL REFERENCES CUSTOMERS(CUSTOMER_ID),
    PRODUCT_TYPE    VARCHAR(30)   NOT NULL, -- 'Health', 'Life', 'Motor', 'Home'
    PLAN_NAME       VARCHAR(50),
    PREMIUM_AMOUNT  NUMBER(12,2)  NOT NULL,
    PAYMENT_FREQUENCY VARCHAR(15) DEFAULT 'Monthly',
    START_DATE      DATE          NOT NULL,
    END_DATE        DATE          NOT NULL,
    STATUS          VARCHAR(15)   DEFAULT 'Active', -- Active, Lapsed, Cancelled, Expired
    AUTO_RENEW      BOOLEAN       DEFAULT TRUE,
    CREATED_AT      TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);

CREATE OR REPLACE TABLE CLAIMS (
    CLAIM_ID        VARCHAR(20)   PRIMARY KEY,
    POLICY_ID       VARCHAR(20)   NOT NULL REFERENCES POLICIES(POLICY_ID),
    CUSTOMER_ID     VARCHAR(20)   NOT NULL REFERENCES CUSTOMERS(CUSTOMER_ID),
    CLAIM_DATE      DATE          NOT NULL,
    CLAIM_AMOUNT    NUMBER(12,2)  NOT NULL,
    APPROVED_AMOUNT NUMBER(12,2),
    STATUS          VARCHAR(15)   DEFAULT 'Pending', -- Pending, Approved, Rejected, Settled
    CATEGORY        VARCHAR(30),  -- 'Hospitalisation', 'Accident', 'Theft', etc.
    RESOLUTION_DATE DATE,
    NOTES           VARCHAR(500),
    CREATED_AT      TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);

CREATE OR REPLACE TABLE PAYMENTS (
    PAYMENT_ID      VARCHAR(20)   PRIMARY KEY,
    POLICY_ID       VARCHAR(20)   NOT NULL REFERENCES POLICIES(POLICY_ID),
    CUSTOMER_ID     VARCHAR(20)   NOT NULL REFERENCES CUSTOMERS(CUSTOMER_ID),
    DUE_DATE        DATE          NOT NULL,
    PAID_DATE       DATE,
    AMOUNT          NUMBER(12,2)  NOT NULL,
    STATUS          VARCHAR(15)   DEFAULT 'Pending', -- Paid, Pending, Overdue, Failed
    PAYMENT_METHOD  VARCHAR(20),  -- 'UPI', 'NetBanking', 'Card', 'AutoDebit'
    CREATED_AT      TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);

CREATE OR REPLACE TABLE INTERACTIONS (
    INTERACTION_ID  VARCHAR(20)   PRIMARY KEY,
    CUSTOMER_ID     VARCHAR(20)   NOT NULL REFERENCES CUSTOMERS(CUSTOMER_ID),
    CHANNEL         VARCHAR(15)   NOT NULL, -- 'Call', 'Email', 'Chat', 'WhatsApp'
    DIRECTION       VARCHAR(10)   NOT NULL, -- 'Inbound', 'Outbound'
    INTERACTION_TS  TIMESTAMP_NTZ NOT NULL,
    CONTENT         VARCHAR(5000) NOT NULL, -- Full transcript or email body
    SUMMARY         VARCHAR(500),           -- AI-generated summary (filled later)
    SENTIMENT_SCORE FLOAT,                  -- AI-generated (-1 to 1, filled later)
    CREATED_AT      TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);
```

The `02_seed_data.sql` file will contain ~50 customers, ~80 policies,
~40 claims, ~200 payments, and ~60 interactions with realistic Indian
names, cities (Mumbai, Delhi, Bengaluru, Chennai, Pune, Hyderabad, etc.),
and insurance scenarios.

**Key synthetic data patterns to include:**

- **Happy path customers:** Regular payments, no claims, high satisfaction.
- **At-risk customers:** Missed payments, recent complaints, claim rejections.
- **Lapsed customers:** Stopped paying, policy expired.
- **High-value customers:** Multiple policies, large premiums.
- **Interaction content:** Realistic call transcripts and emails showing
  frustration, questions about renewals, claim follow-ups, etc.

### Verification

```sql
SELECT 'CUSTOMERS' AS TBL, COUNT(*) AS ROWS FROM CORE.CUSTOMERS
UNION ALL SELECT 'POLICIES', COUNT(*) FROM CORE.POLICIES
UNION ALL SELECT 'CLAIMS', COUNT(*) FROM CORE.CLAIMS
UNION ALL SELECT 'PAYMENTS', COUNT(*) FROM CORE.PAYMENTS
UNION ALL SELECT 'INTERACTIONS', COUNT(*) FROM CORE.INTERACTIONS;
-- Expected: rows > 0 for each table

-- Spot-check referential integrity
SELECT c.CUSTOMER_ID, COUNT(p.POLICY_ID) AS POLICY_COUNT
FROM CORE.CUSTOMERS c
LEFT JOIN CORE.POLICIES p ON c.CUSTOMER_ID = p.CUSTOMER_ID
GROUP BY c.CUSTOMER_ID
ORDER BY POLICY_COUNT DESC
LIMIT 5;
```

### Potential Errors

| Error | Cause | Fix |
|---|---|---|
| `Foreign key constraint violated` | Inserting policy before customer | Insert customers first, then policies, then claims/payments |
| `String too long` | Interaction content exceeds 5000 chars | Trim transcripts or increase column width |
| `Database/schema not found` | Milestone 0 not run | Run `00_foundation.sql` first |

---

## Milestone 2 — AI Enrichment (Sentiment + Summaries)

**Goal:** Use Cortex AI to enrich the INTERACTIONS table with sentiment
scores and auto-generated summaries. This turns raw text into structured
signals for churn analysis.

### Files to Create

| File | Purpose |
|---|---|
| `sql/03_ai_enrichment.sql` | UPDATE statements using Cortex functions |

### Snowflake Objects

No new objects. Updates existing `CORE.INTERACTIONS` rows.

### Dependencies

- Milestone 1 completed (tables populated with data).
- Cortex SENTIMENT and SUMMARIZE confirmed working.

### SQL to Execute

```sql
-- 03_ai_enrichment.sql
USE DATABASE RETAINIQ;
USE SCHEMA CORE;

-- Add sentiment scores to all interactions
UPDATE INTERACTIONS
SET SENTIMENT_SCORE = SNOWFLAKE.CORTEX.SENTIMENT(CONTENT)
WHERE SENTIMENT_SCORE IS NULL;

-- Add AI summaries to interactions that lack them
UPDATE INTERACTIONS
SET SUMMARY = SNOWFLAKE.CORTEX.SUMMARIZE(CONTENT)
WHERE SUMMARY IS NULL;
```

### Verification

```sql
-- Check enrichment completeness
SELECT
    COUNT(*) AS TOTAL,
    COUNT(SENTIMENT_SCORE) AS HAS_SENTIMENT,
    COUNT(SUMMARY) AS HAS_SUMMARY,
    AVG(SENTIMENT_SCORE) AS AVG_SENTIMENT
FROM CORE.INTERACTIONS;
-- Expected: HAS_SENTIMENT = TOTAL, HAS_SUMMARY = TOTAL

-- Spot-check: most negative interactions
SELECT CUSTOMER_ID, CHANNEL, SENTIMENT_SCORE, SUMMARY
FROM CORE.INTERACTIONS
ORDER BY SENTIMENT_SCORE ASC
LIMIT 5;
```

### Potential Errors

| Error | Cause | Fix |
|---|---|---|
| `Cortex function not available` | Region/account issue | Verify with `SELECT SNOWFLAKE.CORTEX.SENTIMENT('test')` |
| Timeout on large batch | Too many rows at once | Add `LIMIT 20` and run in batches |
| Credits consumed quickly | LLM calls cost credits | Monitor with `SELECT * FROM SNOWFLAKE.ACCOUNT_USAGE.METERING_HISTORY WHERE SERVICE_TYPE = 'AI_SERVICES'` |

---

## Milestone 3 — Churn Risk Scoring View

**Goal:** Create a SQL view that computes an explainable churn-risk score
for every active customer. The score is rule-based (not ML), making it
transparent and auditable.

### Files to Create

| File | Purpose |
|---|---|
| `sql/04_churn_risk_view.sql` | View definition with risk logic |

### Snowflake Objects

| Object | Type | Notes |
|---|---|---|
| `CORE.V_CHURN_RISK` | View | Computed churn score + explanation |

### Dependencies

- Milestone 2 completed (sentiment scores populated).

### SQL to Execute

```sql
-- 04_churn_risk_view.sql
USE DATABASE RETAINIQ;
USE SCHEMA CORE;

CREATE OR REPLACE VIEW V_CHURN_RISK AS
WITH payment_stats AS (
    SELECT
        CUSTOMER_ID,
        COUNT(CASE WHEN STATUS = 'Overdue' THEN 1 END) AS OVERDUE_COUNT,
        COUNT(CASE WHEN STATUS = 'Failed' THEN 1 END) AS FAILED_COUNT,
        MAX(CASE WHEN STATUS = 'Paid' THEN PAID_DATE END) AS LAST_PAID_DATE
    FROM CORE.PAYMENTS
    GROUP BY CUSTOMER_ID
),
claim_stats AS (
    SELECT
        CUSTOMER_ID,
        COUNT(CASE WHEN STATUS = 'Rejected' THEN 1 END) AS REJECTED_CLAIMS,
        COUNT(*) AS TOTAL_CLAIMS,
        AVG(DATEDIFF('day', CLAIM_DATE, COALESCE(RESOLUTION_DATE, CURRENT_DATE()))) AS AVG_RESOLUTION_DAYS
    FROM CORE.CLAIMS
    GROUP BY CUSTOMER_ID
),
interaction_stats AS (
    SELECT
        CUSTOMER_ID,
        COUNT(*) AS INTERACTION_COUNT,
        AVG(SENTIMENT_SCORE) AS AVG_SENTIMENT,
        MIN(SENTIMENT_SCORE) AS MIN_SENTIMENT,
        COUNT(CASE WHEN SENTIMENT_SCORE < -0.3 THEN 1 END) AS NEGATIVE_INTERACTIONS
    FROM CORE.INTERACTIONS
    GROUP BY CUSTOMER_ID
),
policy_stats AS (
    SELECT
        CUSTOMER_ID,
        COUNT(*) AS POLICY_COUNT,
        SUM(PREMIUM_AMOUNT) AS TOTAL_PREMIUM,
        MIN(END_DATE) AS NEAREST_RENEWAL,
        COUNT(CASE WHEN STATUS IN ('Lapsed', 'Cancelled') THEN 1 END) AS INACTIVE_POLICIES
    FROM CORE.POLICIES
    GROUP BY CUSTOMER_ID
)
SELECT
    c.CUSTOMER_ID,
    c.NAME,
    c.CITY,
    c.SEGMENT,
    ps.POLICY_COUNT,
    ps.TOTAL_PREMIUM,
    ps.NEAREST_RENEWAL,
    COALESCE(pay.OVERDUE_COUNT, 0)       AS OVERDUE_PAYMENTS,
    COALESCE(cl.REJECTED_CLAIMS, 0)      AS REJECTED_CLAIMS,
    COALESCE(cl.AVG_RESOLUTION_DAYS, 0)  AS AVG_CLAIM_RESOLUTION_DAYS,
    COALESCE(ix.AVG_SENTIMENT, 0)        AS AVG_SENTIMENT,
    COALESCE(ix.NEGATIVE_INTERACTIONS, 0) AS NEGATIVE_INTERACTIONS,

    -- Risk score: 0 (safe) to 100 (very likely to churn)
    LEAST(100, GREATEST(0,
        (COALESCE(pay.OVERDUE_COUNT, 0) * 15)
      + (COALESCE(pay.FAILED_COUNT, 0) * 10)
      + (COALESCE(cl.REJECTED_CLAIMS, 0) * 20)
      + (CASE WHEN COALESCE(cl.AVG_RESOLUTION_DAYS, 0) > 30 THEN 15 ELSE 0 END)
      + (CASE WHEN COALESCE(ix.AVG_SENTIMENT, 0) < -0.2 THEN 20 ELSE 0 END)
      + (COALESCE(ix.NEGATIVE_INTERACTIONS, 0) * 5)
      + (CASE WHEN ps.NEAREST_RENEWAL <= DATEADD('day', 30, CURRENT_DATE()) THEN 10 ELSE 0 END)
      + (COALESCE(ps.INACTIVE_POLICIES, 0) * 10)
    )) AS CHURN_RISK_SCORE,

    -- Human-readable explanation
    ARRAY_TO_STRING(ARRAY_COMPACT(ARRAY_CONSTRUCT(
        CASE WHEN COALESCE(pay.OVERDUE_COUNT, 0) > 0
             THEN pay.OVERDUE_COUNT || ' overdue payment(s)' END,
        CASE WHEN COALESCE(cl.REJECTED_CLAIMS, 0) > 0
             THEN cl.REJECTED_CLAIMS || ' rejected claim(s)' END,
        CASE WHEN COALESCE(cl.AVG_RESOLUTION_DAYS, 0) > 30
             THEN 'Slow claim resolution (' || ROUND(cl.AVG_RESOLUTION_DAYS) || ' days avg)' END,
        CASE WHEN COALESCE(ix.AVG_SENTIMENT, 0) < -0.2
             THEN 'Negative sentiment (avg ' || ROUND(ix.AVG_SENTIMENT, 2) || ')' END,
        CASE WHEN COALESCE(ix.NEGATIVE_INTERACTIONS, 0) > 0
             THEN ix.NEGATIVE_INTERACTIONS || ' negative interaction(s)' END,
        CASE WHEN ps.NEAREST_RENEWAL <= DATEADD('day', 30, CURRENT_DATE())
             THEN 'Policy renewal within 30 days' END,
        CASE WHEN COALESCE(ps.INACTIVE_POLICIES, 0) > 0
             THEN ps.INACTIVE_POLICIES || ' lapsed/cancelled policy(ies)' END
    )), ', ') AS RISK_FACTORS,

    CASE
        WHEN LEAST(100, GREATEST(0,
            (COALESCE(pay.OVERDUE_COUNT, 0) * 15)
          + (COALESCE(pay.FAILED_COUNT, 0) * 10)
          + (COALESCE(cl.REJECTED_CLAIMS, 0) * 20)
          + (CASE WHEN COALESCE(cl.AVG_RESOLUTION_DAYS, 0) > 30 THEN 15 ELSE 0 END)
          + (CASE WHEN COALESCE(ix.AVG_SENTIMENT, 0) < -0.2 THEN 20 ELSE 0 END)
          + (COALESCE(ix.NEGATIVE_INTERACTIONS, 0) * 5)
          + (CASE WHEN ps.NEAREST_RENEWAL <= DATEADD('day', 30, CURRENT_DATE()) THEN 10 ELSE 0 END)
          + (COALESCE(ps.INACTIVE_POLICIES, 0) * 10)
        )) >= 60 THEN 'Critical'
        WHEN LEAST(100, GREATEST(0,
            (COALESCE(pay.OVERDUE_COUNT, 0) * 15)
          + (COALESCE(pay.FAILED_COUNT, 0) * 10)
          + (COALESCE(cl.REJECTED_CLAIMS, 0) * 20)
          + (CASE WHEN COALESCE(cl.AVG_RESOLUTION_DAYS, 0) > 30 THEN 15 ELSE 0 END)
          + (CASE WHEN COALESCE(ix.AVG_SENTIMENT, 0) < -0.2 THEN 20 ELSE 0 END)
          + (COALESCE(ix.NEGATIVE_INTERACTIONS, 0) * 5)
          + (CASE WHEN ps.NEAREST_RENEWAL <= DATEADD('day', 30, CURRENT_DATE()) THEN 10 ELSE 0 END)
          + (COALESCE(ps.INACTIVE_POLICIES, 0) * 10)
        )) >= 30 THEN 'Medium'
        ELSE 'Low'
    END AS RISK_LEVEL

FROM CORE.CUSTOMERS c
LEFT JOIN policy_stats ps    ON c.CUSTOMER_ID = ps.CUSTOMER_ID
LEFT JOIN payment_stats pay  ON c.CUSTOMER_ID = pay.CUSTOMER_ID
LEFT JOIN claim_stats cl     ON c.CUSTOMER_ID = cl.CUSTOMER_ID
LEFT JOIN interaction_stats ix ON c.CUSTOMER_ID = ix.CUSTOMER_ID;
```

### Verification

```sql
SELECT RISK_LEVEL, COUNT(*) AS CUSTOMER_COUNT
FROM CORE.V_CHURN_RISK
GROUP BY RISK_LEVEL;
-- Expected: mix of Critical, Medium, Low

SELECT NAME, CHURN_RISK_SCORE, RISK_LEVEL, RISK_FACTORS
FROM CORE.V_CHURN_RISK
ORDER BY CHURN_RISK_SCORE DESC
LIMIT 10;
-- Expected: top-risk customers with readable explanations
```

### Potential Errors

| Error | Cause | Fix |
|---|---|---|
| `ARRAY_COMPACT not found` | Older Snowflake version | Replace with nested IFF/CASE logic |
| All scores are 0 | Seed data has no risk patterns | Adjust seed data to include overdue payments, rejected claims, etc. |
| Division by zero | Edge case in averages | Already handled with COALESCE defaults |

---

## Milestone 4 — Customer 360 View

**Goal:** Create a single unified view that joins all data sources for any
customer, giving the Streamlit app a single query to power the detail page.

### Files to Create

| File | Purpose |
|---|---|
| `sql/05_customer_360_view.sql` | Unified customer view |

### Snowflake Objects

| Object | Type |
|---|---|
| `CORE.V_CUSTOMER_360` | View |

### Dependencies

- Milestone 3 completed.

### SQL to Execute

```sql
-- 05_customer_360_view.sql
CREATE OR REPLACE VIEW CORE.V_CUSTOMER_360 AS
SELECT
    cr.*,
    -- Recent interactions (last 3)
    (SELECT ARRAY_AGG(OBJECT_CONSTRUCT(
        'channel', i.CHANNEL,
        'date', i.INTERACTION_TS::VARCHAR,
        'sentiment', i.SENTIMENT_SCORE,
        'summary', i.SUMMARY
     )) WITHIN GROUP (ORDER BY i.INTERACTION_TS DESC)
     FROM (SELECT * FROM CORE.INTERACTIONS
           WHERE CUSTOMER_ID = cr.CUSTOMER_ID
           ORDER BY INTERACTION_TS DESC LIMIT 3) i
    ) AS RECENT_INTERACTIONS,
    -- Active policies detail
    (SELECT ARRAY_AGG(OBJECT_CONSTRUCT(
        'policy_id', p.POLICY_ID,
        'product', p.PRODUCT_TYPE,
        'premium', p.PREMIUM_AMOUNT,
        'end_date', p.END_DATE::VARCHAR,
        'status', p.STATUS
     ))
     FROM CORE.POLICIES p
     WHERE p.CUSTOMER_ID = cr.CUSTOMER_ID
    ) AS ALL_POLICIES
FROM CORE.V_CHURN_RISK cr;
```

### Verification

```sql
SELECT CUSTOMER_ID, NAME, CHURN_RISK_SCORE, RISK_FACTORS,
       RECENT_INTERACTIONS, ALL_POLICIES
FROM CORE.V_CUSTOMER_360
WHERE CHURN_RISK_SCORE > 30
LIMIT 3;
```

### Potential Errors

| Error | Cause | Fix |
|---|---|---|
| Correlated subquery slow | Large data volume | For MVP data sizes this is fine; optimise later if needed |

---

## Milestone 5 — Action & Audit Tables

**Goal:** Create tables for retention managers to record their decisions
(approve/edit/reject recommendations) and maintain a full audit trail.

### Files to Create

| File | Purpose |
|---|---|
| `sql/06_action_audit_tables.sql` | DDL for action and audit tables |

### Snowflake Objects

| Object | Type | Key Columns |
|---|---|---|
| `CORE.RETENTION_ACTIONS` | Table | action_id, customer_id, recommended_action, final_action, status, manager_notes, created_at, decided_at |
| `CORE.AUDIT_LOG` | Table | log_id, action_id, event_type, old_value, new_value, performed_by, timestamp |

### Dependencies

- Milestone 1 completed (CUSTOMERS table exists).

### SQL to Execute

```sql
-- 06_action_audit_tables.sql
CREATE OR REPLACE TABLE CORE.RETENTION_ACTIONS (
    ACTION_ID           VARCHAR(20)   PRIMARY KEY,
    CUSTOMER_ID         VARCHAR(20)   NOT NULL REFERENCES CUSTOMERS(CUSTOMER_ID),
    RISK_SCORE_AT_TIME  INT,
    RISK_FACTORS_AT_TIME VARCHAR(1000),
    RECOMMENDED_ACTION  VARCHAR(500)  NOT NULL,
    FINAL_ACTION        VARCHAR(500),
    STATUS              VARCHAR(15)   DEFAULT 'Pending', -- Pending, Approved, Edited, Rejected
    MANAGER_NOTES       VARCHAR(1000),
    CREATED_AT          TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    DECIDED_AT          TIMESTAMP_NTZ,
    DECIDED_BY          VARCHAR(100)
);

CREATE OR REPLACE TABLE CORE.AUDIT_LOG (
    LOG_ID       VARCHAR(30)    PRIMARY KEY,
    ACTION_ID    VARCHAR(20)    REFERENCES RETENTION_ACTIONS(ACTION_ID),
    EVENT_TYPE   VARCHAR(30)    NOT NULL, -- 'CREATED', 'APPROVED', 'EDITED', 'REJECTED', 'COPILOT_QUERY'
    OLD_VALUE    VARIANT,
    NEW_VALUE    VARIANT,
    PERFORMED_BY VARCHAR(100)   DEFAULT CURRENT_USER(),
    EVENT_TS     TIMESTAMP_NTZ  DEFAULT CURRENT_TIMESTAMP()
);
```

### Verification

```sql
SHOW TABLES LIKE '%ACTION%' IN SCHEMA CORE;
SHOW TABLES LIKE '%AUDIT%' IN SCHEMA CORE;
DESCRIBE TABLE CORE.RETENTION_ACTIONS;
DESCRIBE TABLE CORE.AUDIT_LOG;
```

### Potential Errors

| Error | Cause | Fix |
|---|---|---|
| `Referential integrity violation` | CUSTOMER_ID does not exist | Ensure Milestone 1 data is loaded first |

---

## Milestone 6 — Copilot Backend (Cortex LLM)

**Goal:** Create a stored procedure that takes a natural-language question,
builds a context-aware prompt with customer data, calls Cortex COMPLETE,
and returns an answer with next-best-action recommendations.

### Files to Create

| File | Purpose |
|---|---|
| `sql/07_copilot_procedure.sql` | Stored procedure for the copilot |

### Snowflake Objects

| Object | Type |
|---|---|
| `CORE.SP_COPILOT_ASK` | Stored Procedure (SQL) |

### Dependencies

- Milestones 4 and 5 completed (V_CUSTOMER_360 and RETENTION_ACTIONS exist).
- Cortex COMPLETE confirmed working with `llama3.1-70b`.

### SQL to Execute

```sql
-- 07_copilot_procedure.sql
CREATE OR REPLACE PROCEDURE CORE.SP_COPILOT_ASK(
    P_CUSTOMER_ID VARCHAR,
    P_QUESTION VARCHAR
)
RETURNS VARCHAR
LANGUAGE SQL
AS
$$
DECLARE
    v_context VARCHAR;
    v_prompt VARCHAR;
    v_response VARCHAR;
BEGIN
    -- Gather customer context
    SELECT CONCAT(
        'Customer: ', NAME,
        ' | City: ', CITY,
        ' | Segment: ', SEGMENT,
        ' | Policies: ', COALESCE(POLICY_COUNT::VARCHAR, '0'),
        ' | Total Premium: INR ', COALESCE(TOTAL_PREMIUM::VARCHAR, '0'),
        ' | Churn Risk: ', CHURN_RISK_SCORE, '/100 (', RISK_LEVEL, ')',
        ' | Risk Factors: ', COALESCE(RISK_FACTORS, 'None'),
        ' | Overdue Payments: ', OVERDUE_PAYMENTS,
        ' | Rejected Claims: ', REJECTED_CLAIMS,
        ' | Avg Sentiment: ', ROUND(AVG_SENTIMENT, 2)
    ) INTO :v_context
    FROM CORE.V_CHURN_RISK
    WHERE CUSTOMER_ID = :P_CUSTOMER_ID;

    -- Build prompt
    v_prompt := CONCAT(
        'You are RetainIQ, a customer retention copilot for an Indian insurance company. ',
        'You help retention managers reduce customer churn with data-driven, compliant recommendations. ',
        'Always be specific, cite the data, and suggest concrete next-best actions. ',
        'Never recommend anything that violates IRDAI (Insurance Regulatory and Development Authority of India) guidelines. ',
        CHR(10), CHR(10),
        'CUSTOMER DATA:', CHR(10),
        :v_context,
        CHR(10), CHR(10),
        'MANAGER QUESTION: ', :P_QUESTION,
        CHR(10), CHR(10),
        'Respond with:',
        CHR(10), '1. A clear answer to the question.',
        CHR(10), '2. Top 3 recommended next-best actions ranked by likely impact.',
        CHR(10), '3. Any compliance considerations.',
        CHR(10), 'Keep the response under 300 words.'
    );

    -- Call Cortex LLM
    SELECT SNOWFLAKE.CORTEX.COMPLETE('llama3.1-70b', :v_prompt)
    INTO :v_response;

    RETURN :v_response;
END;
$$;
```

### Verification

```sql
-- Replace CUST001 with an actual customer_id from your seed data
CALL CORE.SP_COPILOT_ASK('CUST001', 'Why is this customer at risk of churning?');
CALL CORE.SP_COPILOT_ASK('CUST001', 'What discount can I offer to retain them?');
```

### Potential Errors

| Error | Cause | Fix |
|---|---|---|
| `NULL result` | Customer ID not found | Validate customer_id exists before calling |
| `Model not available` | Model name changed | Try `llama3.1-8b` as a fallback |
| Slow response (>10s) | Large prompt + 70b model | Switch to `llama3.1-8b` for faster (but less detailed) responses |
| Credit usage spike | Many LLM calls | Use `llama3.1-8b` for development, `llama3.1-70b` for demo |

---

## Milestone 7 — Streamlit App (MVP)

**Goal:** Build a Streamlit-in-Snowflake app with three pages:
1. **Dashboard** — churn risk overview with filters.
2. **Customer Detail** — 360 view + copilot chat.
3. **Action Queue** — approve/edit/reject recommendations.

### Files to Create

| File | Purpose |
|---|---|
| `streamlit/retainiq_app.py` | Main Streamlit application |

### Snowflake Objects

| Object | Type |
|---|---|
| `RETAINIQ.CORE.RETAINIQ_APP` | Streamlit App |

### Dependencies

- All milestones 0-6 completed.
- Streamlit-in-Snowflake enabled (confirmed).

### App Structure

```
retainiq_app.py
├── Page: Dashboard
│   ├── Metric cards (total customers, at-risk, critical)
│   ├── Risk distribution bar chart
│   ├── Sortable/filterable risk table
│   └── Click-through to customer detail
│
├── Page: Customer Detail
│   ├── Customer info header
│   ├── Risk score gauge + factor breakdown
│   ├── Policy/claim/payment summaries
│   ├── Interaction timeline with sentiment
│   └── Copilot chat (calls SP_COPILOT_ASK)
│
└── Page: Action Queue
    ├── Pending recommendations list
    ├── Approve / Edit / Reject buttons
    ├── Manager notes field
    └── Audit log viewer
```

### Deploy Command

```sql
-- Deploy via Snowflake SQL (after creating the .py file)
CREATE OR REPLACE STREAMLIT RETAINIQ.CORE.RETAINIQ_APP
    ROOT_LOCATION = '@RETAINIQ.CORE.STREAMLIT_STAGE'
    MAIN_FILE = 'retainiq_app.py'
    QUERY_WAREHOUSE = 'COMPUTE_WH'
    TITLE = 'RetainIQ - Customer Retention Copilot';
```

Alternatively, deploy via Cortex Code CLI (easier for iterating):
```
snow streamlit deploy --database RETAINIQ --schema CORE
```

### Verification

1. Open the Streamlit app URL from Snowsight.
2. Dashboard loads with customer risk data.
3. Click a customer — detail page shows 360 view.
4. Ask the copilot a question — get an LLM-generated response.
5. Create a recommendation — approve it — see it in the audit log.

### Potential Errors

| Error | Cause | Fix |
|---|---|---|
| `ModuleNotFoundError` | Missing import | Use only packages available in SiS: streamlit, pandas, snowflake-snowpark-python, plotly |
| `Stage not found` | Stage not created | `CREATE STAGE IF NOT EXISTS RETAINIQ.CORE.STREAMLIT_STAGE;` |
| App loads but no data | Wrong database context | Ensure app uses fully qualified table names: `RETAINIQ.CORE.V_CHURN_RISK` |
| Session timeout | Long copilot response | Add `st.spinner('Thinking...')` around LLM calls |

---

## Milestone 8 — Polish and Demo Prep

**Goal:** Final touches for the hackathon demo.

### Tasks

| Task | Detail |
|---|---|
| Branded UI | Add RetainIQ logo, colour theme, tagline |
| Error handling | Wrap all SQL/LLM calls in try/except with user-friendly messages |
| Demo script | Prepare a 3-minute walkthrough: Dashboard → pick a risky customer → ask copilot → approve action → show audit log |
| README | Write `README.md` with project summary, setup steps, architecture diagram, and screenshots |
| .gitignore | Add Snowflake credentials, `__pycache__`, `.env` |

### Files to Create/Update

| File | Purpose |
|---|---|
| `README.md` | Project overview + setup instructions |
| `.gitignore` | Standard Python + Snowflake ignores |
| `docs/DEMO_SCRIPT.md` | Step-by-step demo walkthrough |

---

## Full File Tree (End State)

```
retainiq/
├── docs/
│   ├── PLAN.md              ← this file
│   └── DEMO_SCRIPT.md
├── sql/
│   ├── 00_foundation.sql
│   ├── 01_tables.sql
│   ├── 02_seed_data.sql
│   ├── 03_ai_enrichment.sql
│   ├── 04_churn_risk_view.sql
│   ├── 05_customer_360_view.sql
│   ├── 06_action_audit_tables.sql
│   └── 07_copilot_procedure.sql
├── streamlit/
│   └── retainiq_app.py
├── .gitignore
└── README.md
```

## Execution Order

```
Milestone 0  →  1  →  2  →  3  →  4  →  5  →  6  →  7  →  8
Foundation   Data  AI     Risk   360   Audit  LLM   App   Demo
                  Enrich  View   View  Trail  Copilot
```

Each milestone is independently testable. You can demo a partial product
after milestone 3 (risk dashboard without copilot) or milestone 6
(copilot works in SQL, no UI yet).

## Credit Usage Estimates

| Feature | Approx Cost | Notes |
|---|---|---|
| Warehouse (X-Small) | 1 credit/hour | Auto-suspends after 5 min |
| SENTIMENT (60 rows) | <0.01 credits | Very cheap |
| SUMMARIZE (60 rows) | ~0.05 credits | Moderate |
| COMPLETE per call | ~0.01-0.05 credits | Depends on model + prompt size |
| **Total for MVP dev** | **~2-5 credits** | Well within trial limits |

## Key Design Decisions

1. **Rule-based churn scoring** over ML — transparent, auditable, no training needed, works with small synthetic datasets.
2. **llama3.1-70b** for copilot — best available model on this account for quality; fall back to 8b for speed.
3. **Streamlit-in-Snowflake** over external app — zero infrastructure, data never leaves Snowflake, built-in auth.
4. **Stored procedure for copilot** — keeps prompt logic in SQL, callable from Streamlit and SQL console.
5. **Audit via separate table** — not Snowflake streams (simpler for a hackathon, explicit control).
