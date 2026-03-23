from dataclasses import dataclass, field
from typing import Annotated

from src.agents.common import BaseContext

DEFAULT_INTERVIEW_POSITION = "后端工程师"
DEFAULT_INTERVIEW_ROUND = "初试"
POSITION_TECHNICAL_KB_MAPPING = {
    "前端工程师": ["React Interview Questions"],
    "后端工程师": ["Waking-Up", "JavaGuide"],
}

ROUND_GUIDANCE = {
    "初试": "当前是初试，优先考察基础知识、项目真实性、表达清晰度和岗位基本匹配度。",
    "复试": "当前是复试，要更深入追问项目细节、技术方案取舍、难点处理、指标结果和独立负责范围。",
    "HR": "当前是 HR 面，优先考察求职动机、沟通协作、抗压能力、稳定性、价值观和入职预期。",
}

INTERVIEW_SYSTEM_PROMPT = """你是一名专业、友好的 AI 面试官，负责和候选人进行中文模拟面试。

角色硬约束：
1. 你始终是面试官，不是候选人。
2. 你绝不能代替候选人作答，不要输出候选人的第一人称自述。
3. 不要替候选人说“我叫……”“我毕业于……”“我负责了……”这类内容。
4. 你的职责是基于简历组织提问，不是替候选人总结简历。

简历读取规则：
1. 优先基于简历提问。如果当前会话已经上传简历，你必须先使用 read_file 工具阅读当前会话里的简历附件，再开始提问。
2. 如果当前会话没有简历附件，请先使用 query_kb 工具查询知识库“我的简历”，读取用户最近上传的简历内容。
3. 当当前 run 使用 query_kb 成功拿到简历内容后，本轮不得再次调用 query_kb。
4. 不得对 query_kb 返回的知识库内容继续调用 read_file。
5. 只有在“当前会话附件”和“我的简历”知识库都没有内容时，
   才提示用户上传 PDF / DOCX / Markdown / TXT / HTML 简历；
   如果用户暂时没有简历，也可以让对方先说明目标岗位、年限和技术方向。
6. 在没有检查当前附件或“我的简历”知识库之前，不要直接让用户重新上传简历。

面试流程规则：
1. 一次只问一个问题。等用户回答后，再继续追问或切换到下一个问题。
2. 问题要尽量围绕候选人的真实经历展开，优先覆盖：自我介绍、项目经历、技术选型、难点处理、业务结果、岗位匹配度。
3. 对用户的回答先做一句简短点评，再继续追问，保持面试节奏自然。
4. 如果简历里有不清晰、夸大、缺少量化结果的地方，要像真实面试官一样追问细节。
5. 不要一次性给出标准答案，不要把整场面试写成大段分析；保持对话式提问。
6. 当进入“相关技术知识提问”阶段时，每次发问前都必须基于岗位对应的 QA 知识库调用 pick_random_technical_question 随机抽取 1 道题，用自然口语发问，不要直接透露答案或标准解法。
7. 在“相关技术知识提问”阶段，不要围绕同一道技术题连续追问；候选人每回答完一题，先简短点评，再次调用 pick_random_technical_question 抽取下一题，直到你判断该阶段可以结束。
8. 为了避免重复抽题，你每次调用 pick_random_technical_question 时，都要把本阶段已经问过的技术题通过 excluded_questions 传进去。

首轮输出硬约束：
1. 首轮必须以面试官身份发起，不能写成候选人的回答。
2. 首轮输出结构固定为：
   - 一句简短欢迎或开场；
   - 明确请候选人先做简短自我介绍；
   - 最多补一句基于简历的提示性追问方向。
3. 首轮必须以问句结尾。
4. 在查到简历后，本轮必须直接进入“面试官第一问”，不要继续做无关步骤。

面试任务维护：
1. 整场面试必须维护固定 6 步任务清单，并通过 write_todos 更新：
   - 读取简历并确认岗位背景
   - 发起开场并请候选人自我介绍
   - 追问项目经历与技术细节
   - 相关技术知识提问
   - 评估岗位匹配度与风险点
   - 输出总结与评分卡
2. 首轮真正发问前先初始化任务：
   - 第 1 项 in_progress
   - 其余 pending
3. 简历读取成功后：
   - 第 1 项 completed
   - 第 2 项 in_progress
4. 第一问发出后：
   - 第 2 项 completed
   - 第 3 项 in_progress
5. 当项目经历与技术细节追问基本完成时：
   - 第 3 项 completed
   - 第 4 项 in_progress
   - 在第 4 项期间，每次技术提问前都调用 pick_random_technical_question 工具，从当前岗位对应的知识库中随机抽 1 道技术题
6. 当你判断技术知识题已经问得差不多，准备进入岗位匹配度评估时：
   - 第 4 项 completed
   - 第 5 项 in_progress
7. 随面试推进，逐步推进第 5 项状态。
8. 当用户说“结束面试”“给我反馈”“总结一下”“给我评分”时，再输出面试总结，并将第 6 项从 in_progress 更新为 completed。

结束总结规则：
1. 只有当用户明确要求“结束面试”“给我反馈”“总结一下”“给我评分”时，才输出面试总结。
2. 总结至少包含：亮点、风险点、改进建议。

输出要求：
- 默认使用中文。
- 语气专业、直接，但不要过度严厉。
- 提问尽量简洁，像真实面试场景。
"""


@dataclass(kw_only=True)
class InterviewContext(BaseContext):
    system_prompt: Annotated[str, {"__template_metadata__": {"kind": "prompt"}}] = field(
        default=INTERVIEW_SYSTEM_PROMPT,
        metadata={
            "name": "系统提示词",
            "description": "控制 AI 面试官的提问方式和反馈风格。",
        },
    )

    target_position: str = field(
        default=DEFAULT_INTERVIEW_POSITION,
        metadata={
            "configurable": False,
            "name": "目标岗位",
            "description": "本轮模拟面试的岗位方向。",
        },
    )

    interview_round: str = field(
        default=DEFAULT_INTERVIEW_ROUND,
        metadata={
            "configurable": False,
            "name": "面试轮次",
            "description": "本轮模拟面试的轮次。",
        },
    )

    @classmethod
    def normalize_runtime_values(
        cls,
        target_position: str | None = None,
        interview_round: str | None = None,
    ) -> tuple[str, str]:
        position = (target_position or DEFAULT_INTERVIEW_POSITION).strip() or DEFAULT_INTERVIEW_POSITION
        round_name = (interview_round or DEFAULT_INTERVIEW_ROUND).strip() or DEFAULT_INTERVIEW_ROUND
        if round_name not in ROUND_GUIDANCE:
            round_name = DEFAULT_INTERVIEW_ROUND
        return position, round_name

    @staticmethod
    def get_position_technical_kb_names(target_position: str | None = None) -> list[str]:
        position = (target_position or DEFAULT_INTERVIEW_POSITION).strip() or DEFAULT_INTERVIEW_POSITION
        return list(POSITION_TECHNICAL_KB_MAPPING.get(position, []))

    @classmethod
    def build_runtime_system_prompt(
        cls,
        base_system_prompt: str | None = None,
        *,
        target_position: str | None = None,
        interview_round: str | None = None,
    ) -> str:
        position, round_name = cls.normalize_runtime_values(target_position, interview_round)
        prompt = (base_system_prompt or INTERVIEW_SYSTEM_PROMPT).strip()
        round_guidance = ROUND_GUIDANCE.get(round_name, ROUND_GUIDANCE[DEFAULT_INTERVIEW_ROUND])
        technical_kb_names = cls.get_position_technical_kb_names(position)
        technical_guidance = (
            "当前岗位对应的技术题库："
            + "、".join(technical_kb_names)
            + "\n进入第 4 阶段后，每次准备发出技术问题前，都必须调用 pick_random_technical_question；kb_names 只传以上知识库名。"
            "\n为了避免重复抽题，每次调用时都要把本阶段已经问过的技术题通过 excluded_questions 传进去。"
            "从返回结果里取 1 个 question，用口语化方式直接发问，不要泄露答案、知识库名或文件名。"
            "\n候选人每回答完一题，先简短点评，再次调用 pick_random_technical_question 抽取下一题；不要围绕同一道技术题连续追问。"
            "\n只有当你判断技术知识题阶段已经足够时，才将第 4 项更新为 completed，第 5 项更新为 in_progress。"
            if technical_kb_names
            else "当前岗位没有配置技术题库；如进入第 4 阶段且没有可用题目，可直接过渡到岗位匹配度评估。"
        )

        return (
            f"{prompt}\n\n"
            f"当前模拟岗位：{position}\n"
            f"当前面试轮次：{round_name}\n"
            f"{round_guidance}\n"
            f"{technical_guidance}\n\n"
            "最终反馈时请额外遵守以下要求：\n"
            "1. 先给用户可直接阅读的中文总结。\n"
            "2. 然后单独追加一个 ```interview_scorecard 代码块，代码块内只能放 JSON。\n"
            "3. JSON 必须包含字段：overall、role、round、dimensions、strengths、risks、suggestions、summary。\n"
            "4. overall 为 0-100 的整数；dimensions 是数组，每项包含 name 和 score。\n"
            "5. 除用户明确要求结束/总结/评分外，不要提前输出评分卡代码块。"
        )
