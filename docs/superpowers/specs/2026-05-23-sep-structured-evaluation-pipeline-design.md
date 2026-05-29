# SEP Design Spec: Structured Evaluation Pipeline
> Date: 2026-05-23 | Status: **Implemented** (2026-05, in working tree) | Competition: AI Application Development Track

> **Implementation notes** (divergences from this spec, verified 2026-05-29):
> - **Added** `src/services/sep/session_cache.py` (thread-scoped `SEPSession`). The agent seeds the
>   selected question id at *ask-time* via the `pick_sep_adaptive_question` tool, so scoring matches
>   answers to the exact bank question rather than reconstructing the mapping post-hoc.
> - **Added** `src/services/interview_result_sep_helpers.py` — pure (IO-free) report→scorecard
>   conversion, deterministic narrative, bank-slug resolution, and a Jaccard fuzzy matcher used by the
>   legacy/non-adaptive fallback path. Carries a coverage-based `score_source` flag (`sep` vs `sep_partial`).
> - **Dropped** `CognitiveTimeline.vue` (the third frontend component in §6). Only `EvidenceChain.vue`
>   and `AdaptiveTrajectory.vue` were built and wired into `InterviewResultView.vue`.
> - **Status**: 48 SEP unit tests pass (`test/unit/sep/`); frontend builds clean. Question banks live at
>   `src/data/question_banks/` and are tracked via a `.gitignore` negative rule (`src/data` is otherwise ignored).

## 1. Core Claim

Current AI interview products share a fundamental flaw: the evaluation path is
`candidate answer → LLM → score`. The LLM acts as both interviewer and judge.
Scores are inexplicable, non-reproducible, and drift with model versions.

**SEP's core claim**: LLM handles only natural language I/O (question phrasing,
narrative generation). All scoring logic is deterministic, traceable, and
model-independent.

**Verifiable competition proposition**: Swapping GPT-4 for Qwen produces < 5-point
variance in dimension scores.

---

## 2. Three-Layer Architecture

```
Layer 1: Adaptive Question Selector
  Input:  candidate history + current ability estimate θ
  Output: next question (maximizes information gain, covers untested domains)
  Method: simplified IRT + greedy domain-coverage constraint

         ↓  question + candidate answer

Layer 2: Cognitive Feature Extractor
  Input:  raw answer text
  Output: 8-dimensional feature vector
  Method: rule-based + keyword matching + statistics — ZERO LLM calls

         ↓  feature vectors × N questions

Layer 3: Evidence Chain Builder
  Input:  feature vectors + question rubrics
  Output: evidence items + dimension scores + evidence-chain report
  Method: rubric mapping engine, deterministic computation

         ↓
  LLM called ONCE here to translate evidence items into narrative text
```

---

## 3. Layer 1 — Adaptive Question Selector

### Question Bank Schema

Stored in `src/data/question_banks/{domain}.json`:

```json
{
  "id": "tcp-001",
  "domain": "networking",
  "concept": "TCP三次握手",
  "difficulty": 0.65,
  "question_template": "请解释TCP建立连接的过程",
  "rubric": {
    "required": ["SYN", "SYN-ACK", "ACK"],
    "bonus": ["TIME_WAIT", "半连接队列", "SYN flood防护"],
    "misconceptions": ["四次握手建立连接", "握手传输数据"]
  }
}
```

Initial coverage: 3 positions (backend / frontend / algorithm), 20–30 questions
each, across 4–6 domains. Difficulty hand-calibrated in [0.1, 0.9].

### Ability Estimation

Simplified Bayesian update — avoids full IRT parameter fitting:

```python
def update_ability(θ: float, question_difficulty: float, answer_score: float) -> float:
    expected = 1 / (1 + math.exp(-3 * (θ - question_difficulty)))
    error = answer_score - expected
    return max(0.1, min(0.9, θ + 0.3 * error))
```

### Question Selection

```python
def select_next_question(θ, asked_ids, question_bank) -> Question:
    candidates = [q for q in question_bank if q.id not in asked_ids]
    by_info = sorted(candidates, key=lambda q: abs(q.difficulty - θ))
    asked_domains = {q.domain for q in asked_questions}
    uncovered = [q for q in by_info if q.domain not in asked_domains]
    return uncovered[0] if uncovered else by_info[0]
```

---

## 4. Layer 2 — Cognitive Feature Extractor

Produces an 8-dimensional feature vector per answer — **zero LLM calls**:

| Feature | Computation | Meaning |
|---------|-------------|---------|
| `required_hit_rate` | hits / total required keywords | Knowledge coverage |
| `bonus_hit_count` | count of bonus keyword hits | Depth |
| `misconception_count` | count of misconception keywords found | Errors |
| `star_s` | contains background/context words | STAR Situation |
| `star_t` | contains task/goal/responsibility words | STAR Task |
| `star_a` | contains "I did/implemented/designed" | STAR Action |
| `star_r` | contains "finally/result/improved" | STAR Result |
| `hedge_ratio` | hedge words / total words | Certainty |

```python
@dataclass
class AnswerFeatures:
    required_hit_rate: float
    bonus_hit_count: int
    misconception_count: int
    star_scores: dict[str, bool]   # {"S": bool, "T": bool, "A": bool, "R": bool}
    hedge_ratio: float

    def to_answer_score(self) -> float:
        base         = self.required_hit_rate
        bonus        = min(0.2, self.bonus_hit_count * 0.05)
        star_bonus   = sum(self.star_scores.values()) / 4 * 0.1
        penalty      = min(0.3, self.misconception_count * 0.15)
        hedge_penalty = self.hedge_ratio * 0.1
        return max(0.0, min(1.0, base + bonus + star_bonus - penalty - hedge_penalty))
```

---

## 5. Layer 3 — Evidence Chain Builder

### Evidence Item

```python
@dataclass
class EvidenceItem:
    dimension: str        # "technical_competence"
    question: str         # question text
    concept: str          # "TCP三次握手"
    score_delta: int      # +8 / -5 / 0
    evidence_text: str    # "提到了SYN、SYN-ACK、ACK三个阶段"
    evidence_type: str    # "keyword_hit" | "misconception" | "star_complete" | "hedge"
```

### Rubric Score Map

```python
RUBRIC_SCORE_MAP = {
    "required_keyword_hit": lambda rate: round(rate * 15),   # max +15
    "bonus_keyword_hit":    lambda n:    min(10, n * 3),     # max +10
    "misconception_found":  lambda n:    -min(15, n * 8),    # max -15
    "star_complete":        lambda s:    round(s * 8),       # max +8
    "hedge_heavy":          lambda r:    -round(r * 5),      # max -5
}
```

### Position → Dimension Mapping

```python
POSITION_DIMENSION_MAP = {
    "backend": {
        "networking":    "technical_competence",
        "database":      "technical_competence",
        "algorithms":    "problem_solving",
        "system_design": "problem_solving",
        "behavioral":    "soft_skills",
    },
    # frontend / algorithm / pm follow the same pattern
}
```

### Score Assembly

```python
def build_evidence_chain(answers, questions, position) -> EvaluationReport:
    evidence_items = []
    dimension_scores = defaultdict(list)

    for features, question in zip(answers, questions):
        items = extract_evidence_items(features, question)
        dimension = POSITION_DIMENSION_MAP[position][question.domain]
        raw = 50 + sum(item.score_delta for item in items)
        dimension_scores[dimension].append(max(0, min(100, raw)))
        evidence_items.extend(items)

    final_dims = {d: round(mean(s)) for d, s in dimension_scores.items()}
    overall    = round(sum(final_dims.values()) / len(final_dims))

    return EvaluationReport(
        overall=overall,
        dimensions=final_dims,
        evidence_chain=evidence_items,
        narrative=generate_narrative_from_evidence(evidence_items),  # single LLM call
    )
```

---

## 6. Integration with Existing Codebase

### New Backend Files

```
src/services/sep/
├── __init__.py
├── adaptive_selector.py       # Layer 1
├── feature_extractor.py       # Layer 2
├── evidence_builder.py        # Layer 3
├── rubric_engine.py           # rubric maps + score calculation
└── ability_estimator.py       # θ update algorithm

src/data/question_banks/
├── backend.json
├── frontend.json
└── algorithm.json
```

**Interview Agent hook**: add `adaptive_question_hook` in
`src/agents/interview_agent/` — called after each dialogue turn to select the
next question via `adaptive_selector.select_next_question()`.

**Score path priority in `interview_result_service.py`**:
SEP-generated structured scores take precedence; LLM scorecard extraction
(`_extract_scorecard()`) becomes fallback.

### New Frontend Components (`web/src/components/sep/`)

| Component | Purpose |
|-----------|---------|
| `EvidenceChain.vue` | Per-question evidence list with score deltas |
| `AdaptiveTrajectory.vue` | Line chart: question index × θ, point size = difficulty |
| `CognitiveTimeline.vue` | Heat-map bar: 8 features across all questions |

**Modified**: `InterviewResultView.vue` — insert the three components into the
evidence section, replacing the current plain progress-bar dimension display.

---

## 7. Demo Script (Competition Presentation)

1. Start interview → UI shows "System selecting question matched to your level"
2. Q1: medium difficulty (θ = 0.5)
3. Candidate answers well → θ rises to 0.68 → Q2 difficulty increases (live trajectory chart)
4. Q4: candidate makes a misconception → evidence item appears in real time: "−8: stated TCP uses four-way handshake to establish connection"
5. Interview ends → full evidence chain report, every point accounted for
6. **Key demo move**: swap underlying LLM to a different API, refresh report → scores unchanged, evidence chain unchanged

Step 6 is the direct proof of proprietary capability the judges are asking for.

---

## 8. Implementation Schedule (1–2 weeks)

| Day | Task | Output |
|-----|------|--------|
| 1 | Annotate question bank (3 positions × 20 questions) | `src/data/question_banks/` |
| 2 | `feature_extractor.py` + unit tests | Layer 2 core |
| 3 | `evidence_builder.py` + `rubric_engine.py` | Layer 3 core |
| 4 | `adaptive_selector.py` + `ability_estimator.py` | Layer 1 core |
| 5 | Integrate with Interview Agent, replace scoring path | Backend connected |
| 6–7 | `EvidenceChain.vue` + `AdaptiveTrajectory.vue` | Frontend visualization |
| 8 | End-to-end demo debug, LLM narrative prompt tuning | Demo-ready |
| 9–10 | Buffer / polish / competition materials | Submission-ready |

---

## 9. Risks

| Risk | Level | Mitigation |
|------|-------|-----------|
| Difficulty calibration inaccurate, adaptive effect weak | Medium | Use fixed sequence for demo, update θ silently in background |
| Keyword matching misses variants (Chinese tokenization) | Medium | Use `jieba` + synonym expansion table |
| Layer 2 false negatives (good answer scored low) | Low | Keep LLM scorecard as weighted fallback |
| SEP hook disrupts conversation SSE flow | Low | Call adaptive_hook async, non-blocking |

---

## 10. What Remains LLM-Dependent

- Question text naturalization (template → natural phrasing)
- Evidence-to-narrative translation (one call per report)
- Summary sentence generation

Everything else — question selection, feature extraction, scoring, evidence
building — is deterministic and model-independent.
