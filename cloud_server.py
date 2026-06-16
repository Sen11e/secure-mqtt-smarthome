# ============================================
# cloud_server.py - 完整修复版（确保绑定正常工作）
# ============================================

import json
import time
import secrets
from typing import Dict, List, Any

import paho.mqtt.client as mqtt

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
    def __init__(self):
        self.device_users: Dict[str, List[str]] = {}
        self.user_devices: Dict[str, List[str]] = {}
        self.device_states: Dict[str, Dict] = {}
        self.device_keys: Dict[str, bytes] = {}
        self.user_keys: Dict[str, bytes] = {}

        self.mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        self.setup_mqtt_callbacks()
        self._init_defaults()

    def _init_defaults(self):
        """初始化默认设备"""
        default_devices = [
            {"id": "ac_001", "name": "空调"},
            {"id": "lb_001", "name": "灯泡"},
            {"id": "ss_001", "name": "插座"}
        ]

        for device in default_devices:
            device_id = device["id"]
            self.device_keys[device_id] = secrets.token_bytes(32)
            self.device_states[device_id] = {
                "status": "online",
                "properties": {"power": "off", "temperature": 24, "brightness": 80}
            }
            self.device_users[device_id] = []
            print(f"[Cloud] 初始化设备: {device_id}")

        for user_id in ["user_001", "user_002"]:
            self.user_keys[user_id] = secrets.token_bytes(32)
            self.user_devices[user_id] = []

        print(f"\n[Cloud] 初始化完成")
        print(f"[Cloud] 可用设备: {list(self.device_keys.keys())}")
        print(f"[Cloud] 可用用户: {list(self.user_keys.keys())}")
        print(f"[Cloud] 当前绑定: 无（需要手动绑定）\n")

    def setup_mqtt_callbacks(self):
        self.mqtt_client.on_connect = self.on_connect
        self.mqtt_client.on_message = self.on_message

    def on_connect(self, client, userdata, flags, rc, properties=None):
        if rc == 0:
            print("[Cloud] ✅ 已连接到MQTT Broker")
            self.mqtt_client.subscribe(TOPICS["device_status"])
            self.mqtt_client.subscribe(TOPICS["device_register"])
            self.mqtt_client.subscribe(TOPICS["user_command"])
            print("[Cloud] 已订阅: device/status, device/register, user/command\n")
        else:
            print(f"[Cloud] ❌ 连接失败，错误码: {rc}")

    def on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode())
            print(f"\n[Cloud] 📨 收到 [{msg.topic}]: {json.dumps(payload, ensure_ascii=False)}")

            if msg.topic == TOPICS["device_status"]:
                self.handle_device_status(payload)
            elif msg.topic == TOPICS["device_register"]:
                self.handle_device_register(payload)
            elif msg.topic == TOPICS["user_command"]:
                self.handle_user_command(payload)
        except Exception as e:
            print(f"[Cloud] ❌ 处理异常: {e}")

    def handle_device_status(self, payload: Dict):
        device_id = payload.get("device_id")
        if device_id in self.device_states:
            self.device_states[device_id]["status"] = payload.get("status", "unknown")
            self.device_states[device_id]["properties"] = payload.get("properties", {})

            props = payload.get("properties", {})
            power = "🟢 开启" if props.get("power") == "on" else "🔴 关闭"
            temp = props.get("temperature", "?")
            print(f"[Cloud] 📊 状态 | {device_id} | {power} | 🌡️ {temp}°C")

    def handle_device_register(self, payload: Dict):
        device_id = payload.get("device_id")
        if device_id not in self.device_keys:
            self.device_keys[device_id] = secrets.token_bytes(32)
            self.device_states[device_id] = {"status": "registered", "properties": {}}
            self.device_users[device_id] = []
            print(f"[Cloud] 📱 新设备注册: {device_id}")
        else:
            print(f"[Cloud] 🔄 设备重新上线: {device_id}")

    def handle_user_command(self, payload: Dict):
        cmd_type = payload.get("type")
        user_id = payload.get("user_id")
        print(f"\n[Cloud] 👤 用户命令 | {user_id} -> {cmd_type}")

        if cmd_type == "bind_device":
            self.handle_bind_device(payload)
        elif cmd_type == "unbind_device":
            self.handle_unbind_device(payload)
        elif cmd_type == "control_device":
            self.handle_control_device(payload)
        elif cmd_type == "get_devices":
            self.handle_get_devices(payload)
        else:
            self.send_response(payload, False, f"未知命令: {cmd_type}")

    def handle_bind_device(self, payload: Dict):
        """绑定设备"""
        user_id = payload.get("user_id")
        params = payload.get("params", {})
        device_id = params.get("device_id") or payload.get("device_id")

        print(f"\n[Cloud] 🔗 绑定请求 | 用户: {user_id} | 设备: {device_id}")

        if not device_id:
            self.send_response(payload, False, "设备ID不能为空")
            return

        # 检查设备是否存在
        if device_id not in self.device_keys:
            print(f"[Cloud] ❌ 设备不存在！可用设备: {list(self.device_keys.keys())}")
            self.send_response(payload, False, f"设备不存在: {device_id}")
            return

        # 检查是否已绑定
        if user_id in self.device_users.get(device_id, []):
            self.send_response(payload, False, "设备已经绑定到当前用户")
            return

        # 执行绑定
        if device_id not in self.device_users:
            self.device_users[device_id] = []
        self.device_users[device_id].append(user_id)

        if user_id not in self.user_devices:
            self.user_devices[user_id] = []
        if device_id not in self.user_devices[user_id]:
            self.user_devices[user_id].append(device_id)

        print(f"[Cloud] ✅ 绑定成功！")
        print(f"[Cloud] 设备 {device_id} 当前绑定用户: {self.device_users[device_id]}")

        self.send_response(payload, True, "绑定成功", {"device_id": device_id})

    def handle_unbind_device(self, payload: Dict):
        user_id = payload.get("user_id")
        params = payload.get("params", {})
        device_id = params.get("device_id") or payload.get("device_id")

        if device_id in self.device_users and user_id in self.device_users[device_id]:
            self.device_users[device_id].remove(user_id)
            if user_id in self.user_devices and device_id in self.user_devices[user_id]:
                self.user_devices[user_id].remove(device_id)
            self.send_response(payload, True, "解绑成功")
        else:
            self.send_response(payload, False, "设备未绑定")

    def handle_get_devices(self, payload: Dict):
        user_id = payload.get("user_id")
        devices = self.user_devices.get(user_id, [])
        self.send_response(payload, True, "获取成功", {"devices": devices})

    def handle_control_device(self, payload: Dict):
        """控制设备"""
        user_id = payload.get("user_id")
        params = payload.get("params", {})
        device_id = params.get("device_id") or payload.get("device_id")
        command = params.get("command") or payload.get("command")
        cmd_params = params.get("params", {})

        print(f"\n[Cloud] 🎮 控制请求 | 用户: {user_id} | 设备: {device_id} | 命令: {command}")

        if not device_id:
            self.send_response(payload, False, "设备ID为空")
            return

        # 检查设备是否存在
        if device_id not in self.device_keys:
            self.send_response(payload, False, f"设备不存在: {device_id}")
            return

        # 检查是否已绑定
        if user_id not in self.device_users.get(device_id, []):
            print(f"[Cloud] ❌ 用户 {user_id} 未绑定设备 {device_id}")
            print(f"[Cloud] 当前绑定: {self.device_users.get(device_id, [])}")
            self.send_response(payload, False, f"请先绑定设备: {device_id}")
            return

        # 发送命令到设备
        command_msg = {
            "command": command,
            "params": cmd_params,
            "timestamp": time.time()
        }

        device_topic = f"device/{device_id}/command"
        self.mqtt_client.publish(device_topic, json.dumps(command_msg))
        print(f"[Cloud] ✅ 命令已发送到: {device_topic}")
        print(f"[Cloud] 📨 命令内容: {command_msg}")

        self.send_response(payload, True, "命令已发送", {"device_id": device_id})

    def send_response(self, request: Dict, success: bool, message: str, data: Dict = None):
        response = {
            "success": success,
            "message": message,
            "data": data or {},
            "timestamp": time.time()
        }
        reply_topic = request.get("reply_topic", TOPICS["user_command_response"])
        self.mqtt_client.publish(reply_topic, json.dumps(response))
        status = "✅" if success else "❌"
        print(f"[Cloud] {status} 响应: {message}")

    def start(self):
        print(f"\n{'=' * 50}")
        print(f"[Cloud] 🚀 启动云端服务器")
        print(f"[Cloud] MQTT Broker: {BROKER_HOST}:{BROKER_PORT}")
        print(f"{'=' * 50}\n")

        try:
            self.mqtt_client.connect(BROKER_HOST, BROKER_PORT, 60)
            self.mqtt_client.loop_start()
            print("[Cloud] ✅ 运行中，等待连接...\n")
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n[Cloud] 🛑 关闭")
        finally:
            self.mqtt_client.loop_stop()
            self.mqtt_client.disconnect()


if __name__ == "__main__":
    cloud = CloudServer()
    cloud.start()