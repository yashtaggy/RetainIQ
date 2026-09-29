"""
RetainIQ — Customer Retention Copilot
Streamlit-in-Snowflake Application
"""
import streamlit as st
import pandas as pd
from snowflake.snowpark.context import get_active_session
from datetime import datetime
import json
import uuid

session = get_active_session()

st.set_page_config(page_title="RetainIQ", page_icon="🛡️", layout="wide")

st.markdown("""
<style>
    .block-container { padding-top: 1.5rem; }
    .metric-card { background: #f8f9fa; border-radius: 10px; padding: 1rem; text-align: center; border-left: 4px solid #29B5E8; }
    .risk-critical { color: #e74c3c; font-weight: bold; }
    .risk-high { color: #e67e22; font-weight: bold; }
    .risk-medium { color: #f39c12; }
    .risk-low { color: #27ae60; }
</style>
""", unsafe_allow_html=True)

# ─── Helpers ───────────────────────────────────────────────
def run_query(sql, params=None):
    try:
        if params:
            return session.sql(sql, params=params).to_pandas()
        return session.sql(sql).to_pandas()
    except Exception as e:
        st.error(f"Query error: {e}")
        return pd.DataFrame()

def risk_color(level):
    return {"Critical": "🔴", "High": "🟠", "Medium": "🟡", "Low": "🟢"}.get(level, "⚪")

# ─── Sidebar Navigation ───────────────────────────────────
st.sidebar.title("🛡️ RetainIQ")
st.sidebar.caption("Customer Retention Copilot")
page = st.sidebar.radio("Navigate", ["📊 Portfolio Dashboard", "👤 Customer Workspace"])

# ═══════════════════════════════════════════════════════════
# PAGE 1: PORTFOLIO DASHBOARD
# ═══════════════════════════════════════════════════════════
if page == "📊 Portfolio Dashboard":
    st.title("Portfolio Dashboard")

    # Filters
    col_f1, col_f2 = st.columns(2)
    with col_f1:
        seg_filter = st.multiselect("Customer Segment", ["Individual", "Family", "Corporate"], default=["Individual", "Family", "Corporate"])
    with col_f2:
        risk_filter = st.multiselect("Risk Level", ["Critical", "High", "Medium", "Low"], default=["Critical", "High", "Medium", "Low"])

    seg_list = ",".join([f"'{s}'" for s in seg_filter]) if seg_filter else "'Individual','Family','Corporate'"
    risk_list = ",".join([f"'{r}'" for r in risk_filter]) if risk_filter else "'Critical','High','Medium','Low'"

    # KPI Cards
    kpi = run_query(f"""
        SELECT
            COUNT(*) AS TOTAL_CUSTOMERS,
            COUNT(CASE WHEN RISK_LEVEL IN ('Critical','High') THEN 1 END) AS AT_RISK,
            SUM(REVENUE_AT_RISK) AS TOTAL_REVENUE,
            ROUND(AVG(CHURN_RISK_SCORE), 1) AS AVG_RISK
        FROM RETAINIQ_DB.CURATED.CUSTOMER_360
        WHERE SEGMENT IN ({seg_list}) AND RISK_LEVEL IN ({risk_list})
    """)

    if not kpi.empty:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total Customers", f"{kpi['TOTAL_CUSTOMERS'].iloc[0]:,}")
        c2.metric("At-Risk (High+Critical)", f"{kpi['AT_RISK'].iloc[0]:,}")
        c3.metric("Revenue at Risk", f"₹{kpi['TOTAL_REVENUE'].iloc[0]:,.0f}")
        c4.metric("Avg Risk Score", f"{kpi['AVG_RISK'].iloc[0]}/100")

    st.markdown("---")

    # Risk distribution
    col_chart, col_table = st.columns([1, 2])

    with col_chart:
        st.subheader("Risk Distribution")
        risk_dist = run_query(f"""
            SELECT RISK_LEVEL, COUNT(*) AS CUSTOMERS, SUM(REVENUE_AT_RISK) AS PREMIUM
            FROM RETAINIQ_DB.CURATED.CUSTOMER_360
            WHERE SEGMENT IN ({seg_list}) AND RISK_LEVEL IN ({risk_list})
            GROUP BY RISK_LEVEL
            ORDER BY CASE RISK_LEVEL WHEN 'Critical' THEN 1 WHEN 'High' THEN 2 WHEN 'Medium' THEN 3 ELSE 4 END
        """)
        if not risk_dist.empty:
            st.bar_chart(risk_dist.set_index("RISK_LEVEL")["CUSTOMERS"])

    with col_table:
        st.subheader("Customers by Risk Score")
        customers = run_query(f"""
            SELECT
                CUSTOMER_ID,
                FIRST_NAME || ' ' || LAST_NAME AS NAME,
                CITY, SEGMENT, RISK_LEVEL,
                CHURN_RISK_SCORE AS SCORE,
                TOTAL_ACTIVE_PREMIUM AS PREMIUM,
                LATE_PAYMENT_COUNT AS LATE_PAY,
                REJECTED_CLAIMS AS REJ_CLAIMS,
                COMPETITOR_MENTION_COUNT AS COMP_MENTIONS
            FROM RETAINIQ_DB.CURATED.CUSTOMER_360
            WHERE SEGMENT IN ({seg_list}) AND RISK_LEVEL IN ({risk_list})
            ORDER BY CHURN_RISK_SCORE DESC
            LIMIT 50
        """)
        if not customers.empty:
            st.dataframe(customers, use_container_width=True)

    # NBA summary
    st.markdown("---")
    st.subheader("Pending Recommendations")
    nba_summary = run_query("""
        SELECT ACTION_CODE, COUNT(*) AS COUNT,
            SUM(PREMIUM_AT_RISK) AS PREMIUM_AT_RISK,
            ROUND(AVG(CONFIDENCE_SCORE), 2) AS AVG_CONFIDENCE
        FROM RETAINIQ_DB.CURATED.NBA_RECOMMENDATIONS
        WHERE RECOMMENDATION_ID NOT IN (SELECT RECOMMENDATION_ID FROM RETAINIQ_DB.APP.ACTION_LOG)
        GROUP BY ACTION_CODE
        ORDER BY COUNT DESC
    """)
    if not nba_summary.empty:
        st.dataframe(nba_summary, use_container_width=True)
    else:
        st.info("All recommendations have been reviewed.")

# ═══════════════════════════════════════════════════════════
# PAGE 2: CUSTOMER WORKSPACE
# ═══════════════════════════════════════════════════════════
elif page == "👤 Customer Workspace":
    st.title("Customer Workspace")

    # ─── Copilot Question Box ──────────────────────────────
    with st.expander("💬 Ask RetainIQ Copilot", expanded=True):
        question = st.text_input("Ask a question about any customer or the portfolio",
            placeholder="e.g., Why is customer C0003 at risk? Which customers mentioned Bajaj Allianz?")
        if question:
            with st.spinner("Thinking..."):
                try:
                    agent_sql = f"""
                        SELECT SNOWFLAKE.CORTEX.DATA_AGENT_RUN(
                            'RETAINIQ_DB.APP.RETAINIQ_COPILOT',
                            '{{"messages":[{{"role":"user","content":[{{"type":"text","text":"{question.replace(chr(34), '').replace(chr(39), '')}"}}]}}]}}',
                            TRUE
                        ) AS RESPONSE
                    """
                    result = run_query(agent_sql)
                    if not result.empty:
                        resp = json.loads(result["RESPONSE"].iloc[0])
                        for item in resp.get("content", []):
                            if item.get("type") == "text" and item.get("text"):
                                st.markdown(item["text"])
                except Exception as e:
                    st.error(f"Copilot error: {e}")

    st.markdown("---")

    # ─── Customer Selector ─────────────────────────────────
    col_search, col_info = st.columns([1, 3])
    with col_search:
        cust_id = st.text_input("Customer ID", value="C0003", placeholder="e.g., C0003")

    if cust_id:
        cust = run_query("""
            SELECT * FROM RETAINIQ_DB.CURATED.CUSTOMER_360
            WHERE CUSTOMER_ID = ?
        """, params=[cust_id.upper()])

        if cust.empty:
            st.warning(f"Customer {cust_id} not found.")
        else:
            row = cust.iloc[0]

            # ─── Header ───────────────────────────────────
            with col_info:
                st.subheader(f"{row['FIRST_NAME']} {row['LAST_NAME']}  {risk_color(row['RISK_LEVEL'])}")
                st.caption(f"{row['CITY']}, {row['STATE']} · {row['SEGMENT']} · {row['PREFERRED_LANGUAGE']}")

            # ─── Risk Score + KPIs ─────────────────────────
            st.markdown("---")
            m1, m2, m3, m4, m5 = st.columns(5)
            m1.metric("Churn Risk", f"{int(row['CHURN_RISK_SCORE'])}/100", delta=f"{row['RISK_LEVEL']}", delta_color="inverse" if row['RISK_LEVEL'] in ('Critical','High') else "off")
            m2.metric("Active Premium", f"₹{row['TOTAL_ACTIVE_PREMIUM']:,.0f}")
            m3.metric("Active Policies", int(row['ACTIVE_POLICIES']))
            m4.metric("Late Payments", int(row['LATE_PAYMENT_COUNT']))
            m5.metric("Avg Sentiment", f"{row['AVG_SENTIMENT']:.2f}")

            # ─── Risk Factors ──────────────────────────────
            if row['RISK_FACTORS']:
                st.subheader("Risk Drivers")
                factors = str(row['RISK_FACTORS']).split(' | ')
                for f in factors:
                    if f.strip():
                        st.markdown(f"- {f.strip()}")

            # ─── Tabs: Policies, Claims, Payments, Interactions ─
            tab_pol, tab_clm, tab_pay, tab_ix = st.tabs(["📋 Policies", "📄 Claims", "💰 Payments", "💬 Interactions"])

            with tab_pol:
                policies = run_query("""
                    SELECT POLICY_ID, PRODUCT_TYPE, VEHICLE_MAKE || ' ' || VEHICLE_MODEL AS VEHICLE,
                        PREMIUM_AMOUNT, STATUS, START_DATE, END_DATE
                    FROM RETAINIQ_DB.RAW.POLICIES WHERE CUSTOMER_ID = ?
                    ORDER BY START_DATE DESC
                """, params=[cust_id.upper()])
                if not policies.empty:
                    st.dataframe(policies, use_container_width=True)
                else:
                    st.info("No policies found.")

            with tab_clm:
                claims = run_query("""
                    SELECT CLAIM_ID, CATEGORY, CLAIM_AMOUNT, STATUS, CLAIM_DATE,
                        RESOLUTION_DATE, REJECTION_REASON
                    FROM RETAINIQ_DB.RAW.CLAIMS WHERE CUSTOMER_ID = ?
                    ORDER BY CLAIM_DATE DESC
                """, params=[cust_id.upper()])
                if not claims.empty:
                    st.dataframe(claims, use_container_width=True)
                else:
                    st.info("No claims filed.")

            with tab_pay:
                payments = run_query("""
                    SELECT PAYMENT_ID, POLICY_ID, AMOUNT, STATUS, DUE_DATE, PAID_DATE,
                        PAYMENT_METHOD, LATE_FEE
                    FROM RETAINIQ_DB.RAW.PAYMENTS WHERE CUSTOMER_ID = ?
                    ORDER BY DUE_DATE DESC LIMIT 20
                """, params=[cust_id.upper()])
                if not payments.empty:
                    st.dataframe(payments, use_container_width=True)
                else:
                    st.info("No payment records.")

            with tab_ix:
                interactions = run_query("""
                    SELECT INTERACTION_ID, CHANNEL, SENTIMENT_LABEL, PRIMARY_INTENT,
                        CHURN_SIGNAL, COMPETITOR,
                        LEFT(SUMMARY, 200) AS SUMMARY, LEFT(KEY_QUOTE, 200) AS KEY_QUOTE
                    FROM RETAINIQ_DB.CURATED.INTERACTION_INSIGHTS WHERE CUSTOMER_ID = ?
                    ORDER BY INTERACTION_TS DESC LIMIT 10
                """, params=[cust_id.upper()])
                if not interactions.empty:
                    st.dataframe(interactions, use_container_width=True)
                else:
                    st.info("No interaction records.")

            # ─── NBA Recommendation ────────────────────────
            st.markdown("---")
            st.subheader("Recommended Action")
            nba = run_query("""
                SELECT n.RECOMMENDATION_ID, n.ACTION_CODE, n.RECOMMENDED_ACTION,
                    n.RATIONALE, n.SUPPORTING_EVIDENCE, n.CONFIDENCE_SCORE,
                    n.COMPLIANCE_STATUS, n.DISCOUNT_AMOUNT,
                    a.ACTION_NAME
                FROM RETAINIQ_DB.CURATED.NBA_RECOMMENDATIONS n
                JOIN RETAINIQ_DB.CURATED.ACTION_CATALOG a ON n.ACTION_CODE = a.ACTION_CODE
                WHERE n.CUSTOMER_ID = ?
                  AND n.RECOMMENDATION_ID NOT IN (SELECT RECOMMENDATION_ID FROM RETAINIQ_DB.APP.ACTION_LOG)
            """, params=[cust_id.upper()])

            if nba.empty:
                already_acted = run_query("""
                    SELECT l.DECISION, l.FINAL_ACTION, l.DECIDED_AT, l.DECIDED_BY
                    FROM RETAINIQ_DB.APP.ACTION_LOG l
                    JOIN RETAINIQ_DB.CURATED.NBA_RECOMMENDATIONS n ON l.RECOMMENDATION_ID = n.RECOMMENDATION_ID
                    WHERE n.CUSTOMER_ID = ? ORDER BY l.DECIDED_AT DESC LIMIT 1
                """, params=[cust_id.upper()])
                if not already_acted.empty:
                    act = already_acted.iloc[0]
                    st.success(f"Action already taken: **{act['DECISION']}** — {act['FINAL_ACTION']} (by {act['DECIDED_BY']} at {act['DECIDED_AT']})")
                else:
                    st.info("No recommendation for this customer.")
            else:
                rec = nba.iloc[0]
                col_a, col_b = st.columns([2, 1])
                with col_a:
                    st.markdown(f"**{rec['ACTION_NAME']}** (`{rec['ACTION_CODE']}`)")
                    st.markdown(f"📌 {rec['RECOMMENDED_ACTION']}")
                    if rec['DISCOUNT_AMOUNT'] and rec['DISCOUNT_AMOUNT'] > 0:
                        st.markdown(f"💰 Discount: **₹{rec['DISCOUNT_AMOUNT']:,.0f}**")
                with col_b:
                    st.metric("Confidence", f"{rec['CONFIDENCE_SCORE']:.0%}")
                    if rec['COMPLIANCE_STATUS'] == 'COMPLIANT':
                        st.success("✅ Compliant")
                    elif rec['COMPLIANCE_STATUS'] == 'NEEDS_HUMAN_REVIEW':
                        st.warning("⚠️ Needs Human Review")
                    else:
                        st.error("🚫 Flagged")

                with st.expander("📝 Rationale & Evidence"):
                    st.markdown("**Rationale:**")
                    st.markdown(rec['RATIONALE'] if rec['RATIONALE'] else "No rationale available.")
                    st.markdown("**Supporting Evidence:**")
                    st.markdown(rec['SUPPORTING_EVIDENCE'] if rec['SUPPORTING_EVIDENCE'] else "No evidence available.")

                # ─── Approve / Edit / Reject ───────────────
                st.markdown("---")
                st.markdown("**Manager Decision**")
                decision = st.radio("Action", ["Approve", "Edit", "Reject"], horizontal=True, key="decision_radio")
                notes = st.text_area("Manager Notes", placeholder="Optional: add context for the audit trail", key="mgr_notes")

                final_action = rec['RECOMMENDED_ACTION']
                if decision == "Edit":
                    final_action = st.text_area("Edit the action", value=rec['RECOMMENDED_ACTION'], key="edit_action")

                if st.button("Submit Decision"):
                    log_id = f"LOG{uuid.uuid4().hex[:12].upper()}"
                    try:
                        session.sql("""
                            INSERT INTO RETAINIQ_DB.APP.ACTION_LOG
                            (LOG_ID, RECOMMENDATION_ID, CUSTOMER_ID, ACTION_CODE,
                             DECISION, ORIGINAL_ACTION, FINAL_ACTION, MANAGER_NOTES)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """, params=[
                            log_id,
                            rec['RECOMMENDATION_ID'],
                            cust_id.upper(),
                            rec['ACTION_CODE'],
                            decision.upper(),
                            rec['RECOMMENDED_ACTION'],
                            final_action if decision == "Edit" else rec['RECOMMENDED_ACTION'],
                            notes if notes else None
                        ]).collect()
                        st.success(f"✅ Decision recorded: **{decision}** (Log: {log_id})")
                        try:
                            st.rerun()
                        except AttributeError:
                            st.experimental_rerun()
                    except Exception as e:
                        st.error(f"Failed to log decision: {e}")

    # ─── Recent Action Log ─────────────────────────────────
    st.markdown("---")
    st.subheader("Recent Action Log")
    log = run_query("""
        SELECT LOG_ID, CUSTOMER_ID, ACTION_CODE, DECISION,
            LEFT(FINAL_ACTION, 100) AS ACTION, DECIDED_BY, DECIDED_AT
        FROM RETAINIQ_DB.APP.ACTION_LOG
        ORDER BY DECIDED_AT DESC LIMIT 20
    """)
    if not log.empty:
        st.dataframe(log, use_container_width=True)
    else:
        st.info("No decisions recorded yet.")
