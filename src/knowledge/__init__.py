import os

from ..config import config
from .factory import KnowledgeBaseFactory
from .implementations.milvus import MilvusKB
from .manager import KnowledgeBaseManager

KnowledgeBaseFactory.register("milvus", MilvusKB, {"description": "基于 Milvus 的生产级向量知识库，适合高性能部署"})

work_dir = os.path.join(config.save_dir, 'knowledge_base_data')
knowledge_base = KnowledgeBaseManager(work_dir)

__all__ = ['knowledge_base']
