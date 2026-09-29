# Plan: Next Best Action Recommendation Engine

## Architecture

The engine has **three layers**, each with a clear responsibility:

```
Layer 1: Deterministic Eligibility (SQL rules)
  ↓ eligible customers + action type
Layer 2: LLM Rationale (Cortex COMPLETE)
  ↓ human-readable rationale + evidence
Layer 3: Confidence + Compliance (SQL post-processing)
  ↓ final recommendations with scores and flags
```

**Why this split:** Business rules (who gets what action) must be auditable and deterministic — no LLM involvement. The LLM is only used to generate the narrative rationale from pre-selected evidence, never to decide eligibility.

---

## Action Catalog (6 Actions)

| # | Action Code | Action Name | Trigger Condition (SQL) | Max Discount / Limit | Compliance Rule |
|---|---|---|---|---|---|
| 1 | `CLAIM_ESCALATION` | Escalate Pending Claim | Customer has ≥1 claim in Pending status >30 days | N/A | Must reference a real CLAIM_ID in Pending status |
| 2 | `RETENTION_DISCOUNT` | Offer Retention Discount | Risk ≥ High AND active premium > 0 AND competitor mentioned OR cancellation intent | Max 15% of annual premium, cap Rs. 10,000 | No discount based on age, gender, or language |
| 3 | `PAYMENT_PLAN` | Offer Flexible Payment Plan | ≥2 overdue/failed payments AND has active policy | Switch from Annual to Quarterly | Cannot waive existing late fees without manager approval |
| 4 | `PROACTIVE_CALLBACK` | Schedule Proactive Callback | Risk ≥ Medium AND ≥1 negative interaction AND no action already recommended | Must be within business hours | No callback for Low-risk customers (cost efficiency) |
| 5 | `CLAIM_REVIEW` | Re-review Rejected Claim | Has ≥1 Rejected claim AND customer has complained about it (claim_enquiry + claim_delay churn signal) | N/A | Must reference real CLAIM_ID and rejection reason |
| 6 | `RENEWAL_INCENTIVE` | Early Renewal Incentive | Active policy AND risk ≥ Medium AND no cancellation intent | Max 10% NCB bonus uplift | Do not combine with RETENTION_DISCOUNT for same customer |

### Priority Order

When a customer qualifies for multiple actions, select the **highest priority** one:

1. `CLAIM_ESCALATION` (most time-sensitive)
2. `CLAIM_REVIEW` (dispute resolution)
3. `RETENTION_DISCOUNT` (direct save)
4. `PAYMENT_PLAN` (financial flexibility)
5. `RENEWAL_INCENTIVE` (preemptive)
6. `PROACTIVE_CALLBACK` (catch-all)

---

## Table Design

### `CURATED.ACTION_CATALOG` (reference table)

| Column | Type | Description |
|---|---|---|
| ACTION_CODE | VARCHAR(30) PK | e.g., CLAIM_ESCALATION |
| ACTION_NAME | VARCHAR(100) | Human-readable name |
| DESCRIPTION | VARCHAR(500) | What this action does |
| PRIORITY | INT | 1=highest |
| MAX_DISCOUNT_PCT | FLOAT | NULL if N/A |
| MAX_DISCOUNT_AMT | NUMBER(12,2) | NULL if N/A |
| COMPLIANCE_NOTES | VARCHAR(500) | Guardrails |

### `CURATED.NBA_RECOMMENDATIONS` (output table)

| Column | Type | Description |
|---|---|---|
| RECOMMENDATION_ID | VARCHAR(20) PK | Auto-generated |
| CUSTOMER_ID | VARCHAR(10) FK | |
| ACTION_CODE | VARCHAR(30) FK | From ACTION_CATALOG |
| RECOMMENDED_ACTION | VARCHAR(200) | e.g., "Escalate claim CLM00042 to senior claims officer" |
| RATIONALE | VARCHAR(2000) | LLM-generated, grounded in data |
| SUPPORTING_EVIDENCE | VARCHAR(2000) | Specific data points and transcript quotes |
| RISK_SCORE | INT | Customer's CHURN_RISK_SCORE at time of recommendation |
| CONFIDENCE_SCORE | FLOAT | 0.0 to 1.0, computed from evidence strength |
| COMPLIANCE_STATUS | VARCHAR(20) | COMPLIANT, NEEDS_HUMAN_REVIEW, FLAGGED |
| REVIEW_REASON | VARCHAR(200) | NULL if COMPLIANT; reason otherwise |
| PREMIUM_AT_RISK | NUMBER(12,2) | Customer's active premium |
| DISCOUNT_AMOUNT | NUMBER(12,2) | NULL unless RETENTION_DISCOUNT |
| CREATED_AT | TIMESTAMP_NTZ | |

---

## Confidence Scoring Formula

```
confidence = base_score
  + 0.15 if customer has interaction evidence (churn_signal != 'none')
  + 0.10 if customer has ≥3 supporting data points
  + 0.10 if sentiment aligns with action (negative for escalation/discount)
  - 0.20 if no transcript evidence exists for this customer
  - 0.15 if action relies on a single data point
```

Base scores by action:
- CLAIM_ESCALATION: 0.80 (hard evidence: claim exists in Pending)
- CLAIM_REVIEW: 0.75 (claim exists + rejection reason exists)
- RETENTION_DISCOUNT: 0.70 (competitor mention or cancellation intent)
- PAYMENT_PLAN: 0.70 (overdue count is hard data)
- RENEWAL_INCENTIVE: 0.60 (preemptive, less certain)
- PROACTIVE_CALLBACK: 0.55 (weakest signal)

If final confidence < 0.60 → set COMPLIANCE_STATUS = 'NEEDS_HUMAN_REVIEW'.

---

## LLM Usage (Layer 2)

The LLM generates RATIONALE and SUPPORTING_EVIDENCE only. It receives a strict prompt:

```
You are a compliance-aware retention analyst. Given the customer data below,
write a brief rationale for the recommended action.

Rules:
- Only cite data provided in the context. Do not fabricate quotes or numbers.
- Reference specific CLAIM_IDs, amounts, and dates from the data.
- If evidence is weak, say so explicitly.
- Keep rationale under 200 words.

Customer data: [structured fields from CUSTOMER_360]
Recommended action: [from eligibility SQL]
```

The LLM call uses `llama3.1-8b` for cost efficiency (1,500 calls at ~0.15 credits).

---

## Compliance Guardrails

| Rule | Implementation |
|---|---|
| No sensitive attributes for eligibility | SQL rules use only: risk_score, claim_status, payment_status, competitor_mention, cancellation_intent, premium |
| Discount caps | SQL enforces LEAST(premium * 0.15, 10000) |
| No cross-sell for at-risk | Action catalog has no cross-sell action |
| Real claim references | JOIN to RAW.CLAIMS ensures CLAIM_ID exists |
| Evidence required | Confidence drops 0.20 if no transcript evidence |
| Human review threshold | NEEDS_HUMAN_REVIEW when confidence < 0.60 |

---

## Testing Plan

For each of the 6 actions, I will:

1. Write a test query that selects a known customer who should qualify
2. Verify the eligibility SQL matches them
3. Check that ineligible customers are excluded
4. Verify confidence score and compliance status
5. Show expected vs actual results

Test cases:
- **CLAIM_ESCALATION:** Customer with pending claim >30 days
- **CLAIM_REVIEW:** Customer with rejected claim + complaint interaction
- **RETENTION_DISCOUNT:** Critical-risk customer with competitor mention (verify discount cap)
- **PAYMENT_PLAN:** Customer with 3+ overdue payments, active policy
- **RENEWAL_INCENTIVE:** Medium-risk customer, no cancellation intent
- **PROACTIVE_CALLBACK:** Medium-risk customer with negative interaction, no other action
- **Edge case:** Low-risk customer should get NO recommendation
- **Edge case:** Customer with confidence < 0.60 gets NEEDS_HUMAN_REVIEW

---

## Execution Steps

1. Create `ACTION_CATALOG` reference table (6 rows)
2. Create empty `NBA_RECOMMENDATIONS` table
3. Run eligibility SQL (deterministic, no LLM) → inserts eligible rows with NULL rationale
4. Run LLM rationale generation in batches of 50 → fills RATIONALE and SUPPORTING_EVIDENCE
5. Run confidence scoring and compliance check → updates CONFIDENCE_SCORE and COMPLIANCE_STATUS
6. Run all 8 test cases and show results
7. Save complete SQL to `sql/08_nba_engine.sql`
