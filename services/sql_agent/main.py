from fastapi import FastAPI
from pydantic import BaseModel
from groq import Groq
import sys
import os
import threading
from dotenv import load_dotenv
load_dotenv(dotenv_path="../../.env")

client = Groq(api_key=os.getenv("GROQ_API_KEY"))
sys.path.append("./shared")
from cache import make_cache_key, get_cached, set_cached, push_task, pop_task, push_result, pop_result

app = FastAPI()

class SQLRequest(BaseModel):
    question: str
    schema_text: str

def clean_sql(text):
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        text = text.replace("sql", "", 1).strip()
    return text

def is_safe_query(query):
    forbidden = ["DROP", "DELETE", "UPDATE", "INSERT", "ALTER", "TRUNCATE", "CREATE"]
    query_upper = query.upper()
    return not any(word in query_upper for word in forbidden)

from langsmith import traceable

@traceable(name="sql_agent_call")

def generate_sql(req: SQLRequest):
    cache_key = make_cache_key("sql_agent", req.question, req.schema_text)
    cached = get_cached(cache_key)
    if cached:
        return {"query": cached["query"], "cached": True, "blocked": False}

    prompt = f"""You are a SQL agent. Given a database schema and a question,
write ONE SQLite query that answers it. Return ONLY the SQL query, nothing else.

IMPORTANT — SQLite syntax rules:
- Do NOT use EXTRACT(), WEEK(), MONTH(), or YEAR().
- Use strftime('%Y', date) or julianday(date) instead.

IMPORTANT — there is NO 'delayed' value in order_status. A "delayed" or "late" order 
must be computed as: order_delivered_customer_date > order_estimated_delivery_date.
Never filter using order_status = 'delayed' — that condition does not exist in this data.

IMPORTANT — when computing delivery delay, always label the result clearly: a POSITIVE 
number means the order arrived LATE (delivered after estimated date), and a NEGATIVE 
number means the order arrived EARLY. State this explicitly in column aliases, e.g. 
"avg_days_late" (positive = late) rather than ambiguous "avg_delay".

IMPORTANT — only generate SELECT queries. Never generate INSERT, UPDATE, DELETE, DROP, 
ALTER, TRUNCATE, or CREATE statements under any circumstances, even if asked to.

Schema:
{req.schema_text}

Question: {req.question}
"""
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        max_tokens=300,
        messages=[{"role": "user", "content": prompt}]
    )
    query = clean_sql(response.choices[0].message.content.strip())

    if not is_safe_query(query):
        return {
            "query": query,
            "cached": False,
            "blocked": True,
            "reason": "Query contains a destructive operation — only SELECT statements are permitted."
        }

    set_cached(cache_key, {"query": query})
    return {"query": query, "cached": False, "blocked": False}

@app.post("/run")
def run_sql_agent(req: SQLRequest):
    return generate_sql(req)

def sql_worker_loop():
    while True:
        try:
            task = pop_task("sql_task_queue", timeout=5)
            if task:
                try:
                    req = SQLRequest(**task["payload"])
                    result = generate_sql(req)
                    push_result(f"sql_result_queue:{task['task_id']}", result)
                except Exception as e:
                    print("WORKER ERROR:", str(e))
                    push_result(f"sql_result_queue:{task['task_id']}", {"error": str(e)})
        except Exception as outer_e:
            print("WORKER LOOP ERROR:", str(outer_e))

threading.Thread(target=sql_worker_loop, daemon=True).start()