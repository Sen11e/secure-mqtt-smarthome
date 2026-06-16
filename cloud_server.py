# ============================================
# cloud_server.py - 简化可运行版本
# ============================================

import json
import time
import secrets
from typing import Dict, Any

import paho.mqtt.client as mqtt

# 导入修复后的模块
from crypto_utils import CryptoUtils, check_timestamp, check_seq_num
from message_format import Message, MessageType, ResponseCode

# 配置
BROKER_HOST = "localhost"
BROKER_PORT = 1883

TOPICS = {
    "device_command": "device/command",
    "device_status": "device/status",
    "device_register": "device/register",
    "user_command": "user/command",
    "user_command_response": "user/response",
}


class CloudServer:
    """云端服务器"""

    def __init__(self):
        # 绑定关系
        self.device_users: Dict[str, str] = {}  # device_id -> user_id
        self.user_devices: Dict[str, list] = {}  # user_id -> [device_ids]

        # 设备状态
        self.device_states: Dict[str, Dict] = {}

        # 密钥
        self.device_keys: Dict[str, bytes] = {}
        self.user_keys: Dict[str, bytes] = {}

        # MQTT客户端
        self.mqtt_client = mqtt.Client()
        self.setup_mqtt_callbacks()

        # 初始化
        self._init_defaults()

    def _init_defaults(self):
        """初始化默认数据"""
        # 默认设备
        default_devices = ["ac_001", "lb_001", "ss_001"]
        for device_id in default_devices:
            self.device_keys[device_id] = secrets.token_bytes(32)
            self.device_states[device_id] = {"status": "offline", "properties": {}}

        # 默认用户
        default_users = ["user_001", "user_002"]
        for user_id in default_users:
            self.user_keys[user_id] = secrets.token_bytes(32)
            self.user_devices[user_id] = []

        # 默认绑定
        bindings = [
            ("user_001", "ac_001"),
            ("user_001", "lb_001"),
            ("user_002", "ss_001"),
        ]
        for user_id, device_id in bindings:
            self.device_users[device_id] = user_id
            self.user_devices[user_id].append(device_id)

        print("[Cloud] 初始化完成")
        print(f"  设备: {default_devices}")
        print(f"  用户: {default_users}")
        print(f"  绑定: {bindings}")

    def setup_mqtt_callbacks(self):
        """设置MQTT回调"""
        self.mqtt_client.on_connect = self.on_connect
        self.mqtt_client.on_message = self.on_message

    def on_connect(self, client, userdata, flags, rc):
        """连接成功回调"""
        if rc == 0:
            print("[Cloud] ✅ 已连接到MQTT Broker")
            # 订阅主题
            self.mqtt_client.subscribe(TOPICS["device_status"])
            self.mqtt_client.subscribe(TOPICS["device_register"])
            self.mqtt_client.subscribe(TOPICS["user_command"])
            print(f"[Cloud] 已订阅: {list(TOPICS.values())}")
        else:
            print(f"[Cloud] ❌ 连接失败，错误码: {rc}")

    def on_message(self, client, userdata, msg):
        """消息处理回调"""
        try:
            payload = json.loads(msg.payload.decode())
            print(f"[Cloud] 收到消息 [{msg.topic}]: {payload}")

            if msg.topic == TOPICS["device_status"]:
                self.handle_device_status(payload)
            elif msg.topic == TOPICS["device_register"]:
                self.handle_device_register(payload)
            elif msg.topic == TOPICS["user_command"]:
                self.handle_user_command(payload)

        except json.JSONDecodeError:
            print(f"[Cloud] ❌ JSON解析失败: {msg.payload}")
        except Exception as e:
            print(f"[Cloud] ❌ 处理消息异常: {e}")

    def handle_device_status(self, payload: Dict):
        """处理设备状态上报"""
        device_id = payload.get("device_id")
        status = payload.get("status", "unknown")
        properties = payload.get("properties", {})

        if device_id in self.device_states:
            self.device_states[device_id] = {
                "status": status,
                "properties": properties,
                "timestamp": time.time()
            }
            print(f"[Cloud] 📊 设备状态更新: {device_id} = {status}, {properties}")
        else:
            print(f"[Cloud] ⚠️ 未知设备: {device_id}")

    def handle_device_register(self, payload: Dict):
        """处理设备注册"""
        device_id = payload.get("device_id")
        device_type = payload.get("device_type")
        mac = payload.get("mac")

        if device_id not in self.device_keys:
            # 新设备注册
            self.device_keys[device_id] = secrets.token_bytes(32)
            self.device_states[device_id] = {"status": "registered", "properties": {}}
            print(f"[Cloud] 📱 新设备注册: {device_id} ({device_type}), MAC: {mac}")

            response = {
                "success": True,
                "device_id": device_id,
                "message": "注册成功",
                "device_secret": self.device_keys[device_id].hex()
            }
        else:
            # 已注册设备重新上线
            print(f"[Cloud] 🔄 设备重新上线: {device_id}")
            response = {
                "success": True,
                "device_id": device_id,
                "message": "设备已注册"
            }

        # 回复设备
        self.mqtt_client.publish(
            f"device/{device_id}/register_response",
            json.dumps(response)
        )

    def handle_user_command(self, payload: Dict):
        """处理用户命令"""
        cmd_type = payload.get("type")
        user_id = payload.get("user_id")

        print(f"[Cloud] 👤 用户命令: {user_id} -> {cmd_type}")

        if cmd_type == "bind_device":
            self.handle_bind_device(payload)
        elif cmd_type == "unbind_device":
            self.handle_unbind_device(payload)
        elif cmd_type == "get_devices":
            self.handle_get_devices(payload)
        elif cmd_type == "control_device":
            self.handle_control_device(payload)
        elif cmd_type == "get_status":
            self.handle_get_status(payload)
        else:
            self.send_response(payload, False, f"未知命令: {cmd_type}")

    def handle_bind_device(self, payload: Dict):
        """绑定设备"""
        user_id = payload.get("user_id")
        device_id = payload.get("device_id")

        # 检查设备是否存在
        if device_id not in self.device_keys:
            self.send_response(payload, False, "设备不存在")
            return

        # 检查设备是否已被绑定
        if device_id in self.device_users:
            current_user = self.device_users[device_id]
            if current_user == user_id:
                self.send_response(payload, False, "设备已绑定到当前用户")
            else:
                self.send_response(payload, False, f"设备已被用户 {current_user} 绑定")
            return

        # 绑定设备
        self.device_users[device_id] = user_id
        if user_id not in self.user_devices:
            self.user_devices[user_id] = []
        if device_id not in self.user_devices[user_id]:
            self.user_devices[user_id].append(device_id)

        print(f"[Cloud] 🔗 设备绑定: {user_id} -> {device_id}")
        self.send_response(payload, True, "绑定成功", {"device_id": device_id})

    def handle_unbind_device(self, payload: Dict):
        """解绑设备"""
        user_id = payload.get("user_id")
        device_id = payload.get("device_id")

        if self.device_users.get(device_id) == user_id:
            del self.device_users[device_id]
            if user_id in self.user_devices and device_id in self.user_devices[user_id]:
                self.user_devices[user_id].remove(device_id)

            print(f"[Cloud] 🔓 设备解绑: {user_id} -> {device_id}")
            self.send_response(payload, True, "解绑成功")
        else:
            self.send_response(payload, False, "无权解绑此设备")

    def handle_get_devices(self, payload: Dict):
        """获取用户设备列表"""
        user_id = payload.get("user_id")
        devices = self.user_devices.get(user_id, [])

        # 获取设备详细信息
        device_list = []
        for device_id in devices:
            device_list.append({
                "device_id": device_id,
                "status": self.device_states.get(device_id, {}).get("status", "unknown"),
                "properties": self.device_states.get(device_id, {}).get("properties", {})
            })

        self.send_response(payload, True, "获取成功", {"devices": device_list})

    def handle_control_device(self, payload: Dict):
        """控制设备"""
        user_id = payload.get("user_id")
        device_id = payload.get("device_id")
        command = payload.get("command")
        params = payload.get("params", {})

        # 检查权限
        if self.device_users.get(device_id) != user_id:
            self.send_response(payload, False, "无权控制此设备")
            return

        # 转发命令到设备
        command_msg = {
            "device_id": device_id,
            "command": command,
            "params": params,
            "user_id": user_id,
            "timestamp": time.time()
        }

        self.mqtt_client.publish(TOPICS["device_command"], json.dumps(command_msg))
        print(f"[Cloud] 🎮 转发命令: {user_id} -> {device_id}.{command}({params})")

        self.send_response(payload, True, "命令已发送", {"device_id": device_id, "command": command})

    def handle_get_status(self, payload: Dict):
        """获取设备状态"""
        user_id = payload.get("user_id")
        device_id = payload.get("device_id")

        # 检查权限
        if self.device_users.get(device_id) != user_id:
            self.send_response(payload, False, "无权查看此设备")
            return

        status = self.device_states.get(device_id, {})
        self.send_response(payload, True, "获取成功", {"device_id": device_id, "status": status})

    def send_response(self, request: Dict, success: bool, message: str, data: Dict = None):
        """发送响应给用户"""
        response = {
            "success": success,
            "message": message,
            "data": data or {},
            "timestamp": time.time()
        }

        reply_topic = request.get("reply_topic", TOPICS["user_command_response"])
        self.mqtt_client.publish(reply_topic, json.dumps(response))
        print(f"[Cloud] 📤 响应: {message}")

    def start(self):
        """启动云端服务器"""
        print(f"[Cloud] 🚀 启动云端服务器...")
        print(f"[Cloud] MQTT Broker: {BROKER_HOST}:{BROKER_PORT}")

        try:
            self.mqtt_client.connect(BROKER_HOST, BROKER_PORT, 60)
            self.mqtt_client.loop_start()

            print("[Cloud] ✅ 云端服务器运行中... (按 Ctrl+C 停止)")

            # 保持运行
            while True:
                time.sleep(1)

        except KeyboardInterrupt:
            print("\n[Cloud] 🛑 正在关闭...")
        except Exception as e:
            print(f"[Cloud] ❌ 连接失败: {e}")
            print("[Cloud] 请确保 MQTT Broker 正在运行")
        finally:
            self.mqtt_client.loop_stop()
            self.mqtt_client.disconnect()
            print("[Cloud] 👋 已关闭")


if __name__ == "__main__":
    cloud = CloudServer()
    cloud.start()