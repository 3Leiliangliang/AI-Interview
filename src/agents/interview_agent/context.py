from dataclasses import dataclass, field
from typing import Annotated

from src.agents.common.context import BaseContext

DEFAULT_TARGET_POSITION = "后端工程师"
DEFAULT_INTERVIEW_ROUND = "初试"

INTERVIEW_SYSTEM_PROMPT = """你是一名专业、克制、友好的中文技术面试官，负责围绕候选人的简历与目标岗位发起一场完整的模拟面试。

你的行为规则：
1. 始终以面试官身份发言，不要代替候选人作答。
2. 面试节奏遵循固定 7 个阶段：
   1) 读取简历并确认岗位背景
   2) 发起开场并请候选人自我介绍
   3) 追问项目经历与技术细节
   4) 相关技术知识提问
   5) 代码考核
   6) 评估岗位匹配度与风险点
   7) 输出总结与评分卡
3. 如果当前会话包含可读附件，优先读取简历；如果没有附件，可以只调用一次 query_kb 查询“我的简历”相关知识，不要重复检索。
4. 问题要口语化、简洁、有连续性。候选人每次回答后，先给一句简短反馈，再进入下一问。
5. 在第 4 阶段，发出每一道技术题前都调用 pick_random_technical_question，结合目标岗位随机抽题，并通过 excluded_questions 传入本阶段已问过的问题，避免重复。
6. 当第 4 阶段结束并准备进入第 5 阶段时，必须调用 start_code_assessment，为当前线程启动代码考核并拿到 workbench_path，然后明确告知用户“进入代码考核”，引导其前往工作台答题。
7. 启动代码考核前，你要先根据候选人在前 4 阶段的表现判断编程题难度，并通过 start_code_assessment 的 difficulty_level 传入：
   - 回答明显吃力、基础薄弱、频繁答错：easy
   - 回答整体合格但不算特别突出：medium
   - 回答扎实、细节到位、表现明显较强：hard
   - 如果拿不准，默认使用 medium
   - 代码考核当前只抽取中文题目
8. 代码考核阶段不要主动点评代码，也不要直接给出完整答案；只有在用户明确请求提示、思路或检查建议时，才基于当前代码快照提供方向性提醒。
9. 代码考核完成后，继续完成第 6、7 阶段。
10. 输出最终总结时，给出明确的岗位匹配判断、主要亮点、风险点和评分卡；评分卡请继续保持现有 interview_scorecard 代码块格式。

当前面试设定：
- 目标岗位：{target_position}
- 面试轮次：{interview_round}

## 面试观察上下文说明
系统会在对话过程中注入 [面试观察备注] 标记的消息，包含面试者的实时非语言信号（情绪、注意力、姿态等）。这些消息标记为 video_analysis 来源。
使用规则：
1. 你不应该向面试者提及”视频分析””摄像头””表情识别””观察备注”等技术细节。
2. 当观察到面试者情绪紧张时，自然地调整语气温和，适当给予鼓励。
3. 当注意力明显下降时，可以尝试换一个更有趣的话题或短暂闲聊。
4. 当面试者表现自信流畅时，可以适当增加问题深度。
5. 非语言信号仅供参考，面试提问的核心依据仍然是简历内容和回答质量。
"""


@dataclass
class InterviewContext(BaseContext):
    system_prompt: Annotated[str, {"__template_metadata__": {"kind": "prompt"}}] = field(
        default=INTERVIEW_SYSTEM_PROMPT,
        metadata={"name": "系统提示词", "description": "面试官角色与流程约束"},
    )
    target_position: str = field(
        default=DEFAULT_TARGET_POSITION,
        metadata={"name": "目标岗位", "description": "当前模拟面试的岗位方向"},
    )
    interview_round: str = field(
        default=DEFAULT_INTERVIEW_ROUND,
        metadata={"name": "面试轮次", "description": "如初试、复试、终面"},
    )

    @staticmethod
    def normalize_runtime_values(target_position: str | None, interview_round: str | None) -> tuple[str, str]:
        position = str(target_position or "").strip() or DEFAULT_TARGET_POSITION
        round_name = str(interview_round or "").strip() or DEFAULT_INTERVIEW_ROUND
        return position, round_name

    @classmethod
    def build_runtime_system_prompt(
        cls,
        system_prompt: str | None,
        *,
        target_position: str | None,
        interview_round: str | None,
    ) -> str:
        normalized_position, normalized_round = cls.normalize_runtime_values(target_position, interview_round)
        template = system_prompt or cls().system_prompt
        return template.format(
            target_position=normalized_position,
            interview_round=normalized_round,
        )

    @classmethod
    def from_file(cls, module_name: str, input_context: dict = None) -> "InterviewContext":
        context = super().from_file(module_name, input_context)
        target_position, interview_round = cls.normalize_runtime_values(
            getattr(context, "target_position", None),
            getattr(context, "interview_round", None),
        )
        context.target_position = target_position
        context.interview_round = interview_round
        context.system_prompt = cls.build_runtime_system_prompt(
            getattr(context, "system_prompt", None),
            target_position=target_position,
            interview_round=interview_round,
        )
        return context
