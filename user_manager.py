# ============================================
# 1. user_manager.py - 用户管理模块
# ============================================
"""
用户管理模块
支持用户注册、登录、第三方授权
"""

import hashlib
import secrets
import time
from typing import Dict, Optional, List
from dataclasses import dataclass, field
from enum import Enum


class AuthLevel(Enum):
    """授权级别"""
    OWNER = "owner"  # 设备所有者
    CONTROLLER = "controller"  # 可控制
    READONLY = "readonly"  # 只读


@dataclass
class User:
    """用户数据结构"""
    user_id: str
    username: str
    password_hash: str
    email: str
    created_at: float
    is_active: bool = True
    tokens: List[str] = field(default_factory=list)  # 第三方授权token


@dataclass
class ThirdPartyAuth:
    """第三方授权记录"""
    app_id: str
    app_name: str
    user_id: str
    scope: List[str]  # 授权范围
    token: str
    expires_at: float
    refresh_token: str


class UserManager:
    """用户管理器 - 支持注册、登录、第三方授权"""

    def __init__(self):
        self.users: Dict[str, User] = {}  # user_id -> User
        self.username_to_id: Dict[str, str] = {}  # username -> user_id
        self.third_party_auths: Dict[str, ThirdPartyAuth] = {}  # token -> auth
        self._init_default_users()

    def _init_default_users(self):
        """初始化默认用户（向后兼容）"""
        # 创建默认用户
        default_users = [
            ("user_001", "张三", "password123", "zhangsan@example.com"),
            ("user_002", "李四", "password456", "lisi@example.com"),
        ]
        for user_id, username, password, email in default_users:
            if user_id not in self.users:
                self.register(username, password, email, user_id)

    def register(self, username: str, password: str, email: str,
                 user_id: str = None) -> Optional[str]:
        """
        用户注册
        返回: user_id (成功) 或 None (失败)
        """
        # 检查用户名是否已存在
        if username in self.username_to_id:
            return None

        # 生成用户ID
        if user_id is None:
            user_id = f"user_{secrets.token_hex(4)}"

        # 密码哈希
        password_hash = hashlib.sha256(password.encode()).hexdigest()

        # 创建用户
        user = User(
            user_id=user_id,
            username=username,
            password_hash=password_hash,
            email=email,
            created_at=time.time()
        )

        self.users[user_id] = user
        self.username_to_id[username] = user_id

        print(f"[UserManager] 新用户注册: {username} ({user_id})")
        return user_id

    def login(self, username: str, password: str) -> Optional[str]:
        """
        用户登录
        返回: user_id (成功) 或 None (失败)
        """
        if username not in self.username_to_id:
            return None

        user_id = self.username_to_id[username]
        user = self.users[user_id]

        password_hash = hashlib.sha256(password.encode()).hexdigest()
        if user.password_hash == password_hash and user.is_active:
            print(f"[UserManager] 用户登录成功: {username}")
            return user_id

        return None

    def get_user(self, user_id: str) -> Optional[User]:
        """获取用户信息"""
        return self.users.get(user_id)

    def get_user_by_username(self, username: str) -> Optional[User]:
        """通过用户名获取用户"""
        if username not in self.username_to_id:
            return None
        return self.users[self.username_to_id[username]]

    def create_third_party_token(self, app_id: str, app_name: str,
                                 user_id: str, scope: List[str],
                                 expires_in: int = 3600) -> Optional[str]:
        """
        创建第三方授权token
        用于设备分享等场景
        """
        user = self.get_user(user_id)
        if not user:
            return None

        token = secrets.token_urlsafe(32)
        refresh_token = secrets.token_urlsafe(32)

        auth = ThirdPartyAuth(
            app_id=app_id,
            app_name=app_name,
            user_id=user_id,
            scope=scope,
            token=token,
            expires_at=time.time() + expires_in,
            refresh_token=refresh_token
        )

        self.third_party_auths[token] = auth
        user.tokens.append(token)

        print(f"[UserManager] 创建第三方授权: {app_name} -> {user_id}")
        return token

    def verify_third_party_token(self, token: str) -> Optional[ThirdPartyAuth]:
        """验证第三方授权token"""
        auth = self.third_party_auths.get(token)
        if not auth:
            return None

        if time.time() > auth.expires_at:
            # token过期
            del self.third_party_auths[token]
            return None

        return auth

    def revoke_third_party_token(self, user_id: str, token: str) -> bool:
        """撤销第三方授权token"""
        auth = self.third_party_auths.get(token)
        if auth and auth.user_id == user_id:
            del self.third_party_auths[token]
            user = self.get_user(user_id)
            if user and token in user.tokens:
                user.tokens.remove(token)
            return True
        return False

    def list_users(self) -> List[Dict]:
        """列出所有用户"""
        return [
            {
                "user_id": u.user_id,
                "username": u.username,
                "email": u.email,
                "created_at": u.created_at
            }
            for u in self.users.values()
        ]