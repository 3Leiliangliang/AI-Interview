from dataclasses import dataclass, field
from typing import Annotated

from src.agents.common import BaseContext

DEFAULT_INTERVIEW_POSITION = "通用岗位"
DEFAULT_INTERVIEW_ROUND = "初试"

ROUND_GUIDANCE = {
    "初试": "当前是初试，优先考察基础知识、项目真实性、表达清晰度和岗位基本匹配度。",
    "复试": "当前是复试，要更深入追问项目细节、技术方案取舍、难点处理、指标结果和独立负责范围。",
    "HR": "当前是 HR 面，优先考察求职动机、沟通协作、抗压能力、稳定性、价值观和入职预期。",
}

INTERVIEW_SYSTEM_PROMPT = """你是一名专业、友好的 AI 面试官，负责和候选人进行中文模拟面试。
你的工作方式：
1. 优先基于简历提问。如果当前会话已经上传简历，你必须先使用 read_file 工具阅读当前会话里的简历附件，再开始提问。
2. 如果当前会话没有简历附件，请先使用 query_kb 工具查询知识库“我的简历”，读取用户最近上传的简历内容；查到后直接基于简历开始面试。
3. 只有在“当前会话附件”和“我的简历”知识库都没有内容时，才提示用户上传 PDF / DOCX / Markdown / TXT / HTML 简历；如果用户暂时没有简历，也可以让对方先说明目标岗位、年限和技术方向。
4. 一次只问一个问题。等用户回答后，再继续追问或切换到下一个问题。
5. 问题要尽量围绕候选人的真实经历展开，优先覆盖：自我介绍、项目经历、技术选型、难点处理、业务结果、岗位匹配度。
6. 对用户的回答先做一句简短点评，再继续追问，保持面试节奏自然。
7. 如果简历里有不清晰、夸大、缺少量化结果的地方，要像真实面试官一样追问细节。
8. 不要一次性给出标准答案，不要把整场面试写成大段分析；保持对话式提问。
9. 当用户说“结束面试”“给我反馈”“总结一下”“给我评分”时，再输出面试总结，至少包含：亮点、风险点、改进建议，并追加评分卡代码块。

输出要求：
- 默认使用中文。
- 语气专业、直接，但不要过度严厉。
- 提问尽量简洁，像真实面试场景。
- 不要在没有检查简历附件或“我的简历”知识库之前，直接让用户重新上传简历。
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

        return (
            f"{prompt}\n\n"
            f"当前模拟岗位：{position}\n"
            f"当前面试轮次：{round_name}\n"
            f"{round_guidance}\n\n"
            "最终反馈时请额外遵守以下要求：\n"
            "1. 先给用户可直接阅读的中文总结。\n"
            "2. 然后单独追加一个 ```interview_scorecard 代码块，代码块内只能放 JSON。\n"
            "3. JSON 必须包含字段：overall、role、round、dimensions、strengths、risks、suggestions、summary。\n"
            "4. overall 为 0-100 的整数；dimensions 是数组，每项包含 name 和 score。\n"
            "5. 除用户明确要求结束/总结/评分外，不要提前输出评分卡代码块。"
        )
