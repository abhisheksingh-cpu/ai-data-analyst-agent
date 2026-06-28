from fastapi import FastAPI
from pydantic import BaseModel
from groq import Groq
from tavily import TavilyClient
import sys
import threading
import sys
sys.path.append("./shared")
from cache import make_cache_key, get_cached, set_cached, push_task, pop_task, push_result, pop_result


app = FastAPI()
import os
from dotenv import load_dotenv
load_dotenv(dotenv_path="../../.env")

client = Groq(api_key=os.getenv("GROQ_API_KEY"))
tavily_client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))

class ResearchRequest(BaseModel):
    step_text: str
    original_question: str

def search_web(query, max_results=3):
    try:
        results = tavily_client.search(query=query, max_results=max_results)
        snippets = [r["content"] for r in results.get("results", [])]
        return "\n\n".join(snippets) if snippets else "No relevant search results found."
    except Exception as e:
        return f"Search failed: {str(e)}"

from langsmith import traceable

@traceable(name="research_agent_call")
def generate_research(req: ResearchRequest):
    cache_key = make_cache_key("research_agent", req.step_text, req.original_question)
    cached = get_cached(cache_key)
    if cached:
        return {"answer": cached["answer"], "cached": True}

    search_query = f"{req.step_text} {req.original_question}"
    search_results = search_web(search_query)
   

    prompt = f"""You are a research agent. The following analytics question has a 
sub-step that cannot be answered from internal data and requires external context.

Original question: {req.original_question}
Sub-step: {req.step_text}

Here are real web search results relevant to this step:
{search_results}

Based on these search results, provide a brief, evidence-based explanation (2-4 
sentences). If the search results don't actually address the question, say so 
clearly rather than guessing.
"""
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        max_tokens=300,
        messages=[{"role": "user", "content": prompt}]
    )
    answer = response.choices[0].message.content.strip()

    set_cached(cache_key, {"answer": answer})
    return {"answer": answer, "cached": False}
@app.post("/run")
def run_research_agent(req: ResearchRequest):
    return generate_research(req)

def research_worker_loop():
    while True:
        try:
            task = pop_task("research_task_queue", timeout=5)
            if task:
                try:
                    req = ResearchRequest(**task["payload"])
                    result = generate_research(req)
                    push_result(f"research_result_queue:{task['task_id']}", result)
                except Exception as e:
                    print("WORKER ERROR:", str(e))
                    push_result(f"research_result_queue:{task['task_id']}", {"error": str(e)})
        except Exception as outer_e:
            print("WORKER LOOP ERROR:", str(outer_e))

threading.Thread(target=research_worker_loop, daemon=True).start()