"""Pure helpers that translate a SEP `EvaluationReport` into the scorecard
shape expected by the frontend, plus the deterministic narrative generator.

Extracted from `interview_result_service.py` to keep that file under the
4 KLoC threshold and to give SEP-related logic an obvious home that does
*not* depend on FastAPI request lifetime, database sessions, or LLM
clients — making it trivially unit-testable in isolation.

Also hosts the bank-slug resolver and the Jaccard-style fuzzy matcher used
by the legacy (non-adaptive) scoring path.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover - only for type hints
    from src.services.sep.evidence_builder import EvaluationReport


# ---------------------------------------------------------------------------
# Bank-slug resolution
# ---------------------------------------------------------------------------
SEP_BANK_SLUGS: tuple[str, ...] = ("backend", "frontend", "algorithm")
SEP_POSITION_KEYWORDS: tuple[tuple[str, str], ...] = (
    ("frontend", "frontend"),
    ("前端", "frontend"),
    ("react", "frontend"),
    ("vue", "frontend"),
    ("angular", "frontend"),
    ("web", "frontend"),
    ("h5", "frontend"),
    ("ui", "frontend"),
    ("algorithm", "algorithm"),
    ("算法", "algorithm"),
    ("机器学习", "algorithm"),
    ("ml", "algorithm"),
    ("ai", "algorithm"),
    ("backend", "backend"),
    ("后端", "backend"),
    ("server", "backend"),
    ("java", "backend"),
    ("python", "backend"),
    ("golang", "backend"),
    ("node", "backend"),
    ("c++", "backend"),
    ("c#", "backend"),
    ("rust", "backend"),
    ("php", "backend"),
    ("ruby", "backend"),
    ("全栈", "backend"),
    ("fullstack", "backend"),
)


def resolve_bank_slug(raw_position: str) -> str:
    """Map a free-form Chinese/English position string to a SEP bank slug."""
    raw = str(raw_position or "").strip().lower()
    if raw in SEP_BANK_SLUGS:
        return raw
    for keyword, slug in SEP_POSITION_KEYWORDS:
        if keyword in raw:
            return slug
    return "backend"


# ---------------------------------------------------------------------------
# Jaccard fuzzy matcher (legacy non-adaptive path)
# ---------------------------------------------------------------------------
SEP_MIN_BANK_COVERAGE = 0.5  # at least 50% of Q&A pairs must match a real rubric
SEP_MIN_MATCHED_PAIRS = 2

_QUESTION_TOKENIZER = None


def _tokenize(text: str) -> set[str]:
    """Tokenise a question for matching: drop punctuation, length >= 2 (CJK-aware)."""
    global _QUESTION_TOKENIZER  # noqa: PLW0603
    if _QUESTION_TOKENIZER is None:
        try:
            import jieba

            _QUESTION_TOKENIZER = jieba
        except Exception:  # noqa: BLE001 - jieba missing → fall back to character set
            _QUESTION_TOKENIZER = False
    if not text:
        return set()
    if _QUESTION_TOKENIZER:
        tokens = {tok.strip().lower() for tok in _QUESTION_TOKENIZER.cut(text) if len(tok.strip()) >= 2}
    else:
        tokens = set()
    # Always include 2-char windows so we degrade gracefully when jieba is absent.
    clean = "".join(ch for ch in text if ch.isalnum() or "一" <= ch <= "鿿")
    tokens.update(clean[i : i + 2].lower() for i in range(len(clean) - 1))
    return tokens


def match_question(question_text: str, bank_questions: list[dict], used_ids: set[str]) -> dict | None:
    """Match an LLM-asked question to a bank entry using Jaccard token overlap.

    Returns None when no entry passes the similarity floor. This prevents the
    pipeline from silently inventing scores for questions outside the bank.
    """
    q_tokens = _tokenize(question_text)
    if len(q_tokens) < 3:
        return None
    best: tuple[float, dict | None] = (0.0, None)
    for bq in bank_questions:
        if bq["id"] in used_ids:
            continue
        b_tokens = _tokenize(bq.get("question_template", "") + " " + bq.get("concept", ""))
        if not b_tokens:
            continue
        inter = len(q_tokens & b_tokens)
        if inter == 0:
            continue
        union = len(q_tokens | b_tokens) or 1
        jaccard = inter / union
        if jaccard >= 0.18 and inter >= 3 and jaccard > best[0]:
            best = (jaccard, bq)
    return best[1]


# Dimension key → human label. Duplicated keys map intentionally because the
# upstream LLM may emit slight variants of the same dimension.
DIMENSION_LABELS: dict[str, str] = {
    "technical_competence": "技术能力",
    "problem_solving": "问题解决",
    "problem_solving_innovation": "问题解决",
    "communication": "沟通表达",
    "communication_clarity": "沟通表达",
    "soft_skills": "综合素质",
    "soft_skills_team_fit": "综合素质",
}


def sep_narrative_from_report(sep_report: EvaluationReport) -> dict[str, list[str] | str]:
    """Build deterministic strengths/risks/suggestions/summary from a SEP report.

    Walks the evidence chain and groups items by type and dimension. Each
    bullet cites a concrete concept so the user can see *why* a score moved,
    not just an opaque number.
    """
    strengths: list[str] = []
    risks: list[str] = []
    suggestions: list[str] = []

    by_dimension: dict[str, list] = {}
    for item in sep_report.evidence_chain:
        by_dimension.setdefault(item.dimension, []).append(item)

    for dim, items in by_dimension.items():
        dim_label = DIMENSION_LABELS.get(dim, dim)
        positives = [
            it for it in items
            if it.score_delta > 0 and it.evidence_type in {"keyword_hit", "bonus_keyword"}
        ]
        misconceptions = [it for it in items if it.evidence_type == "misconception"]
        hedges = [it for it in items if it.evidence_type == "hedge"]

        if positives:
            top = max(positives, key=lambda it: it.score_delta)
            concept = top.concept or "相关考点"
            strengths.append(
                f"{dim_label}：在「{concept}」上覆盖了核心要点（{top.evidence_text}）。"
            )

        if misconceptions:
            top = max(misconceptions, key=lambda it: -it.score_delta)
            concept = top.concept or "相关考点"
            risks.append(
                f"{dim_label}：「{concept}」存在概念误区——{top.evidence_text}。"
            )
            suggestions.append(
                f"重点复习「{concept}」的标准定义与边界条件，避免再次混淆。"
            )

        if hedges:
            risks.append(f"{dim_label}：回答中模糊词较多，可信度被打折扣。")
            suggestions.append(
                f"练习用「我做了 X，达到了 Y」这类陈述句来表达对{dim_label}的掌握。"
            )

    dims_summary = "、".join(
        f"{DIMENSION_LABELS.get(k, k)} {v}" for k, v in sep_report.dimensions.items()
    )
    summary = (
        f"基于 {len(sep_report.evidence_chain)} 条客观证据生成。综合 {sep_report.overall} 分，"
        f"分项得分：{dims_summary}。"
    )
    return {
        "summary": summary,
        "strengths": strengths,
        "risks": risks,
        "suggestions": suggestions,
    }


def scorecard_from_sep_report(
    sep_report: EvaluationReport,
    *,
    coverage: float = 1.0,
) -> dict[str, Any]:
    """Convert a SEP `EvaluationReport` into the scorecard dict the frontend expects.

    `coverage` is the share of Q&A pairs that mapped to a real bank question;
    surfaced as `sep_coverage` + `score_source` so the UI can show users
    whether the number is fully grounded or partially LLM-fallback.
    """
    dimensions = [
        {"key": k, "name": DIMENSION_LABELS.get(k, k), "score": v}
        for k, v in sep_report.dimensions.items()
    ]
    narrative = sep_narrative_from_report(sep_report)
    return {
        "overall": sep_report.overall,
        "dimensions": dimensions,
        "strengths": narrative["strengths"],
        "risks": narrative["risks"],
        "suggestions": narrative["suggestions"],
        "summary": narrative["summary"],
        "sep_evidence_chain": [
            {
                "dimension": item.dimension,
                "question": item.question,
                "concept": item.concept,
                "score_delta": item.score_delta,
                "evidence_text": item.evidence_text,
                "evidence_type": item.evidence_type,
                "difficulty": item.difficulty,
            }
            for item in sep_report.evidence_chain
        ],
        "sep_theta_trajectory": sep_report.theta_trajectory,
        "sep_coverage": round(coverage, 2),
        "score_source": "sep" if coverage >= 0.99 else "sep_partial",
    }
