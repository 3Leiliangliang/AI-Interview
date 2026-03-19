from deepagents.backends import StateBackend
from deepagents.middleware.filesystem import FilesystemMiddleware
from langchain.agents import create_agent
from langchain.agents.middleware import AgentMiddleware, ModelRetryMiddleware

from src.agents.common import BaseAgent, load_chat_model
from src.agents.common.middlewares import RuntimeConfigMiddleware, save_attachments_to_fs
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


def _create_interview_filesystem_middleware() -> FilesystemMiddleware:
    middleware = FilesystemMiddleware(
        backend=StateBackend,
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
    capabilities = ["file_upload", "files", "resume_interview"]

    async def get_graph(self, **kwargs):
        context = self.context_schema.from_file(module_name=self.module_name)

        return create_agent(
            model=load_chat_model(context.model),
            system_prompt=context.system_prompt,
            middleware=[
                save_attachments_to_fs,
                _create_interview_filesystem_middleware(),
                InterviewKnowledgeBaseMiddleware(),
                RuntimeConfigMiddleware(),
                ModelRetryMiddleware(),
            ],
            checkpointer=await self._get_checkpointer(),
        )
