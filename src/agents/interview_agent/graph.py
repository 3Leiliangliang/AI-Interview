from deepagents.middleware.filesystem import FilesystemMiddleware
from deepagents.middleware.patch_tool_calls import PatchToolCallsMiddleware
from langchain.agents import create_agent
from langchain.agents.middleware import (
    AgentMiddleware,
    ModelRetryMiddleware,
    TodoListMiddleware,
    ToolCallLimitMiddleware,
)

from src.agents.common import BaseAgent, load_chat_model
from src.agents.common.backends import create_agent_composite_backend
from src.agents.common.middlewares import (
    OpenVikingContextMiddleware,
    OpenVikingSummaryMiddleware,
    RuntimeConfigMiddleware,
    VideoContextMiddleware,
    save_attachments_to_fs,
)
from src.agents.common.toolkits.interview.tools import start_code_assessment
from src.agents.common.toolkits.kbs.tools import (
    pick_random_technical_question,
    pick_sep_adaptive_question,
    query_kb,
)

from .context import InterviewContext

INTERVIEW_FILESYSTEM_PROMPT = """你只能使用 read_file 工具读取当前会话中已经提供的附件内容。
- 只允许读取系统已明确给出的附件 file_path。
- 不要为了找简历而遍历目录、搜索其他文件或读取无关路径。
- 如果当前没有可读附件，就直接提示用户上传简历，不要猜测路径。
"""

INTERVIEW_READ_FILE_DESCRIPTION = """读取当前会话中用户上传的简历或附件内容。
- 仅对系统已提供的附件 file_path 调用。
- 读取完成后再继续面试提问。
- 若没有附件可读，直接提示用户上传，不要读取无关文件。
"""

INTERVIEW_TODO_PROMPT = """## write_todos

你正在进行一场模拟面试。你必须始终维护固定的 6 个 todo，且只能通过 write_todos 更新整份列表。
固定任务必须始终保持以下 6 项，不能新增、删除、改名：
1. 发起开场并请候选人自我介绍
2. 追问项目经历与技术细节
3. 相关技术知识提问
4. 代码考核
5. 评估岗位匹配度与风险点
6. 输出总结与评分卡

任务状态只允许：pending / in_progress / completed

使用规则：
- 首轮正式发问前先初始化 6 条任务：第 1 条为 in_progress，其余为 pending。
- 开场问题发出后：第 1 条改为 completed，第 2 条改为 in_progress。
- 项目追问接近完成时：第 2 条改为 completed，第 3 条改为 in_progress。
- 第 3 阶段进行中：每次准备发出技术问题前，优先调用 pick_sep_adaptive_question
  （SEP 自适应选题，会基于候选人能力估计 θ 与领域覆盖率选信息量最大的题）。
  - 若返回的 question 为空字符串（SEP 题库耗尽或不可用），再降级调用
    pick_random_technical_question，并通过 excluded_questions 传入本阶段已问过的问题，避免重复。
  - 不要在用户面前展示工具返回的 sep_question_id；可以基于 question 文本做轻微润色，
    但要保留技术核心。
- 当你判断技术知识提问已足够时：先根据候选人前面的回答表现判断代码题难度（easy / medium / hard，拿不准用 medium），
  再调用 start_code_assessment，并把 difficulty_level 传进去；随后将第 3 条改为 completed，第 4 条改为 in_progress，
  并明确告知用户进入代码考核与工作台。
- 代码考核开始后，第 4 条保持 in_progress；在用户完成提交或明确表示结束代码考核后，
  将第 4 条改为 completed，第 5 条改为 in_progress。
- 继续交流岗位匹配度与风险点时，维护第 5 条状态；准备输出总结前，将第 5 条改为 completed，第 6 条改为 in_progress。
- 当用户要求“总结 / 评分 / 结束面试 / 给我反馈”时，先确保第 6 条为 in_progress；输出总结与评分卡后再改为 completed。
- 代码考核阶段，除非用户明确请求提示，否则不要主动点评代码或给出解法。
- 每轮回答最多调用一次 write_todos。
- 除这 6 条固定任务外，不要创建任何额外 todo。
"""


class InterviewKnowledgeBaseMiddleware(AgentMiddleware):
    def __init__(self):
        super().__init__()
        self.tools = [
            query_kb,
            pick_sep_adaptive_question,
            pick_random_technical_question,
            start_code_assessment,
        ]


def _create_interview_filesystem_middleware() -> FilesystemMiddleware:
    middleware = FilesystemMiddleware(
        backend=lambda rt: create_agent_composite_backend(rt, agent_id="InterviewAgent"),
        system_prompt=INTERVIEW_FILESYSTEM_PROMPT,
        custom_tool_descriptions={"read_file": INTERVIEW_READ_FILE_DESCRIPTION},
    )
    middleware.tools = [tool for tool in middleware.tools if getattr(tool, "name", "") == "read_file"]
    return middleware


class InterviewAgent(BaseAgent):
    name = "模拟面试官"
    description = "根据简历发起结构化模拟面试，并在结束后输出总结与评分卡。"
    has_checkpointer = True
    context_schema = InterviewContext
    capabilities = ["file_upload", "files", "resume_interview", "todo"]

    async def get_graph(self, **kwargs):
        context = self.context_schema.from_file(module_name=self.module_name)
        model = load_chat_model(context.model)

        return create_agent(
            model=model,
            system_prompt=context.system_prompt,
            middleware=[
                save_attachments_to_fs,
                _create_interview_filesystem_middleware(),
                InterviewKnowledgeBaseMiddleware(),
                RuntimeConfigMiddleware(),
                OpenVikingContextMiddleware(agent_id=self.id),
                VideoContextMiddleware(),
                TodoListMiddleware(system_prompt=INTERVIEW_TODO_PROMPT),
                PatchToolCallsMiddleware(),
                OpenVikingSummaryMiddleware(
                    model=model,
                    trigger=("tokens", 30000),
                    trim_tokens_to_summarize=2000,
                    max_retention_ratio=0.5,
                ),
                ToolCallLimitMiddleware(
                    tool_name="query_kb",
                    run_limit=1,
                    exit_behavior="continue",
                ),
                ModelRetryMiddleware(),
            ],
            checkpointer=await self._get_checkpointer(),
        )
