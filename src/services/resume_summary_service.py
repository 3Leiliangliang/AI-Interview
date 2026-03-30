"""简历结构化摘要服务 - 使用 LLM 提取简历关键信息。"""

import asyncio
import json
import re
from typing import Any

from src.agents.common.models import load_chat_model
from src.storage.postgres.manager import pg_manager
from src.storage.postgres.models_business import UserResume
from src.utils import logger
from src.utils.prompts import resume_extraction_prompt

# LLM 调用重试配置
MAX_RETRIES = 3
RETRY_DELAY = 2  # 秒
LLM_TIMEOUT = 120  # 秒

# 默认使用可靠模型进行摘要提取
DEFAULT_SUMMARY_MODEL = "siliconflow/Pro/deepseek-ai/DeepSeek-V3.2"


class ResumeSummaryService:
    """简历结构化摘要服务"""

    def __init__(self, model_name: str = DEFAULT_SUMMARY_MODEL) -> None:
        self.model_name = model_name

    async def extract_summary(self, markdown_content: str) -> dict[str, Any]:
        """
        调用 LLM 提取简历结构化信息，支持重试和超时。

        Args:
            markdown_content: 简历的 markdown 内容

        Returns:
            提取的结构化字典

        Raises:
            ValueError: 简历内容为空或提取失败
        """
        if not markdown_content or not markdown_content.strip():
            raise ValueError("简历内容为空，无法提取摘要")

        model = load_chat_model(self.model_name)
        prompt = resume_extraction_prompt.replace("{resume_text}", markdown_content)

        last_error = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                logger.info(f"LLM 提取尝试 {attempt}/{MAX_RETRIES}")
                response = await asyncio.wait_for(model.ainvoke(prompt), timeout=LLM_TIMEOUT)
                content = response.content if hasattr(response, "content") else str(response)

                logger.debug(f"LLM 原始响应长度: {len(content)} 字符")
                logger.debug(f"LLM 完整响应: {content}")

                # 尝试多种方式解析 JSON
                summary = self._parse_json_response(content)
                if summary:
                    logger.info("简历摘要提取成功")
                    return summary
                else:
                    # JSON 解析失败，LLM 已返回内容，重试可能得到不同结果
                    last_error = "JSON 解析失败"
                    logger.warning(f"第 {attempt} 次 JSON 解析失败，原始响应: {content[:500]}")
                    if attempt < MAX_RETRIES:
                        await asyncio.sleep(RETRY_DELAY)
                    continue

            except asyncio.TimeoutError:
                last_error = f"LLM 调用超时（{LLM_TIMEOUT}s）"
                logger.warning(f"第 {attempt} 次 LLM 调用超时")
                if attempt < MAX_RETRIES:
                    await asyncio.sleep(RETRY_DELAY)
            except (ConnectionError, OSError) as e:
                last_error = str(e)
                logger.warning(f"第 {attempt} 次 LLM 网络错误: {e}")
                if attempt < MAX_RETRIES:
                    await asyncio.sleep(RETRY_DELAY)
            except Exception as e:
                last_error = str(e)
                logger.error(f"简历摘要提取失败: {e}")
                # 不再继续重试，直接抛出
                raise ValueError(f"LLM 提取失败: {last_error}") from e

        raise ValueError(f"简历摘要提取失败（已重试 {MAX_RETRIES} 次）: {last_error}")

    def _preprocess_json_text(self, text: str) -> str:
        """
        预处理 JSON 文本，修复常见问题。
        """
        # 修复 LaTeX 公式残留（如 $10 \$ → 10%）
        text = re.sub(r"\$+([^$]*)\$+", lambda m: self._decode_latex_fragment(m.group(1)), text)

        # 修复换行符问题
        text = text.replace("\\n", "\n").replace("\n", " ")

        # 移除多余的控制字符
        text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]", "", text)

        return text

    def _decode_latex_fragment(self, latex: str) -> str:
        """
        解码 LaTeX 公式片段为正常文本。
        """
        if not latex:
            return ""

        # 百分比，如 10\% 或 10 % → 10%
        latex = re.sub(r"(\d+)\s*\\?%", r"\1%", latex)
        # 上标数字，如 ^ { 20 + } → 20+
        latex = re.sub(r"\^\s*\{\s*([\d\s\+]+)\s*\}", r"\1", latex)
        # 移除 \left \right 等 LaTeX 命令
        latex = re.sub(r"\\[a-zA-Z]+\s*", "", latex)
        # 清理多余空格
        latex = re.sub(r"\s+", " ", latex).strip()

        return latex

    def _parse_json_response(self, content: str) -> dict[str, Any] | None:
        """
        解析 LLM 返回的内容，尝试提取 JSON。

        支持多种格式：
        1. 直接是 JSON 对象
        2. markdown 代码块包裹的 JSON
        3. JSON 字符串
        4. 不完整 JSON 的容错解析
        """
        if not content:
            return None

        # 去除首尾空白
        content = content.strip()

        # 尝试 1: 直接解析（最常见情况）
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass

        # 尝试 2: 提取 markdown 代码块中的 JSON
        json_block_patterns = [
            r"```json\s*([\s\S]*?)\s*```",
            r"```\s*([\s\S]*?)\s*```",
        ]
        for pattern in json_block_patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                json_str = match.group(1).strip()
                try:
                    return json.loads(json_str)
                except json.JSONDecodeError:
                    continue

        # 尝试 3: 预处理后解析（修复 LaTeX 等问题）
        try:
            cleaned = self._preprocess_json_text(content)
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass

        # 尝试 4: 查找 JSON 对象模式
        json_pattern = r"\{[\s\S]*\}"
        match = re.search(json_pattern, content)
        if match:
            json_str = match.group(0)
            try:
                return json.loads(json_str)
            except json.JSONDecodeError:
                pass

            # 尝试修复常见的 JSON 问题
            try:
                fixed = self._fix_common_json_errors(json_str)
                return json.loads(fixed)
            except json.JSONDecodeError:
                pass

        # 尝试 5: 查找数组格式
        array_pattern = r"\[[\s\S]*\]"
        array_match = re.search(array_pattern, content)
        if array_match:
            json_str = array_match.group(0)
            try:
                return json.loads(json_str)
            except json.JSONDecodeError:
                pass

        # 尝试 6: 容错解析 - 查找关键字段后截取
        try:
            result = self._fallback_parse(content)
            if result:
                return result
        except Exception:
            pass

        return None

    def _fix_common_json_errors(self, json_str: str) -> str:
        """
        修复常见的 JSON 语法错误。
        """
        # 移除尾部逗号
        json_str = re.sub(r",(\s*[\]})])", r"\1", json_str)

        # 修复单引号为双引号（简单情况）
        # 注意：这个修复比较危险，禁用
        # json_str = re.sub(r"'([^']*)'", r'"\1"', json_str)

        # 移除 JavaScript 注释
        json_str = re.sub(r"//.*?$", "", json_str, flags=re.MULTILINE)

        # 修复 LaTeX 百分号
        json_str = re.sub(r"(\\?)%+", "%", json_str)

        # 修复换行
        json_str = re.sub(r"\\n", " ", json_str)

        return json_str

    def _fallback_parse(self, content: str) -> dict[str, Any] | None:
        """
        容错解析：从内容中提取已知的 JSON 字段。
        用于处理 LLM 返回不完整 JSON 的情况。
        """
        # 提取最外层的大括号内容
        first_brace = content.find("{")
        last_brace = content.rfind("}")

        if first_brace == -1 or last_brace == -1 or first_brace >= last_brace:
            return None

        truncated = content[first_brace : last_brace + 1]

        # 尝试解析
        try:
            return json.loads(truncated)
        except json.JSONDecodeError:
            pass

        # 尝试修复后解析
        fixed = self._fix_common_json_errors(truncated)
        try:
            return json.loads(fixed)
        except json.JSONDecodeError:
            pass

        # 尝试逐个字段解析
        result = {}
        field_patterns = {
            "basic_info": r'"basic_info"\s*:\s*(\{[^}]*\})',
            "education": r'"education"\s*:\s*(\[[^\]]*\])',
            "work_experience": r'"work_experience"\s*:\s*(\[[^\]]*\])',
            "project_experience": r'"project_experience"\s*:\s*(\[[^\]]*\])',
            "skills": r'"skills"\s*:\s*(\{[^}]*\})',
            "awards": r'"awards"\s*:\s*(\[[^\]]*\])',
        }

        for field, pattern in field_patterns.items():
            match = re.search(pattern, content, re.DOTALL)
            if match:
                try:
                    result[field] = json.loads(match.group(1))
                except json.JSONDecodeError:
                    # 尝试修复
                    fixed_field = self._fix_common_json_errors(match.group(1))
                    try:
                        result[field] = json.loads(fixed_field)
                    except json.JSONDecodeError:
                        pass

        if result:
            logger.info(f"使用容错解析提取了 {len(result)} 个字段")
            return result

        return None

    async def update_resume_summary(self, resume_id: int) -> bool:
        """
        更新指定简历的摘要信息。

        Args:
            resume_id: 简历记录 ID

        Returns:
            是否更新成功
        """
        async with pg_manager.get_async_session_context() as session:
            from sqlalchemy import select

            result = await session.execute(select(UserResume).where(UserResume.id == resume_id))
            resume = result.scalar_one_or_none()

            if not resume:
                logger.warning(f"简历不存在，ID: {resume_id}")
                return False

            # 更新状态为处理中
            resume.summary_status = "processing"
            await session.commit()

            try:
                markdown_content = resume.markdown_content or ""
                if not markdown_content.strip():
                    logger.warning(f"简历 markdown_content 为空，跳过提取，resume_id={resume_id}")
                    resume.summary_status = "failed"
                    resume.summary_error = "PDF 解析结果为空，无法提取摘要"
                    await session.commit()
                    return False

                summary = await self.extract_summary(markdown_content)

                if summary:
                    resume.summary_json = summary
                    resume.summary_status = "completed"
                    resume.summary_error = None

                    # 回填意向岗位
                    detected = summary.get("job_preference", {}).get("job_intention", "")
                    if detected and not resume.detected_position:
                        resume.detected_position = detected

                    logger.info(f"简历摘要更新成功，ID: {resume_id}")
                else:
                    resume.summary_status = "failed"
                    resume.summary_error = "LLM 提取返回空结果"
                    logger.warning(f"简历摘要提取返回空，ID: {resume_id}")

                await session.commit()
                return True

            except Exception as e:
                logger.error(f"更新简历摘要失败，ID: {resume_id}, 错误: {e}")
                resume.summary_status = "failed"
                resume.summary_error = str(e)
                await session.commit()
                return False


# 全局单例
resume_summary_service = ResumeSummaryService()
