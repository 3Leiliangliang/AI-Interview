import os

from ..config import config
from .factory import KnowledgeBaseFactory
from .implementations.openviking import OpenVikingKB
from .manager import KnowledgeBaseManager

KnowledgeBaseFactory.register(
    "openviking",
    OpenVikingKB,
    {"description": "基于 OpenViking 的统一知识库，实现文档管理、索引与检索的一体化"},
)

work_dir = os.path.join(config.save_dir, "knowledge_base_data")
knowledge_base = KnowledgeBaseManager(work_dir)

__all__ = ["knowledge_base"]
