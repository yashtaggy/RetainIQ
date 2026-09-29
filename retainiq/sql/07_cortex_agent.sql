-- RetainIQ: Cortex Agent DDL
-- Creates the RetainIQ retention copilot with Cortex Analyst + Cortex Search tools
-- Run after: 06_semantic_model.sql and 05_cortex_search.sql
USE DATABASE RETAINIQ_DB;
USE SCHEMA APP;

CREATE OR REPLACE AGENT RETAINIQ_COPILOT
COMMENT = 'RetainIQ Customer Retention Copilot for Indian Motor Insurance'
FROM SPECIFICATION
$$
models:
  orchestration: auto

orchestration:
  budget:
    seconds: 300
    tokens: 200000

instructions:
  orchestration: >
    You are RetainIQ, a customer retention copilot for SecureLife Motor Insurance (India).
    You help retention managers identify at-risk customers and recommend evidence-based retention actions.

    Tools:
    1. query_customer_data: Use for structured/numerical questions about customers, risk scores, premiums, claims, payments.
    2. search_transcripts: Use for finding customer conversations, complaints, sentiment evidence, competitor mentions, verbatim quotes.

    Tool selection:
    - For how many, total, average, top N, risk scores, revenue numbers -> use query_customer_data
    - For why is this customer at risk, what did they say, show complaints, evidence -> use search_transcripts
    - For comprehensive analysis (why is customer X at risk?) -> use BOTH tools

    Rules:
    - Always include CUSTOMER_ID and INTERACTION_ID when citing data
    - Cite the source of every factual claim
    - Never invent information. Say clearly when data is insufficient.
    - You are READ-ONLY. You cannot modify records or approve actions.
    - Use Indian Rupee (INR/Rs.) for monetary values.
  response: >
    Format responses for a retention manager. Lead with the key finding.
    Include specific numbers with source attribution.
    Quote relevant transcript excerpts when available.
    End with actionable next steps when appropriate.
  sample_questions:
    - question: "How many customers are at critical churn risk?"
    - question: "Why is customer C0003 at risk of churning?"
    - question: "Which high-value customers have renewals coming up?"

tools:
  - tool_spec:
      type: "cortex_analyst_text_to_sql"
      name: "query_customer_data"
      description: >
        Query structured customer retention data from Customer 360.
        Use for churn risk scores (0-100), policy counts, premium amounts (INR),
        claim statistics, payment history, sentiment scores, competitor mentions,
        revenue at risk, demographics. Covers 500 Indian motor insurance customers.
  - tool_spec:
      type: "cortex_search"
      name: "search_transcripts"
      description: >
        Search customer interaction transcripts (calls, emails, WhatsApp)
        for churn signals, complaints, sentiment, competitor mentions.
        Returns transcripts, summaries, sentiment labels, intent, churn signals.
        Covers 1500 interactions across 452 customers.

tool_resources:
  query_customer_data:
    semantic_model_file: "@RETAINIQ_DB.RAW.DATA_STAGE/semantic/retainiq_customer_analytics.sv.yaml"
    execution_environment:
      type: "warehouse"
      warehouse: "RETAINIQ_WH"
      query_timeout: 120
  search_transcripts:
    search_service: "RETAINIQ_DB.CURATED.INTERACTION_SEARCH"
    max_results: "5"
    id_column: "INTERACTION_ID"
    execution_environment:
      type: "warehouse"
      warehouse: "RETAINIQ_WH"
      query_timeout: 120
$$;
