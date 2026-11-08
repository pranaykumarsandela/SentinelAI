# SentinelAI – AI Security Engine & Threat Mitigation Architecture

This document specifies the technical design, threat models, detection strategies, and enforcement policies implemented by SentinelAI.

---

## 1. Threat Model & Scope

Autonomous agent systems face novel attack vectors that standard network firewalls cannot mitigate. SentinelAI provides defense-in-depth against:

1. **Direct Prompt Injection (DPI)**: User instructions attempting to override system prompts, roleplay boundaries, or security constraints.
2. **Jailbreak Exploits**: Adversarial framing (e.g., "DAN", hypothetical scenarios, persona subversion) designed to bypass LLM safety guardrails.
3. **Indirect Prompt Injection (IPI)**: Hostile instructions embedded within retrieved external content (untrusted PDF, DOCX, or web documents) intended to hijack agent execution during RAG context synthesis.
4. **Unauthorized Tool Execution**: Attempts by unauthorized users or compromised LLM planners to execute high-impact actions (e.g. issuing refunds, creating tickets, modifying orders).
5. **PII and Data Leakage**: Inadvertent exposure of sensitive data (SSNs, credit card numbers, secret keys, passwords) in agent inputs or synthesized outputs.
6. **Denial of Service / Token Bombing**: Unbounded input payloads designed to trigger resource exhaustion or astronomical inference bills.

---

## 2. Multi-Tier Security Engine Architecture

```
User Request
    |
    v
+-------------------------------------------------------------+
| STAGE 1: INGRESS FIREWALL (input_guard.py)                  |
| - Character length & token bounds check                     |
| - Deterministic prompt injection pattern heuristics         |
| - Jailbreak & persona subversion signatures                 |
| - Inbound PII scanning & entity extraction                  |
+-------------------------------------------------------------+
    | Verdict: ALLOW (or BLOCK/FLAG)
    v
+-------------------------------------------------------------+
| STAGE 2: RAG INGESTION & CONTEXT GUARD (prompt_injection_guard.py)
| - Scans all retrieved document chunks before prompt assembly|
| - Flags hostile instructions embedded in third-party text   |
| - Sanitizes retrieved chunks prior to model synthesis       |
+-------------------------------------------------------------+
    |
    v
+-------------------------------------------------------------+
| STAGE 3: TOOL POLICY & PERMISSION ENGINE (tool_policy_engine.py)
| - RBAC verification against user role & tool permissions   |
| - Validates argument schemas and bounds                     |
| - Intercepts sensitive tools for Human Approval (HITL)      |
+-------------------------------------------------------------+
    |
    v
+-------------------------------------------------------------+
| STAGE 4: HUMAN-IN-THE-LOOP APPROVAL (approval_engine.py)    |
| - State Machine: PENDING -> APPROVED / REJECTED / EXPIRED   |
| - Cryptographic validation of approval records              |
| - Server-side enforcement: Rejected actions never execute  |
+-------------------------------------------------------------+
    |
    v
+-------------------------------------------------------------+
| STAGE 5: EGRESS GUARDRAILS (output_guard.py)                |
| - Outbound PII masking ([REDACTED_SSN], [REDACTED_CARD])   |
| - Groundedness claim verification                           |
| - Secret token leakage blocking                             |
+-------------------------------------------------------------+
    |
    v
Final Sanitized Agent Response
```

---

## 3. Defense Implementation Principles

### 3.1 Deterministic Over Stochastic Enforcement
Where possible, security policies rely on deterministic regular expressions, AST analyzers, and cryptographically verified approval tokens rather than asking an LLM "Is this input safe?". Models may be jailbroken; deterministic code cannot be subverted by language tricks.

### 3.2 Fail-Closed Principle
If any security component fails (e.g., policy database unreachable, validator timeout, unparseable response), the system fails closed by rejecting the request (`status: BLOCKED`).

### 3.3 Server-Side Enforcement (Never Trust the Client or Model)
LLMs generate tool calling proposals; they never execute tools directly. The SentinelAI backend validates:
- Does the caller have the required role?
- Has human supervisor approval been granted and not yet expired?
- Do tool argument numbers fall within validated boundaries?

### 3.4 Multi-LLM Provider Isolation
External LLM provider API keys are strictly loaded from server-side environment variables and never surfaced to the frontend or included in serialized client responses.

### 3.5 Observability Privacy & Credential Scrubbing
When telemetry is forwarded to external observability systems (such as Langfuse Cloud or OpenTelemetry collectors):
- Ingress and egress payloads pass through recursive sanitization scrubbers.
- Bearer tokens, OpenAI/Groq API keys, passwords, SSNs, and credit cards are scrubbed prior to export.
- Upstream credentials (`LANGFUSE_SECRET_KEY`) are masked in logs and configuration API endpoints.
- Raw retrieved RAG chunks are truncated to previews with verified chunk identifiers.
- Internal chain-of-thought is protected from client or external trace disclosure.

