import streamlit as st
import sys
import os
import pandas as pd

sys.path.append("../orchestrator")
from run_pipeline import run_pipeline

st.set_page_config(page_title="AI Data Analyst Agent", layout="wide")

st.title("AI Data Analyst Agent")
st.caption("Ask a question about the Olist e-commerce dataset — a multi-agent pipeline will plan, research, and analyze it.")

schema_text = "olist_orders_dataset: order_id, customer_id, order_status, order_purchase_timestamp, order_delivered_customer_date, order_estimated_delivery_date"

question = st.text_input("Ask a question:", placeholder="e.g. What percentage of orders were delivered late in 2018?")

if st.button("Run Analysis") and question:
    with st.spinner("Running multi-agent pipeline..."):
        try:
            results, final_answer, critique = run_pipeline(question, schema_text)

            st.subheader("Final Answer")
            st.write(final_answer)

            st.subheader("Critic Verdict")
            if critique.strip().startswith("REVISE"):
                st.warning(critique)
            else:
                st.success(critique)

            st.subheader("Step-by-Step Evidence")
            for r in results:
                with st.expander(f"{r['type'].upper()}: {r['step'][:80]}"):
                    if r["type"] == "sql":
                        st.code(r["query"], language="sql")
                        st.dataframe(r["answer"])

                        df = r["answer"]
                        st.write("DEBUG dtypes:", df.dtypes.to_dict())
                        st.write("DEBUG numeric_cols:", df.select_dtypes(include="number").columns.tolist())
                        numeric_cols = df.select_dtypes(include="number").columns.tolist()
                        non_numeric_cols = df.select_dtypes(exclude="number").columns.tolist()

                        if len(df) >= 2 and len(numeric_cols) >= 1:
                            if non_numeric_cols:
                                chart_df = df.set_index(non_numeric_cols[0])[numeric_cols]
                                label = non_numeric_cols[0].lower()
                                if any(k in label for k in ["month", "date", "year", "quarter"]):
                                    st.line_chart(chart_df)
                                else:
                                    st.bar_chart(chart_df)
                            else:
                                st.bar_chart(df[numeric_cols])

                    elif r["type"] == "research":
                        st.write(r["answer"])
                    elif r["type"] in ("sql_error", "research_error"):
                        st.error(r.get("error", "Unknown error"))

        except Exception as e:
            st.error(f"Pipeline failed: {str(e)}")