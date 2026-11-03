import re
from typing import Any, Dict, List, Optional, Set
from pydantic import BaseModel
from backend.app.security.input_guard import SecurityVerdict, SecurityViolation, input_security_guard


class OutputInspectionResult(BaseModel):
    verdict: SecurityVerdict  # ALLOW, REDACT, FLAG, BLOCK, HUMAN_REVIEW
    sanitized_output: str
    violations: List[SecurityViolation] = []
    citations_verified: bool = True
    groundedness_score: float = 1.0
    reason: str = "Output conforms to safety policies."


class OutputGuard:
    """
    Centralized Output Security & Content Guardrail.
    Verifies:
    - PII / Secret Redaction
    - Citation Authenticity (Anti-hallucination)
    - Groundedness / Unsupported claim verification
    - Output schema & policy compliance
    """

    SYSTEM_LEAK_PATTERNS = [
        (r"(?i)\b(my\s+system\s+prompt\s+is|here\s+are\s+my\s+instructions)\b", "SYSTEM_PROMPT_LEAK"),
        (r"(?i)\b(internal\s+api\s+token|database\s+password)\s*[:=]\s*\S+", "CREDENTIAL_LEAK"),
        (r"-----BEGIN\s+(RSA\s+)?PRIVATE\s+KEY-----", "PRIVATE_KEY_EXPOSURE"),
    ]

    def inspect_output(
        self,
        output_text: str,
        source_context_chunks: Optional[List[str]] = None,
        expected_document_ids: Optional[Set[str]] = None,
        cited_document_ids: Optional[List[str]] = None,
        require_grounding: bool = False,
    ) -> OutputInspectionResult:
        violations: List[SecurityViolation] = []
        sanitized = output_text
        verdict = SecurityVerdict.ALLOW
        reasons = []

        # 1. System & Credential Leakage Check
        for regex, leak_type in self.SYSTEM_LEAK_PATTERNS:
            if re.search(regex, output_text):
                violations.append(
                    SecurityViolation(
                        category="DATA_LEAK",
                        severity="CRITICAL",
                        confidence=0.98,
                        detector_name="DataLeakDetector",
                        detection_method="DETERMINISTIC_REGEX",
                        details={"leak_type": leak_type},
                        remediation="Output contains confidential system internals or keys. Block immediately."
                    )
                )
                verdict = SecurityVerdict.BLOCK
                reasons.append(f"Blocked due to confidential {leak_type}.")

        # 2. PII Redaction
        pii_result = input_security_guard.inspect_input(
            text=sanitized,
            pii_action="REDACT"
        )
        pii_violations = [v for v in pii_result.violations if v.category == "PII_DETECTED"]
        if pii_violations:
            sanitized = pii_result.sanitized_input
            violations.extend(pii_violations)
            if verdict != SecurityVerdict.BLOCK:
                verdict = SecurityVerdict.REDACT
            reasons.append(f"Redacted {len(pii_violations)} PII identifier(s) from output.")

        # 3. Citation Verification
        citations_verified = True
        if cited_document_ids and expected_document_ids is not None:
            for doc_id in cited_document_ids:
                if doc_id not in expected_document_ids:
                    citations_verified = False
                    violations.append(
                        SecurityViolation(
                            category="FABRICATED_CITATION",
                            severity="HIGH",
                            confidence=0.95,
                            detector_name="CitationVerifier",
                            detection_method="PROVENANCE_CHECK",
                            details={"invalid_document_id": doc_id},
                            remediation="Document ID cited by the agent does not exist in verified repository."
                        )
                    )
                    reasons.append(f"Unverified citation detected for doc_id: {doc_id}.")
                    if verdict not in (SecurityVerdict.BLOCK, SecurityVerdict.REDACT):
                        verdict = SecurityVerdict.FLAG

        # 4. Groundedness & Unsupported Claims Check
        groundedness_score = 1.0
        if require_grounding and source_context_chunks:
            # Word overlap with source context
            context_words = set(re.findall(r"\w+", " ".join(source_context_chunks).lower()))
            output_words = [w for w in re.findall(r"\w+", sanitized.lower()) if len(w) > 3]

            if output_words:
                matched_count = sum(1 for w in output_words if w in context_words)
                groundedness_score = round(matched_count / len(output_words), 3)

                if groundedness_score < 0.2:
                    violations.append(
                        SecurityViolation(
                            category="UNSUPPORTED_CLAIMS",
                            severity="MEDIUM",
                            confidence=0.85,
                            detector_name="GroundednessChecker",
                            detection_method="CONTEXT_OVERLAP",
                            details={"groundedness_score": groundedness_score},
                            remediation="Output claims show minimal overlap with retrieved source context."
                        )
                    )
                    reasons.append(f"Low groundedness score ({groundedness_score}). Flagged as unsupported claims.")
                    if verdict not in (SecurityVerdict.BLOCK, SecurityVerdict.REDACT):
                        verdict = SecurityVerdict.FLAG

        # Compile consolidated explanation
        final_reason = "; ".join(reasons) if reasons else "Output conforms to safety policies."

        return OutputInspectionResult(
            verdict=verdict,
            sanitized_output=sanitized,
            violations=violations,
            citations_verified=citations_verified,
            groundedness_score=groundedness_score,
            reason=final_reason
        )


output_guard = OutputGuard()

