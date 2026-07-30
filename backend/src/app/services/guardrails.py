from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from app.models.schemas import RetrievalChunk

TOXIC_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\b(kill|murder|suicide|self-harm)\b", re.IGNORECASE),
    re.compile(r"\b(hate|racist|sexist|slur)\b", re.IGNORECASE),
    re.compile(r"\b(dox|doxx|leak.*personal|private.*info)\b", re.IGNORECASE),
]

INJECTION_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\bignore.*(previous|above|all).*instructions\b", re.IGNORECASE),
    re.compile(r"\b(forget|disregard|override).*(prompt|instructions|system)\b", re.IGNORECASE),
    re.compile(r"\byou are (not |no longer |actually )?", re.IGNORECASE),
    re.compile(r"\brevert\b.*\bprompt\b", re.IGNORECASE),
    re.compile(r"\b(new )?instructions?\b.*\b(follow|obey|listen)\b", re.IGNORECASE),
    re.compile(r"\b(dan|jailbreak|system prompt)\b", re.IGNORECASE),
]

PII_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("email", re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")),
    ("ssn", re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
    ("phone", re.compile(r"\b\d{3}[-.)]\d{3}[-.]?\d{4}\b")),
    (
        "api_key",
        re.compile(
            r"\b(sk-[a-zA-Z0-9]{20,}|[A-Za-z0-9]{32,}|api[-_]?key[-_]?[=:]\s*\S+)\b", re.IGNORECASE
        ),
    ),
    ("ip_address", re.compile(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b")),
    ("credit_card", re.compile(r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b")),
]


@dataclass
class GuardrailResult:
    passed: bool
    reason: str | None = None
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class CitationResult:
    supported_sentences: list[str]
    unsupported_sentences: list[str]
    grounding_score: float
    hallucination_rate: float


class ContentSafetyChecker:
    def check_input(self, text: str) -> GuardrailResult:
        for pattern in TOXIC_PATTERNS:
            match = pattern.search(text)
            if match:
                return GuardrailResult(
                    passed=False,
                    reason="Blocked by content safety",
                    details={"matched_pattern": match.group(), "pattern_type": "toxic"},
                )
        for pattern in INJECTION_PATTERNS:
            match = pattern.search(text)
            if match:
                return GuardrailResult(
                    passed=False,
                    reason="Possible prompt injection detected",
                    details={"matched_pattern": match.group(), "pattern_type": "injection"},
                )
        return GuardrailResult(passed=True)

    def check_output(self, text: str) -> GuardrailResult:
        for pattern in TOXIC_PATTERNS:
            match = pattern.search(text)
            if match:
                return GuardrailResult(
                    passed=False,
                    reason="Output blocked by content safety",
                    details={"matched_pattern": match.group(), "pattern_type": "toxic"},
                )
        return GuardrailResult(passed=True)


class PIIRedactor:
    def __init__(self, replacement: str = "[REDACTED]") -> None:
        self.replacement = replacement

    def detect(self, text: str) -> dict[str, list[str]]:
        found: dict[str, list[str]] = {}
        for name, pattern in PII_PATTERNS:
            matches = pattern.findall(text)
            if matches:
                found[name] = matches
        return found

    def redact(self, text: str) -> str:
        for _, pattern in PII_PATTERNS:
            text = pattern.sub(self.replacement, text)
        return text


def split_sentences(text: str) -> list[str]:
    text = re.sub(r"\s+", " ", text).strip()
    sentences = re.split(r"(?<=[.!?])\s+", text)
    return [s.strip() for s in sentences if s.strip()]


class CitationVerifier:
    def compute_grounding(self, answer: str, chunks: list[RetrievalChunk]) -> CitationResult:
        if not answer.strip() or not chunks:
            return CitationResult(
                supported_sentences=[],
                unsupported_sentences=split_sentences(answer) if answer.strip() else [],
                grounding_score=0.0,
                hallucination_rate=1.0 if answer.strip() else 0.0,
            )

        chunk_texts = [chunk.content.lower() for chunk in chunks]
        sentences = split_sentences(answer)
        supported: list[str] = []
        unsupported: list[str] = []

        for sentence in sentences:
            sentence_lower = sentence.lower()
            words = set(self._tokenize(sentence_lower))
            best_overlap = 0.0
            for chunk_text in chunk_texts:
                chunk_words = set(self._tokenize(chunk_text))
                if not words or not chunk_words:
                    continue
                overlap = len(words & chunk_words) / len(words)
                best_overlap = max(best_overlap, overlap)
            if best_overlap >= 0.3:
                supported.append(sentence)
            else:
                unsupported.append(sentence)

        total = len(sentences)
        supported_count = len(supported)
        grounding_score = supported_count / total if total > 0 else 0.0
        hallucination_rate = 1.0 - grounding_score
        return CitationResult(
            supported_sentences=supported,
            unsupported_sentences=unsupported,
            grounding_score=round(grounding_score, 4),
            hallucination_rate=round(hallucination_rate, 4),
        )

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        return re.findall(r"[a-zA-Z0-9]+", text)


@dataclass
class RelevanceFilter:
    min_score: float = 0.05

    def filter_chunks(self, chunks: list[RetrievalChunk]) -> list[RetrievalChunk]:
        return [chunk for chunk in chunks if chunk.score >= self.min_score]


@dataclass
class GuardrailService:
    safety: ContentSafetyChecker = field(default_factory=ContentSafetyChecker)
    pii: PIIRedactor = field(default_factory=PIIRedactor)
    citation: CitationVerifier = field(default_factory=CitationVerifier)
    relevance: RelevanceFilter = field(default_factory=RelevanceFilter)

    def check_input(self, text: str) -> GuardrailResult:
        return self.safety.check_input(text)

    def check_output(self, text: str) -> GuardrailResult:
        return self.safety.check_output(text)

    def redact_pii(self, text: str) -> str:
        return self.pii.redact(text)

    def detect_pii(self, text: str) -> dict[str, list[str]]:
        return self.pii.detect(text)

    def compute_grounding(self, answer: str, chunks: list[RetrievalChunk]) -> CitationResult:
        return self.citation.compute_grounding(answer, chunks)

    def filter_chunks(self, chunks: list[RetrievalChunk]) -> list[RetrievalChunk]:
        return self.relevance.filter_chunks(chunks)
