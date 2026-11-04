# SentinelAI – Metric Definitions & Mathematical Formulations
## Platform Measurement Standards & Data Integrity Guide

**Version:** 1.0.0-METRICS-SPEC  
**Status:** Enforced  
**Policy Compliance:** Mandatory Data Integrity Policy  

All platform metrics reported across the API, evaluation subsystem, and administrative dashboard must strictly derive from actual persisted database records or formally executed benchmark datasets. No random, synthetic, or hardcoded values are permitted.

---

## 1. Core Execution & Operational Metrics

### 1.1 Total Requests ($N_{\text{total}}$)
- **Definition:** The absolute count of agent invocations received by SentinelAI within the queried scope.
- **Formula:** $N_{\text{total}} = \sum_{i=1}^M 1$
- **Data Source:** `execution_traces` table.
- **SQL Aggregation:**
  ```sql
  SELECT COUNT(id) FROM execution_traces WHERE tenant_id = :tenant_id;
  ```
- **Denominator:** N/A (Discrete count).
- **Sample Size:** All records within the selected filter window.
- **Time Window:** Configurable (e.g. past 1h, 24h, 7d, or all-time).
- **Limitations:** Does not distinguish between successful and aborted executions.
- **Empty-Data Behavior:** Returns `0`.

---

### 1.2 Execution Success Rate ($R_{\text{success}}$)
- **Definition:** The percentage of active execution attempts that terminated in a `SUCCESS` status, excluding blocked policy rejections.
- **Formula:**
  $$R_{\text{success}} = \frac{N_{\text{successful}}}{N_{\text{successful}} + N_{\text{failed}}} \times 100\%$$
- **Data Source:** `execution_traces.status` column.
- **SQL Aggregation:**
  ```sql
  SELECT 
    COUNT(CASE WHEN status = 'SUCCESS' THEN 1 END) * 100.0 / 
    NULLIF(COUNT(CASE WHEN status IN ('SUCCESS', 'ERROR') THEN 1 END), 0)
  FROM execution_traces;
  ```
- **Denominator:** $N_{\text{successful}} + N_{\text{failed}}$ (Active non-blocked executions).
- **Sample Size:** Active executions ($N_{\text{active}} \ge 1$).
- **Time Window:** Query-dependent.
- **Limitations:** Blocked requests are treated as intentional security interventions, not runtime failures, and are thus excluded from the failure denominator.
- **Empty-Data Behavior:** Returns `null` (displayed as `N/A`) when active executions equal zero.

---

### 1.3 Blocked Request Rate ($R_{\text{blocked}}$)
- **Definition:** The proportion of total incoming requests rejected or quarantined by security policy guardrails.
- **Formula:**
  $$R_{\text{blocked}} = \frac{N_{\text{blocked}}}{N_{\text{total}}} \times 100\%$$
- **Data Source:** `execution_traces.status = 'BLOCKED'`.
- **SQL Aggregation:**
  ```sql
  SELECT 
    COUNT(CASE WHEN status = 'BLOCKED' THEN 1 END) * 100.0 / 
    NULLIF(COUNT(id), 0)
  FROM execution_traces;
  ```
- **Denominator:** $N_{\text{total}}$.
- **Sample Size:** Total requests.
- **Time Window:** Query-dependent.
- **Limitations:** High rates may reflect either an active adversarial attack campaign or overly strict ingress policy thresholds.
- **Empty-Data Behavior:** Returns `null` (or `0.0%`) when total requests equal zero.

---

### 1.4 Latency Percentiles (p50, p95, p99)
- **Definition:** The value below which a given percentage of execution latencies fall.
- **Formula:**
  $$p_k = \inf \{ t \in \mathbb{R} : P(L \le t) \ge k/100 \}$$
- **Data Source:** `execution_traces.total_latency_ms` and `trace_spans.latency_ms`.
- **SQL Aggregation:**
  ```sql
  SELECT 
    percentile_cont(0.50) WITHIN GROUP (ORDER BY total_latency_ms) AS p50,
    percentile_cont(0.95) WITHIN GROUP (ORDER BY total_latency_ms) AS p95,
    percentile_cont(0.99) WITHIN GROUP (ORDER BY total_latency_ms) AS p99
  FROM execution_traces;
  ```
- **Denominator:** Count of measured non-null execution durations.
- **Sample Size:** $N \ge 1$.
- **Time Window:** Query-dependent.
- **Limitations:** Latency includes LLM token generation time, which varies with output length.
- **Empty-Data Behavior:** Returns `0.0 ms`.

---

### 1.5 Token Consumption & Cost
- **Definition:** Total token usage recorded from provider metadata, and estimated dollar costs based on model pricing schedules.
- **Formula:**
  $$\text{Tokens}_{\text{total}} = \sum \text{prompt\_tokens} + \sum \text{completion\_tokens}$$
  $$\text{Cost}_{\text{total}} = \sum (\text{prompt\_tokens} \times \text{Rate}_{\text{prompt}} + \text{completion\_tokens} \times \text{Rate}_{\text{completion}})$$
- **Data Source:** `execution_traces.prompt_tokens`, `execution_traces.completion_tokens`.
- **SQL Aggregation:**
  ```sql
  SELECT 
    SUM(total_tokens) AS total_tokens,
    SUM(prompt_tokens) AS prompt_tokens,
    SUM(completion_tokens) AS completion_tokens,
    SUM(estimated_cost_usd) AS total_cost_usd
  FROM execution_traces;
  ```
- **Denominator:** N/A (Additive sum).
- **Sample Size:** All recorded traces.
- **Limitations:** Only accounts for calls where the provider returns token metadata. Mock provider calculates deterministic character-derived approximations.
- **Empty-Data Behavior:** Returns `0` tokens and `$0.00` cost.

---

## 2. Security Evaluation & Adversarial Metrics

Security metrics are **strictly computed on ground-truth labeled benchmark datasets**. Unlabeled production traffic is never used to derive Precision or Recall.

```
                  Actual Malicious       Actual Benign
Detected / Blocked       TP                   FP
Allowed / Not Blocked    FN                   TN
```

### 2.1 Security Precision
- **Definition:** The ratio of correctly blocked malicious attacks to all requests blocked by the security system.
- **Formula:**
  $$\text{Precision} = \frac{\text{TP}}{\text{TP} + \text{FP}}$$
- **Denominator:** $\text{TP} + \text{FP}$ (All blocked attempts).
- **Limitations:** Undefined if the security engine blocks zero requests.
- **Empty-Data Behavior:** Returns `null` ("N/A") when $\text{TP} + \text{FP} = 0$.

### 2.2 Security Recall (Sensitivity)
- **Definition:** The proportion of malicious attacks in the dataset that were successfully detected and mitigated.
- **Formula:**
  $$\text{Recall} = \frac{\text{TP}}{\text{TP} + \text{FN}}$$
- **Denominator:** $\text{TP} + \text{FN}$ (Total malicious ground-truth cases).
- **Limitations:** Dependent on the diversity and breadth of the evaluation attack set.
- **Empty-Data Behavior:** Returns `null` ("N/A") when $\text{TP} + \text{FN} = 0$.

### 2.3 False Positive Rate (FPR)
- **Definition:** The proportion of legitimate, benign requests incorrectly blocked or flagged as threats.
- **Formula:**
  $$\text{FPR} = \frac{\text{FP}}{\text{FP} + \text{TN}}$$
- **Denominator:** $\text{FP} + \text{TN}$ (Total benign ground-truth cases).
- **Limitations:** A high FPR damages agent utility and customer user experience.
- **Empty-Data Behavior:** Returns `null` ("N/A") when $\text{FP} + \text{TN} = 0$.

### 2.4 F1-Score
- **Definition:** Harmonic mean of security precision and recall.
- **Formula:**
  $$F_1 = 2 \times \frac{\text{Precision} \times \text{Recall}}{\text{Precision} + \text{Recall}}$$
- **Empty-Data Behavior:** Returns `null` when $\text{Precision} + \text{Recall} = 0$.

---

## 3. RAGAS Retrieval & Generation Metrics

### 3.1 Faithfulness
- **Definition:** The fraction of factual claims in the generated response that can be directly inferred from the retrieved context chunks.
- **Formula:**
  $$\text{Faithfulness} = \frac{|\text{Supported Claims in Answer}|}{|\text{Total Claims in Answer}|}$$
- **Data Source:** Extracted factual statements compared against joined context.
- **Denominator:** Total extracted propositions in the answer.
- **Limitations:** Grammatical complexity may impede sentence parsing.
- **Empty-Data Behavior:** Returns `null` with explanation if answer contains zero claims or retrieved context is empty.

### 3.2 Answer Relevancy
- **Definition:** Semantic and keyword alignment between the original question and the generated answer.
- **Formula:**
  $$\text{Relevancy} = \frac{1}{2} \cos(\vec{v}_{\text{query}}, \vec{v}_{\text{answer}}) + \frac{1}{2} \left( \frac{|\text{Terms}_{\text{query}} \cap \text{Terms}_{\text{answer}}|}{|\text{Terms}_{\text{query}}|} \right)$$
- **Denominator:** Number of non-stopword query tokens.
- **Empty-Data Behavior:** Returns `null` if question or answer is blank.

### 3.3 Context Precision (Mean Average Precision @ K)
- **Definition:** Measures whether chunks containing ground-truth evidence are positioned at higher ranks in the retrieved context list.
- **Formula:**
  $$\text{Context Precision} = \frac{\sum_{k=1}^K (\text{Precision}@k \times \mathbb{I}(k \text{ is relevant}))}{|\text{Total Relevant Chunks Retrieved}|}$$
- **Denominator:** Count of relevant chunks identified.
- **Empty-Data Behavior:** Returns `null` if ground truth is unavailable or candidate list is empty.

### 3.4 Context Recall
- **Definition:** The proportion of ground-truth propositions successfully retrieved into the context window.
- **Formula:**
  $$\text{Context Recall} = \frac{|\text{Ground Truth Sentences Captured in Context}|}{|\text{Total Ground Truth Sentences}|}$$
- **Denominator:** Total propositions in ground-truth answer.
- **Empty-Data Behavior:** Returns `null` if ground truth is not provided.

---

## 4. Multi-LLM Comparative Benchmark & Cost Accounting

### 4.1 Verified Cost Calculation (PRICING_CATALOG_V1)
- **Definition:** The monetary cost in USD of an LLM invocation or benchmark run, calculated strictly from provider input/output token counts and the official versioned pricing catalog.
- **Formula:**
  $$\text{Cost}_{\text{USD}} = \left( \frac{\text{Tokens}_{\text{input}} \times \text{Price}_{\text{input\_per\_M}}}{1{,}000{,}000} \right) + \left( \frac{\text{Tokens}_{\text{output}} \times \text{Price}_{\text{output\_per\_M}}}{1{,}000{,}000} \right)$$
- **Pricing Catalog (V1.0):**
  - `gemini-2.5-flash`: \$0.075 / 1M input, \$0.30 / 1M output
  - `gemini-2.5-pro`: \$1.25 / 1M input, \$5.00 / 1M output
  - `llama-3.3-70b-versatile`: \$0.59 / 1M input, \$0.79 / 1M output
  - `gpt-4o-mini`: \$0.15 / 1M input, \$0.60 / 1M output
  - `gpt-4o`: \$2.50 / 1M input, \$10.00 / 1M output
  - `mock-sentinel-v1`: \$0.00 / 1M input, \$0.00 / 1M output
- **Data Integrity Rule:** If token counts are missing or null, cost is reported as `null` or `0.00` with pricing source metadata recorded. Zero cost fabrication is permitted.

### 4.2 Provider Success & Fallback Rates
- **Provider Success Rate:**
  $$\text{Success Rate} = \frac{\text{Successful Invocations}}{\text{Total Invocations}}$$
- **Fallback Rate:**
  $$\text{Fallback Rate} = \frac{\text{Fallback Events}}{\text{Total Attempted Requests}}$$
- **Empty-Data Behavior:** Returns `null` ("N/A") when total invocations equal zero.


