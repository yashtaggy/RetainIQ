# RetainIQ End-to-End Test Report

**Date:** 2026-09-29
**Account:** DAAALVW-IS38545
**Total Tests:** 50
**Passed:** 50
**Failed:** 0
**Pass Rate:** 100%

---

## 1. Data Integrity (18 tests)

| Test ID | Test Name | Expected | Actual | Result |
|---|---|---|---|---|
| T1.1 | No duplicate CUSTOMER_ID | 0 dupes | 0 | PASS |
| T1.1 | No duplicate POLICY_ID | 0 dupes | 0 | PASS |
| T1.1 | No duplicate CLAIM_ID | 0 dupes | 0 | PASS |
| T1.1 | No duplicate PAYMENT_ID | 0 dupes | 0 | PASS |
| T1.1 | No duplicate INTERACTION_ID | 0 dupes | 0 | PASS |
| T1.1 | No duplicate INSIGHT IDs | 0 dupes | 0 | PASS |
| T1.1 | No duplicate NBA IDs | 0 dupes | 0 | PASS |
| T1.2 | FK: Policies → Customers | 0 orphans | 0 | PASS |
| T1.2 | FK: Claims → Policies | 0 orphans | 0 | PASS |
| T1.2 | FK: Claims → Customers | 0 orphans | 0 | PASS |
| T1.2 | FK: Payments → Policies | 0 orphans | 0 | PASS |
| T1.2 | FK: Interactions → Customers | 0 orphans | 0 | PASS |
| T1.2 | FK: Insights → Customers | 0 orphans | 0 | PASS |
| T1.3 | No NULL customer names | 0 | 0 | PASS |
| T1.3 | No NULL premium amounts | 0 | 0 | PASS |
| T1.3 | No NULL/empty transcript content | 0 | 0 | PASS |
| T1.3 | No NULL sentiment scores in insights | 0 | 0 | PASS |
| T1.3 | No NULL action codes in NBA | 0 | 0 | PASS |

## 2. Risk Engine (7 tests)

| Test ID | Test Name | Expected | Actual | Result |
|---|---|---|---|---|
| T2.1 | Score bounds 0–100 | 0–100, no NULLs | 0–68, 0 NULLs | PASS |
| T2.2 | Score = sum of component points | 500/500 match | 500/500 | PASS |
| T2.3 | No duplicate customers in 360 | 0 dupes | 0 | PASS |
| T2.4 | Premium not inflated (C0003) | Rs. 26,260 | Rs. 26,260 | PASS |
| T2.5 | Premium not inflated (C0090) | Rs. 81,590 | Rs. 81,590 | PASS |
| T2.6 | All 500 customers in 360 | 500 | 500 | PASS |
| T2.7 | Customers without claims included | >0 | 297 | PASS |

## 3. AI Enrichment (8 tests)

| Test ID | Test Name | Expected | Actual | Result |
|---|---|---|---|---|
| T3.1 | Sentiment range -1 to 1 | Within bounds | -0.88 to 0.891 | PASS |
| T3.2 | Sentiment label matches score | 0 mismatches | 0 | PASS |
| T3.3 | Hand-labelled positive (INT000001) | >0.3 | 0.875 | PASS |
| T3.4 | Hand-labelled negative (INT000002) | <-0.3 | -0.865 | PASS |
| T3.5 | Cancellation transcripts → cancellation_intent | >0 signals | 78 | PASS |
| T3.6 | All intent values valid | 0 invalid | 0 | PASS |
| T3.7 | All churn signal values valid | 0 invalid | 0 | PASS |
| T3.8 | Full coverage (1500/1500 enriched) | 1500 | 1500 | PASS |

## 4. Recommendations (8 tests)

| Test ID | Test Name | Expected | Actual | Result |
|---|---|---|---|---|
| T4.1 | CLAIM_ESCALATION refs real pending claims | 44/44 valid | 44/44 | PASS |
| T4.2 | CLAIM_REVIEW refs real rejected claims + complaints | 29/29 valid | 29/29 | PASS |
| T4.3 | Discount cap enforced (≤15%, ≤Rs.10,000) | 0 violations | 0 | PASS |
| T4.4 | Low confidence → NEEDS_HUMAN_REVIEW | 0 missed | 0 | PASS |
| T4.5 | No sensitive attributes in eligibility | 0 violations | 0 | PASS |
| T4.6 | One recommendation per customer | 0 dupes | 0 | PASS |
| T4.7 | All rationales populated (no refusals) | 0 missing | 0 | PASS |
| T4.8 | No DISCOUNT + INCENTIVE for same customer | 0 violations | 0 | PASS |

## 5. Application (6 tests)

| Test ID | Test Name | Expected | Actual | Result |
|---|---|---|---|---|
| T5.1 | Customer lookup (valid ID: C0003) | 1 row | 1 | PASS |
| T5.2 | Customer lookup (invalid ID: C9999) | 0 rows | 0 | PASS |
| T5.3 | Portfolio filter by segment | Only Individual | 355 Individual | PASS |
| T5.4 | Portfolio filter by risk level | Only Critical+High | 79 | PASS |
| T5.5 | ACTION_LOG table accessible | Accessible | Accessible | PASS |
| T5.6 | Streamlit app deployed | Exists | Exists | PASS |

### Action Log Write Tests (3 tests)

| Test ID | Test Name | Expected | Actual | Result |
|---|---|---|---|---|
| T5.7 | Approve writes correctly | DECISION=APPROVE | APPROVE | PASS |
| T5.8 | Edit preserves modified text | FINAL_ACTION=edited text | Edited action text | PASS |
| T5.9 | Reject writes with notes | DECISION=REJECT | Not appropriate | PASS |

## 6. Agent (3 tests)

| Test ID | Test Name | Expected | Actual | Result |
|---|---|---|---|---|
| T6.1 | Numerical answer (total customers) | Contains "500" | "500" | PASS |
| T6.2 | Grounded transcript evidence (Bajaj Allianz) | Mentions Bajaj + IDs | Bajaj Allianz + customer IDs | PASS |
| T6.3 | Unknown customer fallback (C9999) | Says not found | "No customer with ID C9999 exists" | PASS |

---

## Summary

```
Area                    Tests   Passed  Failed
─────────────────────────────────────────────
1. Data Integrity         18      18       0
2. Risk Engine             7       7       0
3. AI Enrichment           8       8       0
4. Recommendations         8       8       0
5. Application             9       9       0
6. Agent                   3       3       0
─────────────────────────────────────────────
TOTAL                     53      53       0
```

**No failures. No fixes required.**

### Notes

- Test data cleaned up after execution (3 test ACTION_LOG entries removed)
- Agent tests use live Cortex Agent calls (non-deterministic but structurally validated)
- Hand-labelled sentiment tests use synthetic data with known sentiment (INT000001 = positive feedback, INT000002 = cancellation complaint)
