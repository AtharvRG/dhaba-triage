"""
Sanitizer: two jobs.
1. Detect text that tries to give the ASSISTANT instructions
   (prompt injection) and flag it — never obey it.
2. Guarantee ticket text never reaches logs (helped by log.py's allowlist).
"""
import re
from dataclasses import dataclass, field

# Named patterns — we log the NAME, never the matched text
# (the matched text is user content and must not hit logs).
INJECTION_PATTERNS: dict[str, re.Pattern] = {
    "ignore_previous": re.compile(
        r"ignore\s+(?:all\s+)?(?:your\s+)?previous\s+instructions", re.I),
    "fake_system_note": re.compile(
        r"system\s+note\s+for\s+the\s+support\s+assistant", re.I),
    "address_the_agent": re.compile(
        r"for\s+the\s+(?:automated\s+)?(?:agent|ai|bot|assistant)\s+reading\s+this", re.I),
    "prompt_exfiltration": re.compile(
        r"(?:full\s+text\s+of\s+your|your)\s+system\s+prompt|internal\s+refund\s+rules", re.I),
    "auto_resolve": re.compile(
        r"mark\s+this\s+ticket\s+(?:as\s+)?resolved", re.I),
    "command_refund": re.compile(
        r"approve\s+a\s+full\s+refund|process\s+(?:the\s+)?refund\s+(?:now|immediately)", re.I),
    "disregard_rules": re.compile(
        r"disregard\s+(?:the\s+)?(?:above|previous|any)", re.I),
}


@dataclass
class SanitizeReport:
    injection_detected: bool = False
    matched_pattern_names: list[str] = field(default_factory=list)

    # The text we pass to the model — original words (wrapped in
    # clear data markers at prompt-build time), because the classifier
    # needs to understand the complaint, including the angry parts.
    # We just never FOLLOW instructions found in it.
    prompt_body: str = ""


def sanitize(ticket) -> SanitizeReport:
    text = f"{ticket.subject}\n{ticket.body}"
    hits = [name for name, pat in INJECTION_PATTERNS.items() if pat.search(text)]
    return SanitizeReport(
        injection_detected=bool(hits),
        matched_pattern_names=hits,
        prompt_body=text,
    )