"""附件注入中间件。"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import NotRequired

from langchain.agents import AgentState
from langchain.agents.middleware import AgentMiddleware, ModelRequest, ModelResponse
from langchain_core.messages import SystemMessage

from src.utils import logger

ATTACHMENT_PROMPT_MARKER = "<!-- attachment_context -->"


class AttachmentState(AgentState):
    attachments: NotRequired[list[dict]]


def _build_attachment_prompt(attachments: Sequence[dict]) -> str | None:
    if not attachments:
        return None

    valid_attachments = [item for item in attachments if item.get("status") == "parsed"]
    if not valid_attachments:
        return None

    lines = ["用户上传了以下附件：", ""]
    for attachment in valid_attachments:
        file_name = attachment.get("file_name", "unknown")
        file_path = attachment.get("viking_path") or attachment.get("file_path", "")
        truncated = " (truncated)" if attachment.get("truncated") else ""
        if file_path:
            lines.append(f"- {file_name}{truncated}: {file_path}")
        else:
            lines.append(f"- {file_name}{truncated}")

    lines.extend(["", "请使用 read_file 读取上面列出的附件路径后，再回答用户问题。"])
    return "\n".join(lines)


class AttachmentMiddleware(AgentMiddleware[AttachmentState]):
    state_schema = AttachmentState

    async def awrap_model_call(
        self, request: ModelRequest, handler: Callable[[ModelRequest], ModelResponse]
    ) -> ModelResponse:
        attachments = request.state.get("attachments", [])
        logger.info(f"AttachmentMiddleware: found {len(attachments)} attachments in state")

        if attachments:
            attachment_prompt = _build_attachment_prompt(attachments)
            if attachment_prompt:
                logger.info("AttachmentMiddleware: injecting attachment prompt")
                existing_blocks = list(request.system_message.content_blocks) if request.system_message else []
                existing_text = "\n".join(
                    block.get("text", "")
                    for block in existing_blocks
                    if isinstance(block, dict) and block.get("type") == "text"
                )

                if ATTACHMENT_PROMPT_MARKER in existing_text:
                    logger.info("AttachmentMiddleware: attachment prompt already injected, skip")
                    return await handler(request)

                merged_blocks = existing_blocks + [
                    {"type": "text", "text": f"{ATTACHMENT_PROMPT_MARKER}\n{attachment_prompt}"}
                ]
                request = request.override(system_message=SystemMessage(content=merged_blocks))

        return await handler(request)


save_attachments_to_fs = AttachmentMiddleware()
inject_attachment_context = save_attachments_to_fs
