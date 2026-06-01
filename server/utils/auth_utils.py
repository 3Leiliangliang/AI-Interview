import hashlib
import logging
import os
from datetime import timedelta
from typing import Any

import jwt

from src.utils.datetime_utils import utc_now

logger = logging.getLogger(__name__)

# JWT配置
_raw_jwt_secret = os.environ.get("JWT_SECRET_KEY", "")
if not _raw_jwt_secret:
    logger.warning("JWT_SECRET_KEY not set — using derived default. Set a strong secret in production.")
    _raw_jwt_secret = "ai_interview_secure_key"
# Ensure the key is at least 32 bytes for HS256 by deriving via SHA-256 when too short
if len(_raw_jwt_secret.encode("utf-8")) < 32:
    _raw_jwt_secret = hashlib.sha256(_raw_jwt_secret.encode("utf-8")).hexdigest()
JWT_SECRET_KEY = _raw_jwt_secret
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION = 7 * 24 * 60 * 60  # 7天过期


class AuthUtils:
    """认证工具类"""

    @staticmethod
    def hash_password(password: str) -> str:
        """使用SHA-256哈希密码"""
        # 生成盐
        salt = os.urandom(32).hex()
        # 哈希密码
        hashed = hashlib.sha256((password + salt).encode()).hexdigest()
        # 返回格式: "哈希值:盐"
        return f"{hashed}:{salt}"

    @staticmethod
    def verify_password(stored_password: str, provided_password: str) -> bool:
        """验证密码"""
        # 分离哈希值和盐
        if ":" not in stored_password:
            return False

        hashed, salt = stored_password.split(":")

        # 使用相同的盐哈希提供的密码
        check_hash = hashlib.sha256((provided_password + salt).encode()).hexdigest()

        # 比较哈希值
        return hashed == check_hash

    @staticmethod
    def create_access_token(data: dict[str, Any], expires_delta: timedelta | None = None) -> str:
        """创建JWT访问令牌"""
        to_encode = data.copy()

        # 设置过期时间
        if expires_delta:
            expire = utc_now() + expires_delta
        else:
            expire = utc_now() + timedelta(seconds=JWT_EXPIRATION)

        to_encode.update({"exp": expire})

        # 编码JWT
        encoded_jwt = jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
        return encoded_jwt

    @staticmethod
    def decode_token(token: str) -> dict[str, Any] | None:
        """解码验证JWT令牌"""
        try:
            payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
            return payload
        except jwt.PyJWTError:
            return None

    @staticmethod
    def verify_access_token(token: str) -> dict[str, Any]:
        """验证访问令牌，如果无效则抛出异常"""
        try:
            payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
            return payload
        except jwt.ExpiredSignatureError:
            raise ValueError("令牌已过期")
        except jwt.InvalidTokenError:
            raise ValueError("无效的令牌")
