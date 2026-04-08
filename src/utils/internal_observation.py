"""Utilities for filtering internal interview observation tags from model outputs."""

from __future__ import annotations

import re
from dataclasses import dataclass

VIDEO_OBSERVATION_START = "<internal_interview_observation>"
VIDEO_OBSERVATION_END = "</internal_interview_observation>"
VIDEO_OBSERVATION_LINE_PREFIX = "[[video_observation_internal]]"

VIDEO_OBSERVATION_BLOCK_PATTERN = re.compile(
    rf"{re.escape(VIDEO_OBSERVATION_START)}[\s\S]*?{re.escape(VIDEO_OBSERVATION_END)}",
    re.MULTILINE,
)


def strip_internal_observation_text(text: str) -> str:
    """Remove any internal interview observation block/tags from plain text."""
    normalized = str(text or "")
    normalized = VIDEO_OBSERVATION_BLOCK_PATTERN.sub("", normalized)

    # If the start tag appears without a closing tag in streamed text,
    # drop everything after the start marker.
    if VIDEO_OBSERVATION_START in normalized:
        normalized = normalized.split(VIDEO_OBSERVATION_START, 1)[0]

    # Remove orphan tags that may appear independently.
    normalized = normalized.replace(VIDEO_OBSERVATION_START, "")
    normalized = normalized.replace(VIDEO_OBSERVATION_END, "")

    # Remove any internal prefixed lines.
    filtered_lines = [
        line for line in normalized.splitlines() if VIDEO_OBSERVATION_LINE_PREFIX not in line
    ]
    normalized = "\n".join(filtered_lines)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized).strip()
    return normalized


def _longest_overlap_suffix_prefix(text: str, marker: str) -> int:
    """Length of the longest suffix of text that is a prefix of marker."""
    if not text or not marker:
        return 0

    max_overlap = min(len(text), len(marker) - 1)
    for size in range(max_overlap, 0, -1):
        if text.endswith(marker[:size]):
            return size
    return 0


@dataclass
class InternalObservationStreamSanitizer:
    """Incremental sanitizer for streamed model deltas."""

    _raw_content: str = ""
    _emitted_length: int = 0

    def feed(self, delta: str) -> str:
        self._raw_content += str(delta or "")
        sanitized = strip_internal_observation_text(self._raw_content)
        safe_end = len(sanitized) - self._tail_overlap(sanitized)

        if safe_end < self._emitted_length:
            # Fallback safety in rare shrinking cases.
            self._emitted_length = max(0, safe_end)

        if safe_end <= self._emitted_length:
            return ""

        chunk = sanitized[self._emitted_length : safe_end]
        self._emitted_length = safe_end
        return chunk

    def flush(self) -> str:
        sanitized = strip_internal_observation_text(self._raw_content)
        safe_end = len(sanitized) - self._tail_overlap(sanitized)
        if safe_end <= self._emitted_length:
            return ""

        chunk = sanitized[self._emitted_length : safe_end]
        self._emitted_length = safe_end
        return chunk

    def full_text(self) -> str:
        sanitized = strip_internal_observation_text(self._raw_content)
        overlap = self._tail_overlap(sanitized)
        if overlap > 0:
            return sanitized[:-overlap]
        return sanitized

    @staticmethod
    def _tail_overlap(text: str) -> int:
        markers = (
            VIDEO_OBSERVATION_START,
            VIDEO_OBSERVATION_END,
            VIDEO_OBSERVATION_LINE_PREFIX,
        )
        return max(_longest_overlap_suffix_prefix(text, marker) for marker in markers)
