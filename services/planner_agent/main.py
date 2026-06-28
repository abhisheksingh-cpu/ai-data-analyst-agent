from fastapi import FastAPI
from pydantic import BaseModel
from groq import Groq
import os
import sys
import threading
sys.path.append("./shared")
import threading
from cache import make_cache_key, get_cached, set_cached, push_task, pop_task, push_result, pop_result

from dotenv import load_dotenv
load_dotenv(dotenv_path="../../.env")

app = FastAPI()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

class PlannerRequest(BaseModel):
    question: str
    schema_text: str

from langsmith import traceable

@traceable(name="planner_agent_call")
def generate_plan(req: PlannerRequest):
    cache_key = make_cache_key("planner_agent", req.question, req.schema_text)
    cached = get_cached(cache_key)
    if cached:
        return {"plan": cached["plan"], "cached": True}

    prompt = f"""You are a planning agent for a data analytics system using SQLite.
You only have access to the following schema. Do NOT propose steps requiring data 
outside this schema.

SQLite syntax only — no EXTRACT(), WEEK(), MONTH(), YEAR(). Use strftime() and julianday().

Schema:
{req.schema_text}

Question: {req.question}

Each sub-question you write will be sent directly to a SQL agent that writes and runs 
a query against the database. Each sub-question MUST be a question that resolves to a 
concrete number, count, average, or comparison from the data — NOT a question about 
HOW to write SQL, what functions to use, or how to define a term.

GOOD examples (produce a number/fact):
- "How many orders were delivered late in 2018?"
- "What is the average delivery delay in March 2018?"
- "How does order volume in January 2018 compare to January 2017?"

BAD examples (do NOT generate these — these are implementation questions, not analytical questions):
- "How can we compare order_delivered_customer_date and order_estimated_delivery_date?"
- "Can we use julianday() to calculate the difference?"
- "What is the definition of 'delayed' in this context?"
- "Do we need to filter by order_status?"

Return ONLY a numbered list of 2-4 short sub-questions (one line each, no SQL code, 
no explanations). Each one must be answerable with a single aggregate SQL query that 
returns a specific number or comparison. If a step needs external data not in the 
schema, end that line with "[REQUIRES EXTERNAL RESEARCH]".

IMPORTANT — for trend or "how did X change over time" questions, you MUST generate 
ONE sub-question asking for a full grouped breakdown, NOT separate questions per 
month/period and NOT a question comparing two specific months.

GOOD example for a trend question:
- "What is the order count for each month in 2018?" (this lets the SQL agent write 
  one GROUP BY query returning all months at once)

BAD examples (do NOT generate these for trend questions):
- "How many orders were placed in January 2018?" (only one month, not a trend)
- "How many more orders were placed in February than January?" (just a difference 
  between two points, not the full trend)
"""
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        max_tokens=300,
        messages=[{"role": "user", "content": prompt}]
    )
    plan = response.choices[0].message.content.strip()

    set_cached(cache_key, {"plan": plan})
    return {"plan": plan, "cached": False}

@app.post("/run")
def run_planner_agent(req: PlannerRequest):
    return generate_plan(req)

def planner_worker_loop():
    while True:
        try:
            task = pop_task("planner_task_queue", timeout=5)
            if task:
                try:
                    req = PlannerRequest(**task["payload"])
                    result = generate_plan(req)
                    push_result(f"planner_result_queue:{task['task_id']}", result)
                except Exception as e:
                    print("WORKER ERROR:", str(e))
                    push_result(f"planner_result_queue:{task['task_id']}", {"error": str(e)})
        except Exception as outer_e:
            print("WORKER LOOP ERROR:", str(outer_e))

threading.Thread(target=planner_worker_loop, daemon=True).start()