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
    save_attachments_to_fs,
)
from src.agents.common.toolkits.kbs.tools import query_kb

from .context import InterviewContext

INTERVIEW_FILESYSTEM_PROMPT = """你只能使用 read_file 工具读取当前会话里已经给出的附件内容。
- 只读取系统提示中明确列出的附件 file_path。
- 不要为了找简历执行目录遍历、文件搜索或查看无关路径。
- 如果当前没有可读的附件路径，就直接提醒用户上传简历，不要做额外步骤。
"""

INTERVIEW_READ_FILE_DESCRIPTION = """读取用户在当前会话中上传的简历或附件内容。

使用规则：
- 只对系统提示中已经给出的附件 file_path 调用这个工具。
- 读取完简历后再发起面试提问。
- 如果没有可用的附件路径，就直接提醒用户上传简历，不要猜测路径或读取无关文件。
"""

INTERVIEW_TODO_PROMPT = """## `write_todos`

你正在进行一场模拟面试。每一轮面试都必须维护一份固定的 5 步任务清单，并通过 `write_todos` 工具更新整份列表。

固定任务必须始终保持为以下 5 项，不要新增、删除、改名，也不要扩展成更多步骤：
1. 读取简历并确认岗位背景
2. 发起开场并请候选人自我介绍
3. 追问项目经历与技术细节
4. 评估岗位匹配度与风险点
5. 输出总结与评分卡

任务状态只允许使用：
- pending
- in_progress
- completed

使用规则：
- 首轮真正发问前先初始化 5 条任务：第 1 条为 in_progress，其余为 pending。
- 简历读取成功后：第 1 条改为 completed，第 2 条改为 in_progress。
- 第一问已经发出后：第 2 条改为 completed，第 3 条改为 in_progress。
- 面试进行中：根据对话进度推进第 3、4 条任务状态，但始终保持总任务数为 5。
- 当用户要求“结束面试 / 总结 / 评分 / 给我反馈”时：先将第 5 条标记为 in_progress，输出总结和评分卡后再标记为 completed。
- 每轮回答最多调用一次 `write_todos`，避免重复刷新。
- 除这 5 条固定任务外，不要创建任何额外 todo。
"""


def _create_interview_filesystem_middleware() -> FilesystemMiddleware:
    middleware = FilesystemMiddleware(
        backend=lambda rt: create_agent_composite_backend(rt, agent_id="InterviewAgent"),
        system_prompt=INTERVIEW_FILESYSTEM_PROMPT,
        custom_tool_descriptions={"read_file": INTERVIEW_READ_FILE_DESCRIPTION},
    )
    middleware.tools = [tool for tool in middleware.tools if getattr(tool, "name", "") == "read_file"]
    return middleware


class InterviewKnowledgeBaseMiddleware(AgentMiddleware):
    def __init__(self):
        super().__init__()
        self.tools = [query_kb]


class InterviewAgent(BaseAgent):
    name = "模拟面试官"
    description = "根据你上传的简历逐题发起模拟面试，并在结束后给出反馈。"
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
