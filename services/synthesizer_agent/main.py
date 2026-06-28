from fastapi import FastAPI
from pydantic import BaseModel
from groq import Groq
import sys

import sys
import threading
sys.path.append("./shared")
from cache import make_cache_key, get_cached, set_cached, push_task, pop_task, push_result, pop_result

app = FastAPI()
import os
from dotenv import load_dotenv
load_dotenv(dotenv_path="../../.env")

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

class SynthesizerRequest(BaseModel):
    question: str
    summary_text: str

from langsmith import traceable

@traceable(name="synthesizer_agent_call")
def generate_synthesis(req: SynthesizerRequest):
    cache_key = make_cache_key("synthesizer_agent", req.question, req.summary_text)
    cached = get_cached(cache_key)
    if cached:
        return {"answer": cached["answer"], "cached": True}

    prompt = f"""You are a data analyst synthesizing findings into a final answer.

Original question: {req.question}

Findings from each analysis step:
{req.summary_text}

IMPORTANT: Only mention data completeness limitations (e.g., incomplete data after 
August 2018) if the evidence above actually includes data from September/October 2018 
or later. If the evidence only covers earlier months, do NOT mention this limitation — 
it would be an unsupported claim.

Write a clear, evidence-based answer (4-6 sentences) to the original question. 
If the data contradicts the question's premise, say so explicitly rather than 
forcing an answer that fits the assumption.
"""
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        max_tokens=400,
        messages=[{"role": "user", "content": prompt}]
    )
    answer = response.choices[0].message.content.strip()

    set_cached(cache_key, {"answer": answer})
    return {"answer": answer, "cached": False}
@app.post("/run")
def run_synthesizer_agent(req: SynthesizerRequest):
    return generate_synthesis(req)

def synthesizer_worker_loop():
    while True:
        try:
            task = pop_task("synthesizer_task_queue", timeout=5)
            if task:
                try:
                    req = SynthesizerRequest(**task["payload"])
                    result = generate_synthesis(req)
                    push_result(f"synthesizer_result_queue:{task['task_id']}", result)
                except Exception as e:
                    print("WORKER ERROR:", str(e))
                    push_result(f"synthesizer_result_queue:{task['task_id']}", {"error": str(e)})
        except Exception as outer_e:
            print("WORKER LOOP ERROR:", str(outer_e))

threading.Thread(target=synthesizer_worker_loop, daemon=True).start()