import base64
import binascii
import codecs
import enum
import re
import time
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field


class SecurityVerdict(str, enum.Enum):
    ALLOW = "ALLOW"
    BLOCK = "BLOCK"
    REDACT = "REDACT"
    FLAG = "FLAG"
    HUMAN_REVIEW = "HUMAN_REVIEW"


class SecurityViolation(BaseModel):
    category: str
    severity: str  # LOW, MEDIUM, HIGH, CRITICAL
    confidence: float
    detector_name: str
    detection_method: str  # DETERMINISTIC_REGEX, LUHN_CHECKSUM, OBFUSCATION_DECODER, LENGTH_VALIDATOR
    details: Dict[str, Any]
    remediation: str


class InputInspectionResult(BaseModel):
    verdict: SecurityVerdict
    is_safe: bool
    violations: List[SecurityViolation] = []
    sanitized_input: str
    confidence_score: float
    inspection_time_ms: float
    notice: str = "Confidence score reflects deterministic heuristic boundaries; non-zero false negative rate inherent to semantic evaluation."


class InputSecurityGuard:
    """
    Centralized Input Security Firewall.
    Enforces deterministic validation for Prompt Injections, Jailbreaks, PII,
    Sensitive Data, Length Boundaries, and Malicious Obfuscated Payloads.
    """

    MAX_INPUT_LENGTH = 8192
    MAX_REPETITION_THRESHOLD = 80

    # 1. Prompt Injection Signatures
    PROMPT_INJECTION_RULES = [
        (r"(?i)\bignore\s+(all\s+)?(previous|prior|above|former)\s+(instructions|directives|prompts|commands)\b", "INSTRUCTION_OVERRIDE", "CRITICAL", 0.95),
        (r"(?i)\bdisregard\s+(all\s+)?(previous|prior|system)\s+(rules|prompts|commands|constraints)\b", "SYSTEM_RULE_BYPASS", "CRITICAL", 0.95),
        (r"(?i)\b(forget|reset)\s+(all\s+)?(previous|initial|system)\s+(instructions|prompts)\b", "INSTRUCTION_RESET", "CRITICAL", 0.92),
        (r"(?i)\bnew\s+system\s+(instructions|prompt|directive)\b", "SYSTEM_PROMPT_INJECTION", "HIGH", 0.90),
        (r"(?i)(\[\s*system\s*\]|\{\s*\"role\"\s*:\s*\"system\"|<\|im_start\|>system|<<SYS>>)", "SYSTEM_ROLE_SIMULATION", "CRITICAL", 0.98),
        (r"(?i)\b(print|reveal|output|display|show|leak)\s+(the\s+)?(system\s+prompt|developer\s+instructions|secret\s+key)\b", "SYSTEM_PROMPT_EXFILTRATION", "HIGH", 0.92),
        (r"(?i)\bdo\s+not\s+follow\s+(the\s+)?(original|standard)\s+guidelines\b", "GUIDELINE_EVASION", "HIGH", 0.88),
    ]

    # 2. Jailbreak Signatures
    JAILBREAK_RULES = [
        (r"(?i)\byou\s+are\s+now\s+(an?\s+)?(unrestricted|jailbroken|evil|unfiltered|dan|aim)\b", "PERSONA_HIJACKING_JAILBREAK", "CRITICAL", 0.96),
        (r"(?i)\b(dan|aim|mongo\s+tom|evil\s+confidant)\s+(mode|persona|framework)\b", "KNOWN_JAILBREAK_FRAMEWORK", "CRITICAL", 0.95),
        (r"(?i)\bdeveloper\s+mode\s+(is\s+)?(enabled|active|on)\b", "DEVELOPER_MODE_JAILBREAK", "CRITICAL", 0.94),
        (r"(?i)\bpretend\s+(you\s+can\s+do\s+anything|you\s+have\s+no\s+rules|there\s+are\s+no\s+safety\s+filters)\b", "SAFETY_FILTER_EVASION", "HIGH", 0.90),
        (r"(?i)\bhypothetical\s+fictional\s+scenario\s+where\s+all\s+rules\s+are\s+suspended\b", "HYPOTHETICAL_EVASION", "HIGH", 0.88),
    ]

    # 3. PII & Sensitive Information Patterns
    PII_RULES = [
        (r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", "EMAIL_ADDRESS", "MEDIUM", 0.95),
        (r"\b(?:\+?(\d{1,3}))?[-. ]?\(?\d{3}\)?[-. ]?\d{3}[-. ]?\d{4}\b", "PHONE_NUMBER", "LOW", 0.85),
        (r"\b\d{3}-\d{2}-\d{4}\b", "US_SOCIAL_SECURITY_NUMBER", "HIGH", 0.98),
        (r"\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|3[47][0-9]{13}|6(?:011|5[0-9]{2})[0-9]{12})\b", "CREDIT_CARD_PAN", "HIGH", 0.95),
        (r"\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b", "IPV4_ADDRESS", "LOW", 0.90),
        (r"\b(sk-[a-zA-Z0-9]{20,}|AKIA[0-9A-Z]{16}|ghp_[a-zA-Z0-9]{36})\b", "API_SECRET_KEY", "CRITICAL", 0.99),
        (r"-----BEGIN\s+(RSA\s+)?PRIVATE\s+KEY-----", "PRIVATE_KEY_CERTIFICATE", "CRITICAL", 0.99),
    ]

    # 4. Malicious Instruction Patterns
    MALICIOUS_INSTRUCTION_RULES = [
        (r"(?i)\b(drop\s+table|delete\s+from|insert\s+into|truncate\s+table)\b", "SQL_MANIPULATION_ATTEMPT", "HIGH", 0.90),
        (r"(?i)\b(rm\s+-rf|sudo\s+rm|format\s+c:|chmod\s+777|wget\s+http|curl\s+http.*\|\s*sh)\b", "DESTRUCTIVE_SHELL_COMMAND", "CRITICAL", 0.98),
        (r"(?i)\bexfiltrate\s+(data|credentials|tokens)\s+to\b", "DATA_EXFILTRATION_COMMAND", "CRITICAL", 0.95),
    ]

    def _validate_luhn(self, card_number_str: str) -> bool:
        """Luhn algorithm validation for credit card digits."""
        digits = [int(c) for c in card_number_str if c.isdigit()]
        if len(digits) < 13 or len(digits) > 19:
            return False
        total = 0
        reverse_digits = digits[::-1]
        for idx, d in enumerate(reverse_digits):
            if idx % 2 == 1:
                doubled = d * 2
                total += (doubled - 9) if doubled > 9 else doubled
            else:
                total += d
        return total % 10 == 0

    def _decode_obfuscated_payloads(self, text: str) -> List[Tuple[str, str]]:
        """Identifies base64 and hex encoded chunks and returns decoded payloads."""
        decoded_items = []
        # Look for potential base64 blocks (length >= 16, alphanumeric + =/)
        b64_candidates = re.findall(r"\b[A-Za-z0-9+/]{16,}={0,2}\b", text)
        for cand in b64_candidates:
            try:
                decoded_bytes = base64.b64decode(cand, validate=True)
                decoded_str = decoded_bytes.decode("utf-8", errors="ignore")
                if len(decoded_str) >= 8 and any(c.isalpha() for c in decoded_str):
                    decoded_items.append(("BASE64_DECODED", decoded_str))
            except (binascii.Error, UnicodeDecodeError):
                pass
        return decoded_items

    def inspect_input(
        self,
        text: str,
        pii_action: str = "REDACT",  # BLOCK, REDACT, FLAG
        prompt_injection_threshold: float = 0.75,
        max_length: Optional[int] = None,
    ) -> InputInspectionResult:
        start_time = time.perf_counter()
        violations: List[SecurityViolation] = []
        sanitized = text
        effective_max_len = max_length or self.MAX_INPUT_LENGTH

        # 1. Input Length & Repetition Check
        if len(text) > effective_max_len:
            violations.append(
                SecurityViolation(
                    category="INPUT_LENGTH_VIOLATION",
                    severity="HIGH",
                    confidence=1.0,
                    detector_name="InputLengthValidator",
                    detection_method="LENGTH_VALIDATOR",
                    details={"length": len(text), "max_allowed": effective_max_len},
                    remediation=f"Truncate input to within {effective_max_len} characters."
                )
            )

        # Repetitive character bomb check
        for char in set(text):
            if char * self.MAX_REPETITION_THRESHOLD in text:
                violations.append(
                    SecurityViolation(
                        category="TOKEN_BOMBING",
                        severity="MEDIUM",
                        confidence=0.90,
                        detector_name="TokenBombDetector",
                        detection_method="REPETITION_ANOMALY",
                        details={"char": char, "repetition_threshold": self.MAX_REPETITION_THRESHOLD},
                        remediation="Remove excessive repetitive character sequences."
                    )
                )
                break

        # 2. Direct Prompt Injection Check
        for regex, rule_name, severity, confidence in self.PROMPT_INJECTION_RULES:
            match = re.search(regex, text)
            if match and confidence >= prompt_injection_threshold:
                violations.append(
                    SecurityViolation(
                        category="PROMPT_INJECTION",
                        severity=severity,
                        confidence=confidence,
                        detector_name="PromptInjectionHeuristic",
                        detection_method="DETERMINISTIC_REGEX",
                        details={"rule": rule_name, "matched_text": match.group(0)[:60]},
                        remediation="Input contains explicit directive override syntax. Block request."
                    )
                )

        # 3. Jailbreak Detection
        for regex, rule_name, severity, confidence in self.JAILBREAK_RULES:
            match = re.search(regex, text)
            if match:
                violations.append(
                    SecurityViolation(
                        category="JAILBREAK_ATTEMPT",
                        severity=severity,
                        confidence=confidence,
                        detector_name="JailbreakDetector",
                        detection_method="DETERMINISTIC_REGEX",
                        details={"rule": rule_name, "matched_text": match.group(0)[:60]},
                        remediation="Input attempts persona subversion or developer mode bypass. Block request."
                    )
                )

        # 4. Obfuscated Payloads Check
        decoded_payloads = self._decode_obfuscated_payloads(text)
        for encoding_type, decoded_text in decoded_payloads:
            for regex, rule_name, severity, confidence in self.PROMPT_INJECTION_RULES:
                if re.search(regex, decoded_text):
                    violations.append(
                        SecurityViolation(
                            category="PROMPT_INJECTION",
                            severity="CRITICAL",
                            confidence=0.98,
                            detector_name="ObfuscationDecoder",
                            detection_method="OBFUSCATION_DECODER",
                            details={"encoding": encoding_type, "decoded_rule": rule_name},
                            remediation="Hidden malicious directive found inside encoded payload. Block request."
                        )
                    )

        # 5. Malicious Instructions Check
        for regex, rule_name, severity, confidence in self.MALICIOUS_INSTRUCTION_RULES:
            match = re.search(regex, text)
            if match:
                violations.append(
                    SecurityViolation(
                        category="MALICIOUS_INSTRUCTION",
                        severity=severity,
                        confidence=confidence,
                        detector_name="MaliciousInstructionFilter",
                        detection_method="DETERMINISTIC_REGEX",
                        details={"rule": rule_name, "matched_text": match.group(0)[:60]},
                        remediation="Forbidden destructive instruction detected. Block request."
                    )
                )

        # 6. PII & Sensitive Information Detection
        for regex, pii_type, severity, confidence in self.PII_RULES:
            matches = list(re.finditer(regex, text))
            for m in matches:
                matched_val = m.group(0)
                # For credit cards, verify Luhn
                if pii_type == "CREDIT_CARD_PAN" and not self._validate_luhn(matched_val):
                    continue

                violations.append(
                    SecurityViolation(
                        category="PII_DETECTED",
                        severity=severity,
                        confidence=confidence,
                        detector_name="PIIDetector",
                        detection_method="DETERMINISTIC_REGEX",
                        details={"pii_type": pii_type, "masked_preview": matched_val[:2] + "****" + matched_val[-2:]},
                        remediation=f"Sensitive identifier detected ({pii_type}). Apply {pii_action} policy."
                    )
                )
                
                # Apply redaction to sanitized output
                if pii_action in ("REDACT", "BLOCK"):
                    replacement = f"[REDACTED_{pii_type}]"
                    sanitized = sanitized.replace(matched_val, replacement)

        # Determine Verdict
        has_critical_violation = any(v.severity in ("CRITICAL", "HIGH") and v.category in ("PROMPT_INJECTION", "JAILBREAK_ATTEMPT", "MALICIOUS_INSTRUCTION", "INPUT_LENGTH_VIOLATION") for v in violations)
        has_pii_block = any(v.category == "PII_DETECTED" and pii_action == "BLOCK" for v in violations)

        if has_critical_violation or has_pii_block:
            verdict = SecurityVerdict.BLOCK
            is_safe = False
        elif any(v.category == "PII_DETECTED" for v in violations):
            verdict = SecurityVerdict.REDACT if pii_action == "REDACT" else SecurityVerdict.FLAG
            is_safe = True
        elif violations:
            verdict = SecurityVerdict.FLAG
            is_safe = True
        else:
            verdict = SecurityVerdict.ALLOW
            is_safe = True

        elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
        highest_conf = max([v.confidence for v in violations], default=1.0 if is_safe else 0.8)

        return InputInspectionResult(
            verdict=verdict,
            is_safe=is_safe,
            violations=violations,
            sanitized_input=sanitized,
            confidence_score=highest_conf,
            inspection_time_ms=elapsed_ms
        )


input_security_guard = InputSecurityGuard()

