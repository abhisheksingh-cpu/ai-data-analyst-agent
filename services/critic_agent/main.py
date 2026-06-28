from fastapi import FastAPI
from pydantic import BaseModel
from groq import Groq
import os
import sys
import sys
import threading
sys.path.append("./shared")
from cache import make_cache_key, get_cached, set_cached, push_task, pop_task, push_result, pop_result

from dotenv import load_dotenv
load_dotenv(dotenv_path="../../.env")

app = FastAPI()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

class CriticRequest(BaseModel):
    question: str
    summary_text: str
    final_answer: str

from langsmith import traceable

@traceable(name="critic_agent_call")
def generate_critique(req: CriticRequest):
    cache_key = make_cache_key("critic_agent", req.question, req.summary_text, req.final_answer)
    cached = get_cached(cache_key)
    if cached:
        return {"critique": cached["critique"], "cached": True}

    prompt = f"""You are a critic agent reviewing a data analyst's final answer.

Original question: {req.question}

Evidence gathered:
{req.summary_text}

Final answer given:
{req.final_answer}

Check the final answer against the evidence. Flag:
- Any claim not supported by the evidence above
- Any number that looks implausible (e.g. absurdly large/small for the context)
- Any contradiction between the answer and the data
- Any contradiction WITHIN the answer itself (e.g. claiming delays increased while 
  also reporting that actual-vs-estimated gaps were negative)

Respond with either:
"APPROVED" if the answer is well-supported and internally consistent, or
"REVISE: <specific issue found>" if there's a problem.
"""
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        max_tokens=300,
        messages=[{"role": "user", "content": prompt}]
    )
    critique = response.choices[0].message.content.strip()

    set_cached(cache_key, {"critique": critique})
    return {"critique": critique, "cached": False}
@app.post("/run")
def run_critic_agent(req: CriticRequest):
    return generate_critique(req)

def critic_worker_loop():
    while True:
        try:
            task = pop_task("critic_task_queue", timeout=5)
            if task:
                try:
                    req = CriticRequest(**task["payload"])
                    result = generate_critique(req)
                    push_result(f"critic_result_queue:{task['task_id']}", result)
                except Exception as e:
                    print("WORKER ERROR:", str(e))
                    push_result(f"critic_result_queue:{task['task_id']}", {"error": str(e)})
        except Exception as outer_e:
            print("WORKER LOOP ERROR:", str(outer_e))

threading.Thread(target=critic_worker_loop, daemon=True).start()