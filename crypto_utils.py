# ============================================
# crypto_utils.py - 完整版本
# ============================================

import hashlib
import hmac
import time
import json
import secrets
from typing import Dict, Any, Tuple


class CryptoUtils:
    """加密工具类"""

    @staticmethod
    def generate_key() -> bytes:
        """生成随机密钥"""
        return secrets.token_bytes(32)

    @staticmethod
    def sign_message(seq_num: int, timestamp: float, payload: Dict, key: bytes) -> str:
        """生成HMAC-SHA256签名"""
        payload_str = json.dumps(payload, sort_keys=True)
        message = f"{seq_num}|{timestamp}|{payload_str}"
        signature = hmac.new(key, message.encode(), hashlib.sha256).hexdigest()
        return signature

    @staticmethod
    def verify_signature(seq_num: int, timestamp: float, payload: Dict,
                         signature: str, key: bytes) -> bool:
        """验证签名"""
        expected = CryptoUtils.sign_message(seq_num, timestamp, payload, key)
        return hmac.compare_digest(expected, signature)

    @staticmethod
    def hash_password(password: str, salt: str = None) -> Tuple[str, str]:
        """密码哈希"""
        if salt is None:
            salt = secrets.token_hex(16)
        password_hash = hashlib.pbkdf2_hmac(
            'sha256',
            password.encode(),
            salt.encode(),
            100000
        ).hex()
        return password_hash, salt

    @staticmethod
    def verify_password(password: str, password_hash: str, salt: str) -> bool:
        """验证密码"""
        computed_hash, _ = CryptoUtils.hash_password(password, salt)
        return hmac.compare_digest(computed_hash, password_hash)


# 全局配置
HMAC_KEY = b"smart-home-secret-key-2024"
TIME_WINDOW = 300  # 5分钟

# 序列号追踪器
_seq_num_tracker = {}


def check_timestamp(timestamp: float) -> bool:
    """检查时间戳是否在有效窗口内"""
    now = time.time()
    return abs(now - timestamp) <= TIME_WINDOW


def check_seq_num(device_id: str, user_id: str, seq_num: int) -> bool:
    """检查序列号是否递增（防重放）"""
    key = f"{device_id}:{user_id}"
    last_seq = _seq_num_tracker.get(key, -1)

    if seq_num > last_seq:
        _seq_num_tracker[key] = seq_num
        # 清理旧记录（保留最近1000条）
        if len(_seq_num_tracker) > 1000:
            keys_to_remove = list(_seq_num_tracker.keys())[:-500]
            for k in keys_to_remove:
                del _seq_num_tracker[k]
        return True
    return False


def get_last_seq_num(device_id: str, user_id: str) -> int:
    """获取最后的序列号"""
    key = f"{device_id}:{user_id}"
    return _seq_num_tracker.get(key, -1)


def reset_seq_num(device_id: str, user_id: str):
    """重置序列号（用于测试）"""
    key = f"{device_id}:{user_id}"
    if key in _seq_num_tracker:
        del _seq_num_tracker[key]