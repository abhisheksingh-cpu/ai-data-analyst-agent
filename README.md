# AI Data Analyst Agent

> A distributed multi-agent AI system that answers natural-language business questions over a real e-commerce dataset — by planning, querying, researching, synthesizing, and critiquing its own answers across five independent, containerized services.

## Overview

Business questions like *"why did delivery delays increase in early 2018?"* don't have a single-query answer. They require breaking the question down, pulling structured data, gathering outside context when the database doesn't have it, and reasoning over all of it — while staying honest about what the evidence actually supports.

This project automates that workflow with five specialized agents, each running as its own service, coordinating over Redis. It's built to behave less like a chatbot and more like a small team of analysts who check each other's work — including catching, in testing, cases where the system's own data contradicted the question's premise.

---

## Architecture

```
                    User Question
                          │
                          ▼
                 ┌─────────────────┐
                 │  Intent Guardrail │  (blocks destructive requests
                 └────────┬────────┘   before any agent runs)
                          ▼
                 ┌─────────────────┐
                 │  Orchestrator    │  (Python, coordinates everything)
                 └────────┬────────┘
                          │  Redis queues (+ direct HTTP per service)
        ┌─────────┬───────┴───────┬───────────┐
        ▼         ▼               ▼           ▼
   ┌────────┐ ┌────────┐    ┌──────────┐ ┌────────┐
   │Planner │ │  SQL   │    │Research  │ │ Critic │
   │ Agent  │ │ Agent  │    │ Agent    │ │ Agent  │
   └────────┘ └───┬────┘    └────┬─────┘ └────────┘
                   │              │            ▲
                   ▼              ▼            │
              SQLite DB     Tavily Search       │
                   │              │             │
                   └──────┬───────┘             │
                          ▼                     │
                 ┌─────────────────┐             │
                 │ Synthesizer Agent │───────────┘
                 └─────────────────┘
                          │
                          ▼
                   Final Answer
```

**Pipeline for a single question:**
1. **Intent guardrail** rejects destructive requests ("delete all orders") before any agent runs
2. **Planner Agent** decomposes the question into 2-4 sub-questions, grounded in the actual database schema — each sub-question must resolve to a concrete number or comparison, not a question about how to write the query
3. Each sub-question routes to:
   - **SQL Agent** — generates a SQLite query, blocks it if it contains any write/delete operation, executes it against the real database
   - **Research Agent** — for anything outside the schema, runs a real Tavily web search and reasons over the actual search results
4. **Synthesizer Agent** combines every step's results into one evidence-based answer
5. **Critic Agent** checks the answer against the evidence for unsupported claims, implausible numbers, and internal contradictions — triggers a revision if it finds a real issue
6. Failures at any step are retried with backoff; a failed Critic doesn't block the answer, a failed Planner or Synthesizer does (see [Design Decisions](#design-decisions))

Each agent is a separate FastAPI service, containerized via Docker Compose, reachable over both direct HTTP (for manual testing via each service's `/docs` page) and Redis queues (the path actually used by the orchestrator).

---

## Stack

| Layer | Tech |
|---|---|
| LLM | Groq (Llama 3.3 70B) |
| Web search | Tavily |
| Service framework | FastAPI + Uvicorn |
| Inter-service messaging | Redis (queues + caching) |
| Database | SQLite (Olist Brazilian E-Commerce dataset) |
| Containerization | Docker + Docker Compose |
| Observability | LangSmith (per-agent call tracing: inputs, outputs, latency) |
| UI | Streamlit (with auto-generated charts for multi-row results) |
| Orchestration | Custom Python orchestrator — built by hand before reaching for a framework, see [Design Decisions](#design-decisions) |

---

## Project structure

```
ai-data-analyst-agent/
├── app/
│   └── streamlit_app.py
├── eval/
│   ├── eval_questions.json
│   ├── run_eval.py
│   └── results/
├── orchestrator/
│   └── run_pipeline.py
├── services/
│   ├── planner_agent/      (main.py + Dockerfile)
│   ├── sql_agent/
│   ├── research_agent/
│   ├── synthesizer_agent/
│   └── critic_agent/
├── shared/
│   └── cache.py            (Redis cache + queue helpers, used by every service)
├── data/
│   └── raw/                (Olist CSVs — not committed, see Setup)
├── docker-compose.yml
├── requirements.txt
└── .env                     (not committed — see Setup)
```

---

## Setup

**Prerequisites:** Docker Desktop, Python 3.11+, free API keys from [Groq](https://console.groq.com), [Tavily](https://tavily.com), and optionally [LangSmith](https://smith.langchain.com) for tracing.

1. **Clone and enter the repo:**
   ```bash
   git clone https://github.com/<your-username>/ai-data-analyst-agent.git
   cd ai-data-analyst-agent
   ```

2. **Get the dataset:** download the [Olist Brazilian E-Commerce dataset](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce) from Kaggle, place the CSVs in `data/raw/`.

3. **Build the SQLite database:**
   ```python
   import pandas as pd, sqlite3, os
   conn = sqlite3.connect('data/olist.db')
   for f in os.listdir('data/raw'):
       if f.endswith('.csv'):
           pd.read_csv(f'data/raw/{f}').to_sql(f.replace('.csv', ''), conn, if_exists='replace', index=False)
   ```

4. **Create `.env` in the project root:**
   ```
   GROQ_API_KEY=
   TAVILY_API_KEY=
   LANGSMITH_API_KEY=
   LANGSMITH_PROJECT=ai-data-analyst-agent
   LANGSMITH_TRACING=true
   LANGSMITH_ENDPOINT=https://api.smith.langchain.com
   ```

5. **Start all 5 agent services + Redis:**
   ```bash
   docker-compose up --build
   ```

6. **Run the UI:**
   ```bash
   cd app
   streamlit run streamlit_app.py
   ```

7. **Or run a single question from the command line:**
   ```bash
   cd orchestrator
   python run_pipeline.py
   ```

---

## Evaluation

A 16-question eval harness (`eval/`) spans factual lookups, multi-table joins, time-series trends, deliberately false-premise questions, a known data-completeness edge case, and a safety-guardrail test. Ground truth for the answerable, factual/join questions was computed by hand directly against the database before running the system.

**Latest full run** (`eval/results/`): all 16 questions completed with zero pipeline crashes. 56% of answers were flagged by the Critic for revision — every flag corresponded to a real, specific issue (an internally contradictory claim, an unsupported caveat not backed by that run's evidence, an implausible outlier value), not reflexive skepticism. The run also hit Groq's daily rate limit partway through on a later session — the retry/fault-tolerance logic degraded gracefully rather than crashing, which is itself part of what the harness was built to verify.

Run it yourself:
```bash
cd eval
python run_eval.py
```

---

## Design decisions

**Why a custom orchestrator instead of LangChain/LangGraph?**
The orchestration logic — prompt construction, parsing, retries, queue coordination — was built by hand first, specifically to understand what a framework would actually be abstracting away before adopting one. A framework migration is a reasonable next step; doing it after building the raw version means understanding what's underneath it, not just what it returns.

**Why Redis queues *and* direct HTTP, rather than just one?**
Direct HTTP was built first and is simpler. Redis queues were added deliberately, service by service, to prove out an asynchronous, decoupled communication pattern — the kind of pattern real distributed systems need when a consumer can't be guaranteed available the instant a producer calls it. Both paths exist; the queue path is what the orchestrator actually uses.

**Why two layers of safety guardrails, not one?**
The first guardrail checked the SQL Agent's *generated query* for destructive keywords. Testing with the literal prompt "delete all orders from 2018" revealed the Planner would reframe the request into innocuous-sounding sub-questions (date filtering syntax, etc.) that passed the SQL-level check cleanly — while the Synthesizer still narrated the deletion intent in its final answer. A second guardrail was added at the orchestrator's entry point, checking the original question's intent before any agent runs, closing the gap the first guardrail couldn't see.

**Why is a Critic failure non-fatal, but a Planner or Synthesizer failure is?**
An answer that wasn't reviewed by the Critic is still useful. No answer at all is not. The system makes this tradeoff explicit in its output ("CRITIC UNAVAILABLE — answer was not reviewed due to service failure") rather than silently downgrading quality.

---

## Engineering log

Real bugs found and fixed during development — the debugging process here is as much the point of the project as the final architecture.

- **Cross-step inconsistency.** Independent SQL Agent calls within a single pipeline run sometimes used different definitions of the same term (e.g. "delayed orders") because each call had no memory of how a prior step in the same run had defined it. Fixed by hard-coding the definition into the SQL Agent's prompt rather than leaving it to per-call inference.
- **Signed-value misinterpretation.** Delivery delay was computed as `actual date − estimated date`, so early deliveries came out negative. Both the Synthesizer and Critic occasionally reasoned about the sign backwards, calling an improving trend a worsening one. Fixed by requiring explicit, unambiguous column aliases (`avg_days_late`, where positive always means late).
- **Guardrail bypass via reframing.** See Design Decisions above — caught by deliberately testing a destructive prompt, not by accident.
- **Dead worker threads, found three separate times.** Three different agent services had a background queue-worker function fully defined but never actually *started* — `threading.Thread(target=worker_loop, daemon=True).start()` was missing from the file. Tasks piled up silently in the Redis queue with nothing consuming them; no error, no crash, just a hang. Found each time by directly inspecting queue length in Redis rather than trusting application logs.
- **BRPOP socket timeout crash.** Redis's blocking pop call raised an uncaught `TimeoutError` that permanently killed the consuming worker thread after a single empty poll — a known interaction between `redis-py`'s socket timeout and `BRPOP`'s own timeout parameter. Fixed with an explicit, longer socket timeout and an outer exception boundary around the polling loop so a transient error can't take the thread down.
- **SQLite thread-safety under Streamlit.** A connection created with default settings worked fine from a plain CLI script but broke under Streamlit's execution model. Fixed with `check_same_thread=False`.
- **Planner generating implementation questions instead of analytical ones.** Early Planner output included sub-questions like "what SQL function should we use to compare these dates?" instead of questions that resolve to an actual number. Fixed with contrastive few-shot examples (explicit GOOD vs. BAD sub-question pairs) in the prompt — more effective than an abstract instruction alone.
- **LangSmith traces silently not arriving.** Traces appeared to send without error but never showed in the dashboard. Root cause, found by testing the SDK in isolation outside the app: a stale/invalid API key baked into an already-running container — editing `.env` doesn't affect a container that's already running until it's rebuilt. Confirmed and fixed by rotating the key and rebuilding.
- **Cache masking real test results, more than once.** Several "is this actually fixed?" tests quietly returned a stale, cached answer rather than exercising the new code, because the cache key is derived from the question text, not from the underlying logic version. Caught each time by noticing identical, word-for-word output across what should have been different test runs, and resolved by testing with genuinely novel questions.

---

## What's not done

In the interest of accuracy rather than overselling: long-term cross-session memory was scoped but deliberately not built — doing it well needs semantic retrieval, not just exact-match caching, and that's a meaningfully larger addition than anything else here. Three of the sixteen eval questions (trend-category) don't yet have hand-verified ground truth. The Synthesizer's tendency to occasionally insert an unsupported data-completeness caveat is improved with a conditional prompt rule, but not exhaustively re-verified across the full eval set.

## Possible next steps

Kubernetes deployment, a real CI/CD pipeline, multi-database support beyond SQLite, and a lightweight long-term memory layer (Redis-backed run history, retrieved by relevance rather than exact match) are the most natural extensions, in roughly that order of effort-to-value.
