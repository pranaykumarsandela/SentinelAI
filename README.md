# SentinelAI – Enterprise Agent Security & Evaluation Platform

[![Build Status](https://img.shields.io/badge/tests-39%20passed-brightgreen.svg)]()
[![Python](https://img.shields.io/badge/python-3.12%2B-blue.svg)]()
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115%2B-009688.svg)]()
[![TypeScript](https://img.shields.io/badge/TypeScript-5.6-blue.svg)]()
[![React](https://img.shields.io/badge/React-18-61dafb.svg)]()
[![Data Integrity](https://img.shields.io/badge/Data%20Integrity-100%25%20Authentic-emerald.svg)]()

SentinelAI is an enterprise-grade AI agent firewall, orchestration runtime, and continuous evaluation platform. It provides deterministic and model-assisted defense against prompt injection, jailbreaks, indirect document injection, and unauthorized tool calls, while orchestrating agents with LangGraph and monitoring performance with rigorous, zero-fake data integrity.

---

## Architecture Overview

```
                      +---------------------------------------+
                      | React + Vite + TypeScript Frontend   |
                      | (Tailwind CSS, Recharts, Lucide UI)   |
                      +-------------------+-------------------+
                                          | REST API
                                          v
                      +---------------------------------------+
                      |         FastAPI Gateway Router        |
                      +-------------------+-------------------+
                                          |
                      +-------------------v-------------------+
                      |      LangGraph Agent Orchestrator     |
                      |   (StateGraph 7-Phase Security Loop)  |
                      +---+-------------------------------+---+
                          |                               |
        +-----------------+-----------------+             |
        |                                   |             v
+-------v-------+                   +-------v-------+ +---+-------------------+
|  Input Guard  |                   |  Output Guard | | Tool Policy Engine    |
| - Regex/Heur. |                   | - PII Redact  | | - RBAC & Permissions  |
| - Injection   |                   | - Groundedness| | - Human-in-the-Loop   |
| - Jailbreak   |                   | - Secret Mask | | - Server-side Exec    |
+---------------+                   +---------------+ +---+-------------------+
        |                                   |             |
        +-----------------+-----------------+             |
                          |                               v
                      +---v---------------------------+ +---------------------+
                      |      Agentic RAG Subsystem    | | Evaluation Engine   |
                      | - Hybrid Search (BM25 + Dense)| | - RAGAS Faithfulness|
                      | - Cross-Encoder Reranking     | | - Security Benchmk  |
                      | - Indirect Injection Filter   | | - Regression Engine |
                      | - Qdrant & Real Citations     | | - Latency P50/95/99 |
                      +---------------+---------------+ +----------+----------+
                                      |                            |
                                      v                            v
                      +-------------------------------------------------------+
                      |          Relational Persistence & Audit Store         |
                      |      (SQLAlchemy 2 Async: SQLite / PostgreSQL)        |
                      | - execution_traces       - approval_requests          |
                      | - trace_spans            - evaluation_runs            |
                      | - security_events        - documents & chunks         |
                      +-------------------------------------------------------+
```

---

## Mandatory Data Integrity Policy

SentinelAI adheres strictly to the **Mandatory Data Integrity Policy**:
1. **Zero Synthetic / Hardcoded Metrics**: All production dashboard statistics, charts, latency percentiles, and token consumption numbers are computed directly from persisted database execution records (`execution_traces`, `trace_spans`, `security_events`, `approval_requests`).
2. **Fresh Installation Guarantee**: On a clean database, the system reports exactly 0 requests, 0 tokens, null/zero rates, and presents contextual empty states (`is_fresh_install_zero_state: true`).
3. **Strict Environment Segregation**: Live customer execution metrics and deterministic mock test runs are isolated via environment tags (`is_mock=False` vs `is_mock=True`), preventing benchmarking tests from distorting production SLA metrics.
4. **Authentic Evaluation Calculations**: Precision, Recall, F1-score, and False Positive Rates are computed strictly against labeled benchmark datasets with mathematical edge-case handling (zero denominators resolved to `None` / `N/A`).

---

## Core Capabilities

### 1. Centralized AI Security Firewall & Policy Engine
- **Input Guard**: Multi-layered deterministic pattern matching and heuristic classifiers intercepting:
  - Direct instruction overrides and prompt injection.
  - Roleplay exploits and jailbreaks (`DAN`, `developer mode`, `hypothetical bypasses`).
  - Sensitive data and PII scanning (`SSN`, `credit cards`, `API keys`, `passwords`).
  - Configurable max length thresholds.
- **Fail-Closed Policy Design**: Tool authorization engines and approval gates strictly deny execution if policies are missing or the policy engine becomes unavailable.
- **Indirect Prompt Injection Defense**: Evaluates retrieved RAG chunks before supplying context to LLM planning nodes, neutralizing hidden prompt injections embedded in uploaded PDFs or documents.
- **Output Guardrails**: Sanitizes model responses, enforces citation verification against retrieved chunks, masks accidental PII leakage, and blocks unauthorized outbound payload leaks.

### 2. Human-in-the-Loop (HITL) Tool Authorization
- **Role-Based Tool Registry**: Tools specify required roles (`user`, `support_agent`, `supervisor`, `admin`), permission levels (`READ_ONLY`, `READ_WRITE`, `ADMIN`), and explicit approval requirements.
- **Transactional State Machine**: State transitions through `PENDING -> APPROVED / REJECTED / EXPIRED -> EXECUTED`.
- **Server-Side Enforcement**: LLMs are never granted direct tool execution capabilities; tool calls require cryptographic validation and approval record verification before invocation.

### 3. Agentic RAG Subsystem
- **Multi-Format Ingestion**: Validates, extracts, and chunks PDF, Markdown, DOCX, and TXT files with page-level metadata tracking.
- **Hybrid Retrieval**: Combines BM25 sparse keyword matching and 384-dimensional dense vector embeddings with Reciprocal Rank Fusion (RRF) and Cross-Encoder neural reranking.
- **LangGraph Verification Graph**: Implements autonomous query grading, dynamic query rewriting on low similarity scores, and strict evidence groundedness validation.
- **Verifiable Citations**: Preserves true chunk identifiers, source text, document filenames, and page numbers.

### 4. Continuous Evaluation & Regression Suite
- **RAGAS Evaluator**: Evaluates Faithfulness, Answer Relevancy, Context Precision, and Context Recall against grounded ground-truth datasets.
- **Security Benchmark**: Measures True Positives, False Positives, True Negatives, False Negatives, Precision, Recall, F1, and False Positive Rate across 6 attack categories.
- **Regression Detection**: Compares baseline vs. candidate evaluation runs, tracking metric deltas, newly regressed test cases, and candidate model drift.

### 5. Full-Stack Observability & UI
- **React 18 + TypeScript SPA**: Enterprise dashboard with live metric cards, Recharts time-series charts, approval review drawers, interactive agent playground, knowledge base manager, security incident audit log, and trace timeline viewer.
- **Distributed Database Tracing**: Every agent transaction generates an `ExecutionTrace` with step-by-step `TraceSpan` timings, token accounting, and Langfuse-compatible JSON logging.

---

## Technology Stack

| Layer | Technologies |
|---|---|
| **Backend Framework** | Python 3.12+, FastAPI, Pydantic v2, Starlette |
| **Database & ORM** | SQLAlchemy 2.0 (Async), Alembic, aiosqlite / asyncpg, PostgreSQL compatible |
| **Agent Orchestration** | LangGraph, LangChain Core |
| **Vector Database & RAG** | Qdrant (in-memory & networked), Sentence Transformers, BM25, Cross-Encoder |
| **Frontend Framework** | React 18, Vite, TypeScript, Tailwind CSS, PostCSS |
| **Data Visualization & Icons**| Recharts, Lucide React |
| **Testing & Verification** | Pytest, Pytest-AsyncIO, HTTPX |
| **Packaging & Deployment**| Docker, Docker Compose, Nginx |

---

## Directory Structure

```
sentinelai/
├── backend/
│   ├── app/
│   │   ├── agent/             # LangGraph agent orchestrator & state machine
│   │   ├── api/v1/            # FastAPI REST routers (agents, security, rag, approvals, etc.)
│   │   ├── core/              # Config, settings, async database session engine
│   │   ├── evaluation/        # RAGAS, security benchmarks, metrics calculator, regression engine
│   │   ├── models/            # SQLAlchemy 2 declarative entities & enumerations
│   │   ├── observability/     # JSON logger & Langfuse trace exporter
│   │   ├── rag/               # Chunking, loaders, embeddings, Qdrant store, hybrid retriever
│   │   ├── schemas/           # Pydantic v2 validation models
│   │   ├── security/          # Input guards, tool policy engine, HITL approval, output guard
│   │   ├── services/          # LLM provider abstraction (Mock, Groq, OpenAI)
│   │   └── main.py            # FastAPI entrypoint & lifespan lifecycle
│   └── tests/                 # 39 passing unit, integration, and E2E tests
├── frontend/
│   ├── src/
│   │   ├── api/               # Typed API client
│   │   ├── components/        # Navbar, Sidebar, MetricCard, EmptyState
│   │   ├── views/             # 7 core views (Dashboard, Security, Approvals, Agent, Traces, RAG, Eval)
│   │   ├── types/             # TypeScript domain definitions
│   │   ├── App.tsx            # Main layout & router switch
│   │   └── main.tsx           # React root
│   ├── package.json
│   ├── vite.config.ts
│   └── tailwind.config.js
├── docker/
│   ├── Dockerfile.backend     # Python 3.12 production container
│   ├── Dockerfile.frontend    # Multi-stage Node.js build with Nginx runtime
│   └── nginx.conf             # Reverse proxy configuration
├── docker-compose.yml         # One-command full-stack containerization
├── ARCHITECTURE.md            # Deep-dive platform architectural blueprint
├── METRIC_DEFINITIONS.md      # Mathematical specifications for all dashboard & evaluation metrics
├── DEVELOPMENT_STATUS.md      # Comprehensive implementation & phase audit log
└── README.md                  # System overview and quickstart
```

---

## Quickstart & Installation

### Option 1: Docker Compose (Recommended)

Run the entire platform (PostgreSQL, Qdrant, FastAPI Backend, React Frontend) with a single command:

```bash
docker compose up --build -d
```

- **Frontend Application**: [http://localhost:3000](http://localhost:3000)
- **Backend Swagger Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Qdrant Vector Dashboard**: [http://localhost:6333/dashboard](http://localhost:6333/dashboard)

To stop the services:
```bash
docker compose down
```

---

### Option 2: Local Development

#### 1. Backend Setup
```bash
# 1. Create and activate virtual environment
python -m venv .venv
# Windows:
.\.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

# 2. Install dependencies
pip install -r backend/requirements.txt  # Or install pyproject dependencies

# 3. Configure environment
cp .env.example .env

# 4. Start the backend API server
uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000
```

#### 2. Frontend Setup
```bash
# In a new terminal:
cd frontend

# 1. Install dependencies
npm install

# 2. Run development server
npm run dev
```

Visit [http://localhost:5173](http://localhost:5173) in your browser.

---

## API Specifications

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/v1/dashboard/metrics` | Returns live calculated metrics from persisted database records |
| `GET` | `/api/v1/dashboard/timeseries` | Returns authentic hourly request volume, latency, and tokens |
| `POST` | `/api/v1/agents/execute` | Main agent gateway: Input Guard -> RAG -> Plan -> Tool Auth -> Output Guard |
| `POST` | `/api/v1/security/guard/input` | Standalone endpoint to inspect input against injection/jailbreak/PII rules |
| `GET` | `/api/v1/security/events` | Paginated audit log of blocked attacks and security incidents |
| `GET` | `/api/v1/approvals/pending` | Retrieves tool execution requests awaiting human supervisor review |
| `POST` | `/api/v1/approvals/{id}/review`| Authorizes or rejects a pending human-in-the-loop action |
| `POST` | `/api/v1/documents/upload` | Ingests PDF/DOCX/TXT/MD into Qdrant and relational database |
| `POST` | `/api/v1/rag/query` | Executes Agentic LangGraph retrieval with query rewriting and citations |
| `POST` | `/api/v1/evaluations/ragas/run`| Runs RAGAS evaluation against authentic ground truth dataset |
| `POST` | `/api/v1/evaluations/security/benchmark`| Executes adversarial test suite computing precision, recall, and FPR |
| `POST` | `/api/v1/evaluations/compare` | Compares two evaluation runs for performance regressions |
| `GET` | `/api/v1/traces` | Lists execution traces with token counts, latency, and status |
| `GET` | `/api/v1/traces/{id}` | Returns comprehensive trace details with nested execution spans |

---

## Verification & Test Suite

The SentinelAI platform is backed by **39 exhaustive automated tests**:

```bash
# Execute the complete backend test suite:
pytest backend/tests -v
```

### Verified Test Results (39 / 39 Passed)

```
backend/tests/test_agent_orchestrator.py::test_normal_agent_execution_persists_trace_and_spans PASSED
backend/tests/test_agent_orchestrator.py::test_direct_prompt_injection_blocked_by_orchestrator PASSED
backend/tests/test_agent_orchestrator.py::test_tool_execution_authorized PASSED
backend/tests/test_agent_orchestrator.py::test_tool_execution_requiring_human_approval PASSED
backend/tests/test_agent_orchestrator.py::test_traces_and_agents_api_endpoints PASSED
backend/tests/test_e2e_integration.py::test_complete_platform_lifecycle_and_data_integrity PASSED
backend/tests/test_evaluation_engine.py::test_percentile_latency_calculation PASSED
backend/tests/test_evaluation_engine.py::test_confusion_matrix_calculations_and_zero_denominators PASSED
backend/tests/test_evaluation_engine.py::test_known_fixture_metrics_calculation PASSED
backend/tests/test_evaluation_engine.py::test_fresh_install_zero_metrics PASSED
backend/tests/test_evaluation_engine.py::test_ragas_evaluation_engine_metrics PASSED
backend/tests/test_evaluation_engine.py::test_regression_comparison_engine PASSED
backend/tests/test_evaluation_engine.py::test_evaluations_and_dashboard_api_endpoints PASSED
backend/tests/test_foundations.py::test_settings_loaded PASSED
backend/tests/test_foundations.py::test_deterministic_mock_llm PASSED
backend/tests/test_foundations.py::test_deterministic_mock_llm_tool_simulation PASSED
backend/tests/test_foundations.py::test_database_models_persistence PASSED
backend/tests/test_foundations.py::test_fastapi_endpoints PASSED
backend/tests/test_rag_subsystem.py::test_document_loaders_txt_md_docx PASSED
backend/tests/test_rag_subsystem.py::test_document_chunking PASSED
backend/tests/test_rag_subsystem.py::test_embedding_service PASSED
backend/tests/test_rag_subsystem.py::test_hybrid_retrieval_and_cross_encoder PASSED
backend/tests/test_rag_subsystem.py::test_indirect_prompt_injection_guard PASSED
backend/tests/test_rag_subsystem.py::test_agentic_rag_graph_execution_grounded PASSED
backend/tests/test_rag_subsystem.py::test_agentic_rag_graph_poor_retrieval_retry_and_insufficient_evidence PASSED
backend/tests/test_rag_subsystem.py::test_agentic_rag_empty_corpus PASSED
backend/tests/test_rag_subsystem.py::test_full_rag_api_lifecycle PASSED
backend/tests/test_security_engine.py::test_normal_request_allowed PASSED
backend/tests/test_security_engine.py::test_direct_prompt_injection_blocked PASSED
backend/tests/test_security_engine.py::test_jailbreak_attempt_blocked PASSED
backend/tests/test_security_engine.py::test_indirect_injection_through_retrieved_documents PASSED
backend/tests/test_security_engine.py::test_unauthorized_tool_invocation PASSED
backend/tests/test_security_engine.py::test_invalid_refund_amount PASSED
backend/tests/test_security_engine.py::test_approval_bypass_attempt PASSED
backend/tests/test_security_engine.py::test_rejected_approval PASSED
backend/tests/test_security_engine.py::test_expired_approval PASSED
backend/tests/test_security_engine.py::test_pii_leakage_in_output PASSED
backend/tests/test_security_engine.py::test_policy_engine_unavailable_fail_closed PASSED
backend/tests/test_security_engine.py::test_security_api_endpoints PASSED

======================== 39 passed in 7.72s ========================
```

---

## Security Best Practices & Compliance

1. **Deterministic Input Guards**: Input evaluation is executed in deterministic C/Python regex and string parsers prior to invoking any LLM, ensuring zero token cost and zero hallucination risk during threat interception.
2. **Fail-Closed Authorization**: Every tool execution is evaluated by the server-side `ToolPolicyEngine`. If an approver or permission rule is not explicitly located, the execution fails closed with a 403 Forbidden state.
3. **Indirect Injection Isolation**: Retrieved documents from corporate knowledge bases are categorized as untrusted context. Any directive tags (`Ignore`, `SYSTEM:`, `Output secret`) are stripped and logged as an indirect injection incident.
4. **Differential Evaluation**: Regressions in accuracy or security recall are immediately flagged before candidate model deployment using `RegressionEvaluationEngine`.

---

## License

Enterprise Proprietary & Confidential. Built with Google Antigravity.
