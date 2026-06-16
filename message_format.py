# ============================================
# message_format.py
# ============================================

from enum import Enum
from typing import Dict, Any, Optional
from dataclasses import dataclass
import json


class MessageType(Enum):
    """消息类型枚举"""
    # 设备相关
    DEVICE_REGISTER = "device_register"
    DEVICE_STATUS = "device_status"
    DEVICE_COMMAND = "device_command"
    DEVICE_COMMAND_RESPONSE = "device_command_response"
    
    # 用户相关
    USER_COMMAND = "user_command"
    USER_COMMAND_RESPONSE = "user_command_response"
    USER_LOGIN = "user_login"
    USER_LOGOUT = "user_logout"
    
    # 绑定相关
    BIND_DEVICE = "bind_device"
    UNBIND_DEVICE = "unbind_device"
    
    # 分享相关
    SHARE_DEVICE = "share_device"
    ACCEPT_SHARE = "accept_share"
    
    # 规则相关
    ADD_RULE = "add_rule"
    REMOVE_RULE = "remove_rule"
    
    # 心跳
    PING = "ping"
    PONG = "pong"


class ResponseCode(Enum):
    """响应码枚举"""
    SUCCESS = 200
    FAILURE = 400
    UNAUTHORIZED = 401
    FORBIDDEN = 403
    NOT_FOUND = 404
    CONFLICT = 409
    SERVER_ERROR = 500


@dataclass
class Message:
    """消息基类"""
    msg_id: str
    msg_type: MessageType
    timestamp: float
    sender: str
    receiver: str
    payload: Dict[str, Any]
    seq_num: int = 0
    signature: str = ""
    
    def to_json(self) -> str:
        """转换为JSON字符串"""
        data = {
            "msg_id": self.msg_id,
            "msg_type": self.msg_type.value,
            "timestamp": self.timestamp,
            "sender": self.sender,
            "receiver": self.receiver,
            "payload": self.payload,
            "seq_num": self.seq_num,
            "signature": self.signature
        }
        return json.dumps(data)
    
    @classmethod
    def from_json(cls, json_str: str):
        """从JSON字符串解析"""
        data = json.loads(json_str)
        return cls(
            msg_id=data["msg_id"],
            msg_type=MessageType(data["msg_type"]),
            timestamp=data["timestamp"],
            sender=data["sender"],
            receiver=data["receiver"],
            payload=data["payload"],
            seq_num=data.get("seq_num", 0),
            signature=data.get("signature", "")
        )


@dataclass
class DeviceRegisterMessage:
    """设备注册消息"""
    mac_address: str
    device_type: str
    product_key: str
    device_name: Optional[str] = None
    firmware_version: str = "1.0.0"
    
    def to_dict(self) -> Dict:
        return {
            "mac_address": self.mac_address,
            "device_type": self.device_type,
            "product_key": self.product_key,
            "device_name": self.device_name,
            "firmware_version": self.firmware_version
    }


@dataclass
class DeviceStatusMessage:
    """设备状态消息"""
    device_id: str
    status: str  # online, offline, busy
    properties: Dict[str, Any]
    timestamp: float
    
    def to_dict(self) -> Dict:
        return {
            "device_id": self.device_id,
            "status": self.status,
            "properties": self.properties,
            "timestamp": self.timestamp
        }


@dataclass
class DeviceCommandMessage:
    """设备命令消息"""
    device_id: str
    command: str
    params: Dict[str, Any]
    user_id: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return {
            "device_id": self.device_id,
            "command": self.command,
            "params": self.params,
            "user_id": self.user_id
        }


@dataclass
class UserCommandMessage:
    """用户命令消息"""
    user_id: str
    command_type: str
    params: Dict[str, Any]
    reply_topic: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return {
            "user_id": self.user_id,
            "type": self.command_type,
            "params": self.params,
            "reply_topic": self.reply_topic
        }


def create_response(success: bool, message: str, data: Dict = None) -> Dict:
    """创建标准响应"""
    return {
        "success": success,
        "message": message,
        "data": data or {},
        "timestamp": __import__('time').time()
    }



def create_bind_message(user_id: str, device_id: str) -> dict:
    """创建设备绑定消息"""
    import time
    return {
        "type": "bind_device",
        "user_id": user_id,
        "params": {"device_id": device_id},
        "reply_topic": "user/response",
        "timestamp": time.time()
    }

def create_unbind_message(user_id: str, device_id: str) -> dict:
    """创建设备解绑消息"""
    import time
    return {
        "type": "unbind_device",
        "user_id": user_id,
        "params": {"device_id": device_id},
        "reply_topic": "user/response",
        "timestamp": time.time()
    }

def create_control_message(user_id: str, device_id: str, command: str, params: dict = None) -> dict:
    """创建设备控制消息"""
    import time
    return {
        "type": "control_device",
        "user_id": user_id,
        "params": {
            "device_id": device_id,
            "command": command,
            "params": params or {}
        },
        "reply_topic": "user/response",
        "timestamp": time.time()
    }

def create_get_status_message(user_id: str, device_id: str = None) -> dict:
    """创建设备状态查询消息"""
    import time
    return {
        "type": "get_status",
        "user_id": user_id,
        "params": {"device_id": device_id} if device_id else {},
        "reply_topic": "user/response",
        "timestamp": time.time()
    }