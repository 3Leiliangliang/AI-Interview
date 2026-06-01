from __future__ import annotations

from dataclasses import dataclass

import jieba

STAR_KEYWORDS: dict[str, list[str]] = {
    "S": ["背景", "当时", "那时", "情况", "项目中", "在做", "工作中", "遇到", "有一次", "上一家"],
    "T": ["任务", "目标", "负责", "需要", "要求", "职责", "要做"],
    "A": ["我做了", "我采用", "我实现", "我设计", "我主导", "我负责", "我使用", "我开发", "我选择", "我提出"],
    "R": ["最终", "结果", "成功", "提升", "降低", "上线", "完成", "达到", "实现了", "解决了"],
}

HEDGE_WORDS = frozenset(
    [
        "可能",
        "也许",
        "大概",
        "应该",
        "不太确定",
        "我猜",
        "我觉得",
        "或许",
        "感觉",
        "好像",
        "差不多",
        "左右",
        "估计",
        "不确定",
        "不一定",
    ]
)


@dataclass
class AnswerFeatures:
    required_hit_rate: float
    bonus_hit_count: int
    misconception_count: int
    star_scores: dict[str, bool]
    hedge_ratio: float

    def to_answer_score(self) -> float:
        base = self.required_hit_rate
        bonus = min(0.2, self.bonus_hit_count * 0.05)
        star_bonus = sum(self.star_scores.values()) / 4 * 0.1
        penalty = min(0.3, self.misconception_count * 0.15)
        hedge_penalty = self.hedge_ratio * 0.1
        return max(0.0, min(1.0, base + bonus + star_bonus - penalty - hedge_penalty))


def extract_features(answer: str, rubric: dict) -> AnswerFeatures:
    if not answer or not answer.strip():
        return AnswerFeatures(
            required_hit_rate=0.0,
            bonus_hit_count=0,
            misconception_count=0,
            star_scores={"S": False, "T": False, "A": False, "R": False},
            hedge_ratio=0.0,
        )

    words = list(jieba.cut(answer))
    total_words = max(len(words), 1)

    required: list[str] = rubric.get("required", [])
    bonus: list[str] = rubric.get("bonus", [])
    misconceptions: list[str] = rubric.get("misconceptions", [])

    required_hits = sum(1 for kw in required if kw in answer)
    bonus_hits = sum(1 for kw in bonus if kw in answer)
    misconception_hits = sum(1 for kw in misconceptions if kw in answer)

    star_scores = {letter: any(kw in answer for kw in kws) for letter, kws in STAR_KEYWORDS.items()}

    hedge_count = sum(1 for w in words if w in HEDGE_WORDS)

    # When rubric has no required keywords (freeform / unmatched question),
    # required_hit_rate must be 0.0 — not 0.5 — to avoid systematically
    # inflating scores for answers that bear no relation to the question.
    return AnswerFeatures(
        required_hit_rate=required_hits / len(required) if required else 0.0,
        bonus_hit_count=bonus_hits,
        misconception_count=misconception_hits,
        star_scores=star_scores,
        hedge_ratio=hedge_count / total_words,
    )
