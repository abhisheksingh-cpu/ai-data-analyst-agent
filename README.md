# AI Data Analyst Agent

> A distributed multi-agent AI system that autonomously analyzes business data, executes SQL queries, performs statistical analysis, gathers external context, and generates evidence-backed insights.

## Overview

Modern businesses ask questions like:

* *Why did delivery delays increase in March 2018?*
* *Which product categories have the lowest customer satisfaction?*
* *How did order volume affect shipping performance?*

Answering these questions typically requires analysts to write SQL queries, perform data analysis, search for external events, and combine multiple sources of information.

This project automates that workflow using a **distributed multi-agent architecture** where specialized AI agents collaborate to solve complex analytical problems.

Instead of acting as a chatbot, the system behaves like a team of analysts, with each agent responsible for a single task.

---

# Architecture

```
                   User Question
                         │
                         ▼
                  Gateway Service
                         │
                         ▼
                 Planner Agent
                         │
          ┌──────────────┴──────────────┐
          ▼                             ▼
      SQL Agent                  Research Agent
          │                             │
          ▼                             ▼
   SQLite Database              External Knowledge
          │                             │
          └──────────────┬──────────────┘
                         ▼
                 Analysis Agent
                         │
                         ▼
                  Critic Agent
                         │
                         ▼
                  Final Response
```

---

# Agent Responsibilities

### Planner Agent

* Understands the user's intent
* Breaks vague questions into executable tasks
* Decides which agents should execute each task
* Routes tasks through the pipeline

---

### SQL Agent

* Converts natural language into SQLite queries
* Uses schema-aware prompting
* Executes SQL safely
* Returns structured datasets

---

### Research Agent

* Handles questions that require external knowledge
* Identifies information unavailable in the internal database
* Provides contextual evidence while clearly distinguishing facts from hypotheses

---

### Analysis Agent

* Performs statistical analysis using Pandas
* Detects trends, anomalies, correlations, and comparisons
* Converts raw query results into business insights

---

### Critic Agent

* Validates every generated response
* Detects unsupported claims
* Checks logical consistency
* Requests revisions when evidence is insufficient

---

# Distributed System Design

Unlike traditional AI projects where every component runs inside one Python script, this system is designed as independent services.

Each agent can run separately and communicate through a message broker.

Features include:

* Independent microservices
* Asynchronous communication
* Message queues
* Fault isolation
* Retry mechanisms
* Structured logging
* Horizontal scalability

---

# Technology Stack

## AI

* Python
* Groq API
* Prompt Engineering

## Backend

* FastAPI
* Uvicorn
* Pydantic

## Distributed Systems

* Redis
* Redis Streams
* Docker
* Docker Compose

## Data Processing

* SQLite
* Pandas
* NumPy

## Evaluation

* PyTest
* Custom Evaluation Harness
* LangSmith

## Observability

* Structured Logging
* Latency Metrics
* Failure Tracking

## Frontend

* Streamlit

---

## Project Structure

```text
ai-data-analyst-agent/
│
├── app/
│   └── streamlit_app.py          # Streamlit frontend for interacting with the system
│
├── eval/
│   ├── eval_questions.json       # Benchmark questions used for evaluation
│   ├── run_eval.py               # Evaluation pipeline
│   └── results/                  # Saved evaluation outputs
│
├── orchestrator/
│   ├── run_pipeline.py           # Coordinates communication between agents
│   └── __pycache__/
│
├── services/
│   │
│   ├── planner_agent/
│   │   ├── main.py               # Breaks user queries into executable tasks
│   │   └── Dockerfile
│   │
│   ├── sql_agent/
│   │   ├── main.py               # Generates and executes SQL queries
│   │   └── Dockerfile
│   │
│   ├── research_agent/
│   │   ├── main.py               # Retrieves external context when internal data is insufficient
│   │   └── Dockerfile
│   │
│   ├── synthesizer_agent/
│   │   ├── main.py               # Merges outputs from all agents into a unified response
│   │   └── Dockerfile
│   │
│   └── critic_agent/
│       ├── main.py               # Validates evidence and checks response quality
│       └── Dockerfile
│
├── shared/
│   ├── cache.py                  # Redis cache interface
│   ├── config.py                 # Shared configuration
│   ├── logger.py                 # Structured logging utilities
│   ├── models.py                 # Shared Pydantic request/response models
│   ├── prompts.py                # Centralized prompt templates
│   ├── database.py               # SQLite connection management
│   ├── constants.py              # Global constants
│   └── utils.py                  # Shared helper functions
│
├── data/
│   ├── raw/                      # Original Olist CSV dataset
│   ├── processed/                # Cleaned datasets
│   └── olist.db                  # SQLite database
│
├── logs/
│   ├── gateway/
│   ├── planner/
│   ├── sql/
│   ├── research/
│   ├── synthesizer/
│   └── critic/
│
├── tests/
│   ├── test_planner.py
│   ├── test_sql_agent.py
│   ├── test_research_agent.py
│   ├── test_pipeline.py
│   └── test_gateway.py
│
├── .env                          # Environment variables
├── .gitignore
├── docker-compose.yml            # Multi-container orchestration
├── requirements.txt
├── README.md
└── test_langsmith.py             # LangSmith tracing experiments
```

---

# Workflow

1. User submits a business question.
2. Planner Agent decomposes the task.
3. SQL Agent retrieves structured data.
4. Research Agent gathers external context if required.
5. Analysis Agent performs statistical reasoning.
6. Critic Agent validates the answer.
7. Final response is returned with supporting evidence.

---

# Example

### Input

```
Why did delivery delays increase in early 2018?
```

### Planner

* Calculate monthly delivery delays
* Analyze delayed order volume
* Examine customer distribution
* Request external context if necessary

### SQL

Generates SQLite queries automatically.

### Analysis

Finds:

* March 2018 had the highest delivery delay
* Delayed orders increased significantly
* Certain regions experienced higher delays

### Critic

Checks:

* Is every claim supported?
* Was every planner task completed?
* Are assumptions clearly labeled?

### Final Output

A validated, evidence-backed explanation instead of a simple SQL result.

---

# Current Features

* Schema-aware SQL generation
* Automatic query execution
* Multi-agent orchestration
* Planner-based task decomposition
* SQLite dialect validation
* Research routing
* Evidence validation
* Structured logging

---

## Future Improvements

* Apache Kafka for high-throughput distributed messaging
* Kubernetes deployment with horizontal pod autoscaling
* PostgreSQL support alongside SQLite
* Multi-database connectors (MySQL, PostgreSQL, Snowflake)
* OAuth2/JWT authentication for the Gateway API
* CI/CD pipeline using GitHub Actions
* Cloud deployment on AWS/GCP with container orchestration
* Query optimization and execution cost estimation
* Historical analytics dashboard with interactive visualizations
* Support for multiple LLM providers (Groq, Gemini, OpenAI, Anthropic)


---

# Engineering Challenges Solved

## 1. Grounding the Planner in Available Data

### Problem

The initial Planner Agent generated investigation steps that required data the system did not possess, such as:

* Weather conditions
* Traffic reports
* Carrier logistics
* Competitor events

Although these were reasonable business hypotheses, they were impossible to execute because the underlying dataset contained none of this information.

### Solution

The planner was redesigned to become **schema-aware**.

Instead of planning from the user query alone, the agent now receives the complete database schema as part of its prompt.

If the requested information cannot be answered using the available tables, the planner explicitly labels the step as:

```text
[REQUIRES EXTERNAL RESEARCH]
```

This allows the orchestration layer to automatically route those tasks to the Research Agent instead of attempting invalid SQL generation.

**Result**

* Eliminated impossible execution plans
* Reduced planner hallucinations
* Enabled intelligent routing between internal and external knowledge sources

---

## 2. SQL Dialect Incompatibility

### Problem

Despite generating syntactically correct SQL, the LLM consistently defaulted to PostgreSQL/MySQL syntax.

Common failures included:

```sql
EXTRACT(YEAR FROM ...)
```

```sql
WEEK(order_date)
```

```sql
MONTH(order_date)
```

These functions are unsupported in SQLite, causing runtime failures even though the generated queries appeared correct.

### Solution

The SQL Agent was redesigned with explicit SQLite constraints.

The prompt now enforces:

* `strftime()` for date extraction
* `julianday()` for date arithmetic
* SQLite-specific syntax only
* No PostgreSQL/MySQL functions

The agent also receives schema information so it can generate dialect-aware joins and aggregations.

**Result**

* Significantly reduced SQL execution failures
* Improved first-pass query correctness
* Eliminated manual query rewriting

---

## 3. Cleaning LLM Output Before Execution

### Problem

LLM responses frequently contained Markdown formatting:

````text
```sql
SELECT ...
```
````

Passing these responses directly to SQLite caused parser errors.

### Solution

A lightweight preprocessing layer (`clean_sql()`) was introduced to normalize model outputs before execution by removing Markdown fences and preserving only executable SQL.

**Result**

* Reliable query execution
* Reduced runtime parsing errors
* Simplified downstream orchestration

---

## 4. Separating Planning from Execution

### Problem

The initial architecture blurred the responsibilities of planning and execution.

The Planner Agent often attempted to solve the problem directly instead of producing actionable sub-tasks, making the pipeline difficult to orchestrate and extend.

### Solution

Agent responsibilities were redefined using the Single Responsibility Principle.

* **Planner Agent** → Generates execution plans only
* **SQL Agent** → Retrieves structured data
* **Research Agent** → Handles external context
* **Analysis Agent** → Performs statistical reasoning
* **Critic Agent** → Validates evidence and final responses

Each component now performs one well-defined task, enabling independent development, testing, and scaling.

**Result**

* Cleaner orchestration pipeline
* Better modularity
* Easier fault isolation
* Simpler future migration to distributed microservices

---

## 5. Making Natural Language Queries Executable

### Problem

Business questions are inherently ambiguous:

> "Why did delivery delays increase in early 2018?"

This question cannot be answered with a single SQL statement because it combines multiple analytical tasks and may require information outside the database.

### Solution

The Planner Agent decomposes complex questions into smaller executable units.

For example:

1. Calculate monthly delivery delays.
2. Count delayed orders by month.
3. Analyze regional customer distribution.
4. Flag external factors for the Research Agent.

Each task is independently processed and later combined into a single evidence-backed response.

**Result**

* Improved reasoning transparency
* More reliable SQL generation
* Extensible multi-agent workflow
* Easier debugging and evaluation

---

## Key Engineering Takeaways

This project evolved beyond a simple LLM wrapper through iterative engineering improvements:

* Grounded planning using database schema
* SQLite-aware SQL generation
* Automatic output sanitization
* Clear separation of agent responsibilities
* Intelligent routing between internal analytics and external research

Each improvement was driven by failures observed during development, resulting in a more reliable and production-oriented multi-agent system.

# Why This Project?

This project goes beyond a traditional chatbot or RAG application by combining:

* Multi-Agent AI
* Distributed Systems
* Microservices
* Tool Calling
* SQL Generation
* Automated Evaluation
* Fault-Tolerant Architecture
* Production-Oriented Design

It demonstrates practical software engineering principles alongside modern LLM application development.

---

## Getting Started

### Prerequisites

Make sure the following software is installed:

* Python 3.11+
* Docker Desktop
* Docker Compose
* Git

You'll also need:

* A Groq API Key (or another supported LLM provider)
* The Olist Brazilian E-Commerce Dataset

---

## Clone the Repository

```bash
git clone https://github.com/<your-username>/ai-data-analyst-agent.git
cd ai-data-analyst-agent
```

---

## Create a Virtual Environment

### Windows

```bash
python -m venv venv
venv\Scripts\activate
```

### macOS / Linux

```bash
python3 -m venv venv
source venv/bin/activate
```

---

## Install Dependencies

```bash
pip install -r requirements.txt
```

---

## Configure Environment Variables

Create a `.env` file in the project root.

```env
GROQ_API_KEY=your_api_key_here

REDIS_HOST=localhost
REDIS_PORT=6379

SQLITE_DB=data/olist.db
```

---

## Download the Dataset

Download the **Olist Brazilian E-Commerce Dataset** from Kaggle.

Place the extracted files inside:

```text
data/raw/
```

Your folder should look like:

```text
data/
├── raw/
│   ├── olist_customers_dataset.csv
│   ├── olist_orders_dataset.csv
│   ├── olist_order_items_dataset.csv
│   ├── ...
│
└── processed/
```

Run the database setup script to create the SQLite database.

---

## Start Redis

Using Docker:

```bash
docker run -d --name redis -p 6379:6379 redis
```

Verify Redis is running:

```bash
docker ps
```

---

## Launch the Agent Services

From the project root:

```bash
docker-compose up --build
```

This starts:

* Planner Agent
* SQL Agent
* Research Agent
* Synthesizer Agent
* Critic Agent
* Redis
* Gateway Service

---

## Launch the Streamlit UI

Open a new terminal:

```bash
streamlit run app/streamlit_app.py
```

The application will be available at:

```text
http://localhost:8501
```

---

## Running Evaluations

Execute the evaluation suite:

```bash
python eval/run_eval.py
```

Evaluation outputs will be stored in:

```text
eval/results/
```

---

## Running Tests

Run all unit and integration tests:

```bash
pytest
```

---

## Stopping the Services

```bash
docker-compose down
```

To also remove containers and networks:

```bash
docker-compose down --volumes
```
