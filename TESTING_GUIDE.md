# SentinelAI – Testing & Quality Assurance Guide

This guide describes the complete testing strategy, test suites, execution procedures, and data integrity verification protocols for SentinelAI.

---

## 1. Test Architecture Overview

SentinelAI employs a multi-tiered automated verification suite ensuring 100% data authenticity, robust security firewall defenses, and accurate Multi-LLM provider operations:

| Test Suite File | Subsystem Verified | Test Count | Scope |
|---|---|---|---|
| `backend/tests/test_foundations.py` | Core Configuration & Database Models | 5 | Settings, SQLite persistence, Mock provider |
| `backend/tests/test_rag_subsystem.py` | Ingestion, Hybrid Search & RAG | 10 | Loaders (PDF/MD/DOCX/TXT), BM25 + Dense RRF, Cross-encoder |
| `backend/tests/test_security_engine.py` | Security Firewall & Tool Policies | 11 | Injection, Jailbreak, PII, HITL approval, Fail-closed |
| `backend/tests/test_agent_orchestrator.py`| LangGraph StateGraph Execution | 5 | 7-phase state machine, tracing & span hierarchy |
| `backend/tests/test_evaluation_engine.py` | RAGAS & Security Evaluation Suite | 7 | Confusion matrix, FPR/F1, Latency percentiles, Regression diff |
| `backend/tests/test_e2e_integration.py` | Full Lifecycle End-to-End | 1 | 9-step complete platform integration audit |
| `backend/tests/test_multi_llm_execution.py`| Multi-LLM Gateway & Failovers | 10 | Gemini/Groq/OpenAI adapters, fallbacks, pricing, telemetry |
| `backend/tests/test_langfuse_integration.py`| Langfuse Observability & Cloud | 13 | Trace lifecycle, nested spans, OTel IDs, live cloud probe |
| **Total Test Count** | **Complete System** | **62** | **100% Passing Automated Tests** |

---

## 2. Running Automated Tests

### 2.1 Complete Test Suite Execution
Execute the entire test suite using pytest:
```bash
# In Windows PowerShell:
.\.venv\Scripts\pytest backend/tests/ -v
```

### 2.2 Target Specific Subsystems
```bash
# Multi-LLM Provider & Fallback Tests:
.\.venv\Scripts\pytest backend/tests/test_multi_llm_execution.py -v

# Agent Orchestrator LangGraph Tests:
.\.venv\Scripts\pytest backend/tests/test_agent_orchestrator.py -v

# AI Security Firewall Tests:
.\.venv\Scripts\pytest backend/tests/test_security_engine.py -v

# Agentic RAG Subsystem Tests:
.\.venv\Scripts\pytest backend/tests/test_rag_subsystem.py -v

# Evaluation & Regression Engine Tests:
.\.venv\Scripts\pytest backend/tests/test_evaluation_engine.py -v
```

---

## 3. Frontend Quality Assurance & Type Checking

To verify zero TypeScript errors and confirm production bundling:
```bash
cd frontend
npm run build
```
Expected output:
- `tsc -b`: 0 errors
- `vite build`: Successfully builds bundle in `frontend/dist/`

---

## 4. Mandatory Data Integrity Testing Principles

1. **No Mocking of Database Records in Assertions**:
   - Tests assert directly on rows queried via `db.get(ExecutionTrace, trace_id)` and `db.get(LLMInvocation, ...)`.
2. **Deterministic Fallback Verification**:
   - When external LLM provider keys (`GEMINI_API_KEY`, `GROQ_API_KEY`, `OPENAI_API_KEY`) are missing, the system gracefully falls back to deterministic mock or secondary providers.
3. **Zero Token Fabrication**:
   - `total_tokens`, `prompt_tokens`, and `completion_tokens` are populated only from real upstream metadata. If metadata is absent, tokens remain `0` and cost remains `$0.00`.
4. **Isolated Test Databases**:
   - Each test fixture uses an ephemeral SQLite database (`sqlite+aiosqlite:///test_*.db`) cleanly removed on teardown, preventing cross-test pollution.

