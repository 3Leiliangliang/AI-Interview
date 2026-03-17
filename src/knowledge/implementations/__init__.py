"""知识库具体实现模块

包含各种知识库的具体实现：
- MilvusKB: 基于 Milvus 的向量知识库
"""

from .milvus import MilvusKB

__all__ = ["MilvusKB"]
