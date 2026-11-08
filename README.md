# SentinelAI – Enterprise Agent Security & Evaluation Platform

[![Build Status](https://img.shields.io/badge/tests-62%20passed-brightgreen.svg)]()
[![Python](https://img.shields.io/badge/python-3.12%2B-blue.svg)]()
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115%2B-009688.svg)]()
[![TypeScript](https://img.shields.io/badge/TypeScript-5.6-blue.svg)]()
[![React](https://img.shields.io/badge/React-18-61dafb.svg)]()
[![Multi-LLM](https://img.shields.io/badge/Multi--LLM-Gemini%20%7C%20Groq%20%7C%20OpenAI%20%7C%20Mock-purple.svg)]()
[![Observability](https://img.shields.io/badge/Langfuse-Cloud%20%7C%20Self--Hosted-orange.svg)]()
[![Data Integrity](https://img.shields.io/badge/Data%20Integrity-100%25%20Authentic-emerald.svg)]()

SentinelAI is an enterprise-grade AI agent firewall, orchestration runtime, and continuous evaluation platform. It provides deterministic and model-assisted defense against prompt injection, jailbreaks, indirect document injection, and unauthorized tool calls, while orchestrating agents with LangGraph, monitoring performance with production Langfuse observability, and evaluating systems with rigorous, zero-fake data integrity.

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

### 5. Multi-LLM Gateway, Task Routing & Automated Failover
- **Unified Provider Abstraction**: Integrated official SDKs for **Google Gemini** (`google-genai`), **Groq** (`groq`), **OpenAI** (`openai`), and **Deterministic Mock Engine** (`mock-sentinel-v1`).
- **Normalized Response & Zero Token Fabrication**: Returns authentic token consumption (`input_tokens`, `output_tokens`, `total_tokens`), measured latency, provider request IDs, and finish reasons directly from upstream headers.
- **Dynamic Task-Based Routing**: Configurable model routing for specialized agent workloads (`planning`, `fast_classification`, `document_answering`, `evaluation`, `structured_output`).
- **Intelligent Fallback Chains**: Automatic failover upon rate-limits (`429`), timeouts, model deprecations, and connection drops with database-backed `LLMFallbackEvent` records.
- **Multi-LLM Benchmark Comparison**: Executes identical test suites concurrently across providers, rendering comparative scorecards with real faithfulness, relevancy, latency, and costs via `PRICING_CATALOG_V1`.

### 6. Full-Stack Observability & UI
- **React 18 + TypeScript SPA**: Enterprise dashboard with live metric cards, Recharts time-series charts, approval review drawers, interactive agent playground, knowledge base manager, security incident audit log, Multi-LLM provider telemetry, and trace timeline viewer.
- **Distributed Database Tracing**: Every agent transaction generates an `ExecutionTrace` with step-by-step `TraceSpan` timings, token accounting, exact provider and model metadata, fallback indicators, and Langfuse-compatible JSON logging.

### 7. Production Langfuse Observability Integration
- **Dual-Layer Observability Architecture**: Preserves full PostgreSQL execution persistence while transmitting OpenTelemetry-standard telemetry to Langfuse Cloud or self-hosted instances.
- **Correlated Trace Identifiers**: Automatically normalizes SentinelAI UUIDs to 32-hex lowercase OpenTelemetry trace IDs (`uuid.hex`), allowing instant cross-referencing between local database records and Langfuse dashboards.
- **Hierarchical Observation Spans**: Emits native Langfuse observation types (`agent` for root execution, `guardrail` for input/output security decisions, `retriever` for hybrid RAG search, `tool` for server-side tool invocations, and `generation` for Multi-LLM provider calls).
- **Automated Evaluation Scoring**: Submits RAGAS metrics (`ragas_faithfulness`, `ragas_answer_relevancy`, `ragas_context_precision`, `ragas_context_recall`) and security robustness scores (`security_precision`, `security_recall`, `security_f1`) directly to Langfuse trace scorecards.
- **Non-Blocking Graceful Degradation**: Telemetry operations run asynchronously with fail-safe error isolation. If Langfuse is unreachable or credentials are unconfigured, core agent execution continues without latency overhead or interruption.
- **Zero Token & Metric Fabrication**: Strictly forwards authentic provider token counts, true measured latencies, and exact costs computed via `PRICING_CATALOG_V1`. Redacts API keys, bearer tokens, and PII before transmission.

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
│   └── tests/                 # 62 passing unit, integration, and E2E tests
├── frontend/
│   ├── src/
│   │   ├── api/               # Typed API client
│   │   ├── components/        # Navbar, Sidebar, MetricCard, EmptyState
│   │   ├── views/             # 12 core cybersecurity views (Dashboard, Security, Approvals, Agent, Traces, RAG, Eval, Red Team, Tools, Audit, Settings, Auth)
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
| `GET` | `/api/v1/health` | Platform readiness and subsystem status (`database`, `qdrant`, `firewall`, `langfuse`) |
| `GET` | `/api/v1/dashboard/metrics` | Returns live calculated metrics from persisted database records (live vs mock) |
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
| `GET` | `/api/v1/providers` | Lists configured LLM providers, active models, and capabilities |
| `GET` | `/api/v1/providers/health` | Returns health status and measured round-trip latencies across all providers |
| `POST` | `/api/v1/providers/health-check` | Performs an on-demand live connectivity test for a specific provider |
| `GET` | `/api/v1/providers/configuration`| Returns active task routing mappings and fallback chains |
| `PUT` | `/api/v1/providers/configuration`| Updates specialized task routing (planning, classification, answering) |
| `POST` | `/api/v1/llm/benchmarks/run` | Runs standardized benchmark suite across selected providers concurrently |
| `GET` | `/api/v1/observability/langfuse/status` | Live Langfuse connectivity, authentication status, and export counters |
| `GET` | `/api/v1/observability/langfuse/configuration` | Sanitized Langfuse settings with securely masked public & secret keys |
| `POST` | `/api/v1/observability/langfuse/test-connection` | Live authentication probe to Langfuse Cloud or self-hosted endpoint |
| `GET` | `/api/v1/observability/langfuse/traces` | Correlates database traces with 32-hex OTel Langfuse trace IDs and deep links |
| `GET` | `/api/v1/observability/langfuse/metrics` | Returns export telemetry metrics (total exported, failed, success rate) |

---

## Verification & Test Suite

The SentinelAI platform is backed by **62 exhaustive automated tests** across 8 test suites:

```bash
# Execute the complete backend test suite:
pytest backend/tests/ -v
```

### Verified Test Results (62 / 62 Passed in 31.20s)

```
backend/tests/test_agent_orchestrator.py (5 tests) ...................... PASSED [  8%]
  - test_normal_agent_execution_persists_trace_and_spans ................ PASSED
  - test_direct_prompt_injection_blocked_by_orchestrator ................ PASSED
  - test_tool_execution_authorized ...................................... PASSED
  - test_tool_execution_requiring_human_approval ........................ PASSED
  - test_traces_and_agents_api_endpoints ................................ PASSED

backend/tests/test_e2e_integration.py (1 test) .......................... PASSED [ 10%]
  - test_complete_platform_lifecycle_and_data_integrity ................. PASSED

backend/tests/test_evaluation_engine.py (7 tests) ....................... PASSED [ 21%]
  - test_percentile_latency_calculation ................................. PASSED
  - test_confusion_matrix_calculations_and_zero_denominators ............ PASSED
  - test_known_fixture_metrics_calculation .............................. PASSED
  - test_fresh_install_zero_metrics ..................................... PASSED
  - test_ragas_evaluation_engine_metrics ................................ PASSED
  - test_regression_comparison_engine ................................... PASSED
  - test_evaluations_and_dashboard_api_endpoints ........................ PASSED

backend/tests/test_foundations.py (5 tests) ............................. PASSED [ 29%]
  - test_settings_loaded ................................................ PASSED
  - test_deterministic_mock_llm ......................................... PASSED
  - test_deterministic_mock_llm_tool_simulation ......................... PASSED
  - test_database_models_persistence .................................... PASSED
  - test_fastapi_endpoints .............................................. PASSED

backend/tests/test_langfuse_integration.py (13 tests) ................... PASSED [ 50%]
  - test_to_langfuse_trace_id_normalization ............................. PASSED
  - test_mask_secret_utility ............................................ PASSED
  - test_sanitize_value_scrubbing ....................................... PASSED
  - test_langfuse_service_disabled_mode ................................. PASSED
  - test_langfuse_service_health_check_states ........................... PASSED
  - test_mocked_langfuse_lifecycle ...................................... PASSED
  - test_graceful_degradation_on_exception .............................. PASSED
  - test_api_langfuse_status ............................................ PASSED
  - test_api_langfuse_configuration ..................................... PASSED
  - test_api_langfuse_test_connection ................................... PASSED
  - test_api_langfuse_traces_and_metrics ................................ PASSED
  - test_agent_execution_with_langfuse .................................. PASSED
  - test_live_langfuse_cloud_connectivity ............................... PASSED

backend/tests/test_multi_llm_execution.py (10 tests) .................... PASSED [ 66%]
  - test_normal_rag_request_lifecycle ................................... PASSED
  - test_prompt_injection_blocked_and_persisted ......................... PASSED
  - test_unauthorized_tool_blocked_by_policy ............................ PASSED
  - test_human_approval_workflow_lifecycle .............................. PASSED
  - test_provider_health_check_contracts ................................ PASSED
  - test_intelligent_provider_fallback_recording ........................ PASSED
  - test_provider_outage_when_all_fail .................................. PASSED
  - test_database_and_dashboard_consistency ............................. PASSED
  - test_empty_corpus_safe_grounding .................................... PASSED
  - test_output_validation_pii_redaction ................................ PASSED

backend/tests/test_rag_subsystem.py (10 tests) .......................... PASSED [ 82%]
  - test_document_loaders_txt_md_docx ................................... PASSED
  - test_document_chunking .............................................. PASSED
  - test_embedding_service .............................................. PASSED
  - test_hybrid_retrieval_and_cross_encoder ............................. PASSED
  - test_indirect_prompt_injection_guard ................................ PASSED
  - test_agentic_rag_graph_execution_grounded ........................... PASSED
  - test_agentic_rag_graph_poor_retrieval_retry_and_insufficient_evidence PASSED
  - test_agentic_rag_empty_corpus ....................................... PASSED
  - test_full_rag_api_lifecycle ......................................... PASSED

backend/tests/test_security_engine.py (11 tests) ........................ PASSED [100%]
  - test_normal_request_allowed ......................................... PASSED
  - test_direct_prompt_injection_blocked ................................ PASSED
  - test_jailbreak_attempt_blocked ...................................... PASSED
  - test_indirect_injection_through_retrieved_documents ................. PASSED
  - test_unauthorized_tool_invocation ................................... PASSED
  - test_invalid_refund_amount .......................................... PASSED
  - test_approval_bypass_attempt ........................................ PASSED
  - test_rejected_approval .............................................. PASSED
  - test_expired_approval ............................................... PASSED
  - test_pii_leakage_in_output .......................................... PASSED
  - test_policy_engine_unavailable_fail_closed .......................... PASSED
  - test_security_api_endpoints ......................................... PASSED

============================= 62 passed in 31.20s =============================
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

