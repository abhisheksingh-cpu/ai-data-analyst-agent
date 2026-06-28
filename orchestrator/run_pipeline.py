import requests
import re
import sqlite3
import pandas as pd
import uuid
import sys

sys.path.append("../shared")
from cache import push_task, pop_task, push_result, pop_result
PLANNER_URL = "http://127.0.0.1:8002/run"
SQL_AGENT_URL = "http://127.0.0.1:8001/run"
RESEARCH_URL = "http://127.0.0.1:8003/run"
SYNTHESIZER_URL = "http://127.0.0.1:8004/run"
CRITIC_URL = "http://127.0.0.1:8005/run"


conn = sqlite3.connect(r"C:\Users\abhis\Python Project Folder\data\olist.db", check_same_thread=False)


def parse_plan(plan_text):
    steps = re.split(r'\n?\d+\.\s+', plan_text)
    return [s.strip() for s in steps if s.strip()]

def needs_research(step_text):
    return "[REQUIRES EXTERNAL RESEARCH]" in step_text

def clean_sql(text):
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```")[1].replace("sql", "", 1).strip()
    return text

def is_safe_intent(question):
    forbidden_phrases = ["delete", "drop table", "remove all", "erase", "wipe", "truncate"]
    question_lower = question.lower()
    return not any(phrase in question_lower for phrase in forbidden_phrases)

def call_planner_via_queue(question, schema_text):
    task_id = str(uuid.uuid4())
    push_task("planner_task_queue", {
        "task_id": task_id,
        "payload": {"question": question, "schema_text": schema_text}
    })
    result = pop_result(f"planner_result_queue:{task_id}", timeout=20)
    if result is None:
        raise TimeoutError("Planner did not respond in time.")
    if "error" in result:
        raise ValueError(result["error"])
    return result["plan"]


def call_sql_agent_via_queue(question, schema_text):
    task_id = str(uuid.uuid4())
    push_task("sql_task_queue", {
        "task_id": task_id,
        "payload": {"question": question, "schema_text": schema_text}
    })
    result = pop_result(f"sql_result_queue:{task_id}", timeout=15)
    if result is None:
        raise TimeoutError("SQL Agent did not respond in time.")
    if "error" in result:
        raise ValueError(result["error"])
    if result.get("blocked"):
        raise ValueError(f"Blocked query: {result.get('reason')}")
    return result["query"]

def call_research_agent_via_queue(step_text, original_question):
    task_id = str(uuid.uuid4())
    push_task("research_task_queue", {
        "task_id": task_id,
        "payload": {"step_text": step_text, "original_question": original_question}
    })
    result = pop_result(f"research_result_queue:{task_id}", timeout=20)
    if result is None:
        raise TimeoutError("Research Agent did not respond in time.")
    if "error" in result:
        raise ValueError(result["error"])
    return result["answer"]

def call_synthesizer_via_queue(question, summary_text):
    task_id = str(uuid.uuid4())
    push_task("synthesizer_task_queue", {
        "task_id": task_id,
        "payload": {"question": question, "summary_text": summary_text}
    })
    result = pop_result(f"synthesizer_result_queue:{task_id}", timeout=20)
    if result is None:
        raise TimeoutError("Synthesizer did not respond in time.")
    if "error" in result:
        raise ValueError(result["error"])
    return result["answer"]

def call_critic_via_queue(question, summary_text, final_answer):
    task_id = str(uuid.uuid4())
    push_task("critic_task_queue", {
        "task_id": task_id,
        "payload": {"question": question, "summary_text": summary_text, "final_answer": final_answer}
    })
    result = pop_result(f"critic_result_queue:{task_id}", timeout=20)
    if result is None:
        raise TimeoutError("Critic did not respond in time.")
    if "error" in result:
        raise ValueError(result["error"])
    return result["critique"]
def summarize_df(df, max_rows=10):
    if len(df) > max_rows:
        return df.head(max_rows).to_string(index=False) + f"\n... ({len(df)} total rows)"
    return df.to_string(index=False)



import time

def with_retry(func, *args, max_retries=2, backoff_seconds=2, **kwargs):
    last_exception = None
    for attempt in range(max_retries + 1):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            last_exception = e
            print(f"[Retry] Attempt {attempt+1} failed: {str(e)}")
            if attempt < max_retries:
                time.sleep(backoff_seconds * (attempt + 1))  # increasing backoff
    raise last_exception

def run_pipeline(question, schema_text):
    if not is_safe_intent(question):
        return [], "This request appears to involve deleting or destroying data, which this system does not support. Only read-only analysis is permitted.", "BLOCKED: Unsafe intent detected in original question."

    print("[Orchestrator] Calling Planner...")
    try:
        plan = with_retry(call_planner_via_queue, question, schema_text)
    except Exception as e:
        return [], f"Pipeline failed: Planner service is unavailable after retries. ({str(e)})", "BLOCKED: Planner failure."

    steps = parse_plan(plan)
    print(f"[Orchestrator] Got {len(steps)} steps.")

    results = []
    for i, step in enumerate(steps):
        print(f"[Orchestrator] Step {i+1}/{len(steps)}: {step[:80]}")
        if needs_research(step):
            try:
                answer = with_retry(call_research_agent_via_queue, step, question)
                results.append({"step": step, "type": "research", "answer": answer})
            except Exception as e:
                results.append({"step": step, "type": "research_error", "error": str(e)})
        else:
            try:
                query = clean_sql(with_retry(call_sql_agent_via_queue, step, schema_text))
                df = pd.read_sql_query(query, conn)
                results.append({"step": step, "type": "sql", "query": query, "answer": df})
            except Exception as e:
                results.append({"step": step, "type": "sql_error", "query": "", "error": str(e)})

    summary_text = ""
    for r in results:
        summary_text += f"\nStep: {r['step']}\n"
        if r["type"] == "sql":
            summary_text += f"Data:\n{summarize_df(r['answer'])}\n"
        elif r["type"] == "research":
            summary_text += f"Hypothesis: {r['answer']}\n"
        elif r["type"] in ("sql_error", "research_error"):
            summary_text += f"(Failed: {r['error']})\n"

    print("[Orchestrator] Calling Synthesizer...")
    try:
        final_answer = with_retry(call_synthesizer_via_queue, question, summary_text)
    except Exception as e:
        return results, f"Pipeline could not generate a final answer: Synthesizer service is unavailable after retries. ({str(e)})", "BLOCKED: Synthesizer failure."

    print("[Orchestrator] Calling Critic...")
    try:
        critique = with_retry(call_critic_via_queue, question, summary_text, final_answer)
    except Exception as e:
        print(f"[Orchestrator] Critic unavailable after retries, returning unverified answer: {str(e)}")
        return results, final_answer, "CRITIC UNAVAILABLE: Answer was not reviewed due to service failure after retries."

    print("CRITIC VERDICT:", critique)

    if critique.strip().startswith("REVISE"):
        revised_summary = summary_text + f"\n\nPrevious answer was flagged: {critique}\nRevise accordingly, using only the evidence above."
        print("[Orchestrator] Revising via Synthesizer...")
        try:
            final_answer = with_retry(call_synthesizer_via_queue, question, revised_summary)
        except Exception as e:
            print(f"[Orchestrator] Revision failed, returning original answer with critique noted: {str(e)}")

    return results, final_answer, critique

if __name__ == "__main__":
    question = "What is the average review score for orders delivered late versus on time?"
    schema_text = "olist_orders_dataset: order_id, customer_id, order_status, order_purchase_timestamp, order_delivered_customer_date, order_estimated_delivery_date"

    results, final_answer, critique = run_pipeline(question, schema_text)
    print("\nFINAL ANSWER:")
    print(final_answer)