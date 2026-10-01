# RetainIQ

**An AI-powered customer retention copilot for Indian motor insurance, built entirely on Snowflake.**

RetainIQ unifies customer, policy, claim, payment, and interaction data into a single view, applies Cortex AI to extract sentiment and churn signals from call transcripts, computes an explainable risk score, and generates compliance-aware retention recommendations — all accessible through a natural-language copilot and a Streamlit dashboard.

> Built for a hackathon. Uses synthetic data. Not production-validated.

---

## Problem Statement

Indian motor insurance companies face 15-25% annual policy lapse rates. Retention managers struggle because:

- Customer data is fragmented across policy, claims, payments, and call center systems
- Call transcripts contain rich churn signals (competitor mentions, cancellation threats) that are never analysed at scale
- Risk scoring is manual and inconsistent
- Recommended actions lack evidence and compliance guardrails
- There is no unified workspace to triage, investigate, and act on at-risk customers

RetainIQ addresses these gaps with a single Snowflake-native platform.

---

## Solution Overview

RetainIQ is a **read-and-recommend** system. It analyses data to surface risks and suggest actions, but a human retention manager always makes the final decision. The system:

1. **Unifies** customer, policy, claim, payment, and interaction data into a Customer 360 view
2. **Analyses** 1,500 call/email/WhatsApp transcripts using Cortex AI (sentiment, intent, churn signals, competitor extraction)
3. **Scores** each customer with a transparent 0-100 churn risk score decomposed into 8 weighted factors
4. **Recommends** next-best actions from a fixed 6-action catalogue, with deterministic eligibility rules and LLM-generated rationale
5. **Enables** natural-language investigation via a Cortex Agent with structured data + transcript search
6. **Records** every manager decision (approve/edit/reject) in an immutable audit log

---

## Architecture

```
                        +---------------------------+
                        |    Streamlit App (SiS)    |
                        | Dashboard | Workspace     |
                        +------+----------+---------+
                               |          |
                    SQL/Snowpark    Cortex Agent
                               |          |
                  +------------+----------+----------+
                  |         Snowflake Platform        |
                  |                                   |
                  |  +---------+   +---------------+  |
                  |  |   RAW   |   |   CURATED     |  |
                  |  | Tables  |-->| Views/Tables   |  |
                  |  | 5 base  |   | Customer 360   |  |
                  |  +---------+   | Interaction    |  |
                  |                | Insights       |  |
                  |                | NBA Recs       |  |
                  |                | Search Index   |  |
                  |                +---------------+  |
                  |                                   |
                  |  +----------+  +---------------+  |
                  |  | Cortex   |  | APP Schema    |  |
                  |  | AI       |  | Agent         |  |
                  |  | SENTIMENT|  | Action Log    |  |
                  |  | SUMMARIZE|  | Task Pipeline |  |
                  |  | COMPLETE |  | Streamlit     |  |
                  |  +----------+  +---------------+  |
                  +-----------------------------------+
```

**Data flow:** RAW tables --> Cortex AI enrichment --> CURATED views/tables --> Agent + Streamlit app --> ACTION_LOG

---

## Technology Stack

| Component | Technology | Purpose |
|---|---|---|
| Database | Snowflake (RETAINIQ_DB) | All storage and compute |
| Warehouse | RETAINIQ_WH (X-Small) | Query execution |
| AI: Sentiment | `CORTEX.SENTIMENT` | Interaction sentiment scoring |
| AI: Summarization | `CORTEX.SUMMARIZE` | Transcript summarization |
| AI: Extraction | `CORTEX.COMPLETE` (llama3.1-8b/70b) | Intent, churn signal, competitor extraction |
| AI: Search | Cortex Search Service | Semantic transcript retrieval |
| AI: Copilot | Cortex Agent | Natural-language question answering |
| AI: Analytics | Semantic Model (YAML) | Text-to-SQL for business questions |
| Risk Scoring | SQL View | Deterministic, explainable 0-100 score |
| NBA Engine | SQL + LLM | Rule-based eligibility + LLM rationale |
| Frontend | Streamlit-in-Snowflake | Dashboard and workspace UI |
| Pipeline | Snowflake Task + Stored Procedure | Daily automated enrichment |
| Data Generation | Python (seed=42) | Reproducible synthetic data |

---

## Key Features

### Fully Implemented

- **Customer 360 View** — Unified view joining 5 data sources with no duplicate customers (validated)
- **AI Transcript Analysis** — All 1,500 interactions enriched with sentiment, summary, intent, churn signals, competitor names, and key quotes
- **Explainable Churn Risk Score** — 0-100 score decomposed into 8 factors with point-level transparency
- **Next Best Action Engine** — 6-action catalogue with deterministic SQL eligibility, LLM-generated rationale, confidence scoring (0-1.0), and compliance flags. 164 recommendations generated.
- **Cortex Agent Copilot** — Natural-language interface using both structured data (Cortex Analyst) and transcript evidence (Cortex Search). Tested with 10 question types.
- **Cortex Search Service** — Semantic search over 1,500 transcripts with metadata filtering
- **Streamlit Dashboard** — Portfolio overview with KPIs, risk distribution, filterable customer table
- **Customer Workspace** — Copilot chat, 360 summary, risk drivers, tabbed history, NBA display with approve/edit/reject
- **Audit Trail** — Every manager decision logged to APP.ACTION_LOG
- **Daily Pipeline Task** — Automated enrichment + NBA generation (tested, deployed suspended)
- **Test Suite** — 53 automated tests across 6 areas, all passing

### Simulated / Synthetic

- **Customer Data** — 500 fictional Indian motor insurance customers (Python, seed=42)
- **Call Transcripts** — 1,500 interactions from ~20 template patterns with customer-specific data
- **Claim Processing** — Static synthetic statuses. No actual claims workflow.
- **Payment Gateway** — Pre-generated payment statuses. No real payment processing.

### Not Implemented (Future Work)

- Real-time interaction ingestion (call center API)
- Manager role-based access control (currently ACCOUNTADMIN)
- Email/SMS notification of approved actions
- A/B testing of retention offers
- IRDAI compliance API integration
- Multi-language transcript support

---

## Installation and Deployment

### Prerequisites

- Snowflake account with Cortex AI functions enabled
- ACCOUNTADMIN role (or equivalent CREATE privileges)
- Python 3.11+ (for data generation only)

### Setup

```bash
# 1. Clone the repository
git clone <repository-url>
cd retainiq

# 2. Generate synthetic data
python scripts/generate_data.py
```

Execute SQL files sequentially in Snowflake:

| Order | File | What it does |
|---|---|---|
| 1 | `sql/00_foundation.sql` | Creates database, schemas, warehouse |
| 2 | `sql/01_tables.sql` | Creates 5 base tables with FKs |
| 3 | `sql/02_load_data.sql` | Stages and loads CSV data |
| 4 | `sql/03_ai_enrichment.sql` | Runs Cortex AI on all interactions |
| 5 | `sql/04_customer_360.sql` | Creates the Customer 360 view with risk score |
| 6 | `sql/05_cortex_search.sql` | Creates the transcript search service |
| 7 | `sql/06_semantic_model.sql` | Deploys the semantic model |
| 8 | `sql/07_cortex_agent.sql` | Creates the Cortex Agent copilot |
| 9 | `sql/08_nba_engine.sql` | Generates NBA recommendations |
| 10 | `sql/09_daily_task.sql` | Creates the automated pipeline (suspended) |

**Estimated setup:** 20-30 minutes, ~3-5 credits

---

## Synthetic Data Description

All data is fictional. Generated with `random.seed(42)` for reproducibility.

| Table | Records | Details |
|---|---|---|
| CUSTOMERS | 500 | Indian names, 20 cities, 3 segments, ~2% missing age |
| POLICIES | 800 | Car/Two Wheeler/Commercial, Rs. 482-131,490 premium |
| CLAIMS | 300 | 7 categories, 4 statuses, realistic INR amounts |
| PAYMENTS | 2,363 | 6 payment methods, on-time and overdue patterns |
| INTERACTIONS | 1,500 | Call/Email/WhatsApp with customer-specific data |

20% of customers are designed as "at-risk" with higher rates of overdue payments, rejected claims, and negative transcripts.

---

## AI and Risk Scoring Methodology

### Transcript Enrichment

Each interaction processed by 3 Cortex functions:
1. **SENTIMENT** — Score -1.0 to +1.0
2. **SUMMARIZE** — 1-2 sentence summary
3. **COMPLETE** (llama3.1-8b) — JSON extraction: intent, churn signal, competitor, key quote

### Risk Score (0-100)

Weighted sum of 8 factors. Fully deterministic, no ML:

| Factor | Max Pts | Calculation |
|---|---|---|
| Late payments | 20 | 5 per overdue/failed, cap 20 |
| Rejected claims | 15 | 7.5 per rejection, cap 15 |
| Outstanding claims >30d | 10 | 5 per delayed claim, cap 10 |
| Negative sentiment | 15 | abs(recent_avg) * 20, cap 15 |
| Competitor mentions | 10 | 5 per mention, cap 10 |
| Cancellation intent | 15 | 15 if any cancellation interaction |
| Renewal risk | 10 | 10 if renewal <=30 days + other risks |
| Lapsed policies | 5 | 5 if any lapsed/cancelled |

**Levels:** Critical (>=60), High (>=30), Medium (>=10), Low (<10)

### NBA Engine (3 Layers)

1. **SQL Rules** — Deterministic eligibility (who gets what action)
2. **LLM Rationale** — Cortex COMPLETE generates evidence-based explanation
3. **SQL Scoring** — Confidence score + compliance flags

---

## Guardrails and Limitations

### Guardrails

- Read-only copilot (cannot modify data)
- No sensitive attributes (age/gender/language) in eligibility rules
- Discount caps: 15% or Rs. 10,000 max
- Claim references validated against real data
- Confidence < 0.60 triggers mandatory human review
- Full audit trail for all decisions
- No cross-selling for at-risk customers

### Limitations

- Synthetic data only — results reflect generated patterns
- English transcripts only
- Rule-based scoring (not ML-trained)
- No measured retention outcomes
- Single-user (no RBAC)
- LLM outputs are non-deterministic

---

## Testing Results

**53 tests, 100% pass rate.**

| Area | Tests | Passed |
|---|---|---|
| Data Integrity | 18 | 18 |
| Risk Engine | 7 | 7 |
| AI Enrichment | 8 | 8 |
| Recommendations | 8 | 8 |
| Application | 9 | 9 |
| Agent | 3 | 3 |

Full report: [`docs/TEST_REPORT.md`](docs/TEST_REPORT.md)

---

## Business Impact Assumptions

> These are hypothetical projections, not measured outcomes.

| Metric | Value | Basis |
|---|---|---|
| At-risk customers identified | 79 (High + Critical) | Scoring rules on synthetic data |
| Revenue at risk | Rs. 13.5 lakh | Sum of active premiums |
| Potential save rate | 10-15% | Industry benchmark |
| Investigation time reduction | ~30 min to ~5 min | Estimate: unified view + copilot vs manual |

**Not validated with real data or controlled experiments.**

---

## Demo Script (3 minutes)

1. **Dashboard** (30s) — Show KPIs: 500 customers, 79 at-risk, Rs. 13.5L at risk
2. **Customer Workspace** (60s) — Look up C0003 (Anjali Pandey, score 68/100). Show risk factors, rejected claim, overdue payments, interaction sentiment.
3. **Copilot** (60s) — Ask "Why is C0003 at risk?" Then "Which customers mentioned Bajaj Allianz?"
4. **Action** (30s) — Show the NBA recommendation, approve it, verify it appears in the Action Log.

---

## Project Structure

```
retainiq/
├── sql/                          # SQL scripts (run in order 00-09)
├── streamlit/                    # Streamlit app + deployment manifest
├── semantic/                     # Semantic model YAML
├── agent/                        # Agent specification JSON
├── scripts/                      # Python data generator
├── data/                         # Generated CSV and SQL files
├── docs/                         # Plan and test report
└── README.md
```

---

## Snowflake Objects (15 total)

| Object | Type | Records |
|---|---|---|
| RAW.CUSTOMERS | Table | 500 |
| RAW.POLICIES | Table | 800 |
| RAW.CLAIMS | Table | 300 |
| RAW.PAYMENTS | Table | 2,363 |
| RAW.INTERACTIONS | Table | 1,500 |
| CURATED.INTERACTION_INSIGHTS | Table | 1,500 |
| CURATED.CUSTOMER_360 | View | 500 |
| CURATED.INTERACTION_SEARCH | Cortex Search | 1,500 docs |
| CURATED.ACTION_CATALOG | Table | 6 actions |
| CURATED.NBA_RECOMMENDATIONS | Table | 164 |
| APP.RETAINIQ_COPILOT | Cortex Agent | 2 tools |
| APP.RETAINIQ_APP | Streamlit | Deployed |
| APP.ACTION_LOG | Table | Audit trail |
| APP.TASK_RUN_LOG | Table | Pipeline log |
| APP.RETAINIQ_DAILY_PIPELINE | Task | Daily 2AM IST |

---

*Built with Snowflake Cortex Code (CoCo). Estimated total setup cost: ~3.5 credits.*
