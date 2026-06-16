# ============================================
# devices/air_conditioner.py
# ============================================

import json
import time
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import paho.mqtt.client as mqtt
from config import BROKER_HOST, BROKER_PORT, TOPICS, SECRET_KEY
from crypto_utils import CryptoUtils


class AirConditioner:
    def __init__(self, device_id: str, secret_key: bytes):
        self.device_id = device_id
        self.secret_key = secret_key

        # 设备状态
        self.power = "off"
        self.temperature = 24
        self.mode = "cool"
        self.fan_speed = "auto"

        self.mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        self.seq_num = 0
        self.running = True

        self.setup_mqtt_callbacks()

    def setup_mqtt_callbacks(self):
        self.mqtt_client.on_connect = self.on_connect
        self.mqtt_client.on_message = self.on_message

    def on_connect(self, client, userdata, flags, rc, properties=None):
        if rc == 0:
            print(f"\n{'=' * 50}")
            print(f"[空调] ✅ 已连接到MQTT Broker")
            # 订阅命令主题
            command_topic = f"device/{self.device_id}/command"
            self.mqtt_client.subscribe(command_topic)
            print(f"[空调] 已订阅: {command_topic}")
            print(f"{'=' * 50}\n")

            # 注册设备
            self.register_device()

            # 延迟后上报初始状态
            time.sleep(1)
            self.send_status()
        else:
            print(f"[空调] ❌ 连接失败, 错误码: {rc}")

    def register_device(self):
        register_msg = {
            "device_id": self.device_id,
            "device_type": "air_conditioner",
            "mac": f"AC_{self.device_id[-6:]}",
            "product_key": "ac_product_001"
        }
        self.mqtt_client.publish(TOPICS["device_register"], json.dumps(register_msg))
        print(f"[空调] 📱 发送注册请求")

    def on_message(self, client, userdata, msg):
        """处理接收到的命令"""
        try:
            payload = json.loads(msg.payload.decode())
            print(f"\n[空调] 📨 收到消息: {json.dumps(payload, ensure_ascii=False)}")

            # 解析命令（支持多种格式）
            command = None
            params = {}

            if "command" in payload:
                command = payload["command"]
                params = payload.get("params", {})
            elif "params" in payload and isinstance(payload["params"], dict):
                if "command" in payload["params"]:
                    command = payload["params"]["command"]
                    params = payload["params"].get("params", {})

            if command:
                self.execute_command(command, params)
            else:
                print(f"[空调] ⚠️ 未识别到命令")

        except Exception as e:
            print(f"[空调] ❌ 处理异常: {e}")

    def execute_command(self, command, params):
        """执行命令并立即上报状态"""
        print(f"\n[空调] 🎮 执行: {command} {params}")

        changed = False

        if command == "on":
            self.power = "on"
            changed = True
            print(f"[空调] 🔛 空调已开启")

        elif command == "off":
            self.power = "off"
            changed = True
            print(f"[空调] 🔴 空调已关闭")

        elif command == "set_temperature":
            temp = params.get("temperature")
            if temp and 16 <= temp <= 30:
                self.temperature = temp
                changed = True
                print(f"[空调] 🌡️ 温度: {self.temperature}°C")

        elif command == "set_mode":
            mode = params.get("mode")
            if mode in ["cool", "heat", "fan", "auto"]:
                self.mode = mode
                changed = True
                mode_names = {"cool": "制冷", "heat": "制热", "fan": "送风", "auto": "自动"}
                print(f"[空调] 🔄 模式: {mode_names.get(self.mode)}")

        elif command == "set_fan_speed":
            speed = params.get("speed")
            if speed in ["auto", "low", "medium", "high"]:
                self.fan_speed = speed
                changed = True
                print(f"[空调] 💨 风速: {self.fan_speed}")

        # 无论是否改变，都上报当前状态（确保UI同步）
        self.send_status()

    def send_status(self):
        """上报设备状态到云端"""
        status = "online" if self.power == "on" else "standby"

        status_msg = {
            "device_id": self.device_id,
            "status": status,
            "properties": {
                "power": self.power,
                "temperature": self.temperature,
                "current_temperature": self.temperature,
                "mode": self.mode,
                "fan_speed": self.fan_speed
            },
            "timestamp": time.time()
        }

        # 添加签名
        self.seq_num += 1
        signature = CryptoUtils.sign_message(
            self.seq_num,
            status_msg["timestamp"],
            status_msg,
            self.secret_key
        )
        status_msg["seq_num"] = self.seq_num
        status_msg["signature"] = signature

        # 发布到云端
        self.mqtt_client.publish(TOPICS["device_status"], json.dumps(status_msg))

        # 打印状态
        mode_names = {"cool": "制冷", "heat": "制热", "fan": "送风", "auto": "自动"}
        power_text = "🟢 开启" if self.power == "on" else "🔴 关闭"
        print(f"[空调] 📤 上报: {power_text} | 🌡️ {self.temperature}°C | {mode_names.get(self.mode)}")

    def start(self):
        print(f"\n[空调] 🚀 启动设备: {self.device_id}")
        print(f"[空调] Broker: {BROKER_HOST}:{BROKER_PORT}\n")

        try:
            self.mqtt_client.connect(BROKER_HOST, BROKER_PORT, 60)
            self.mqtt_client.loop_start()
            print(f"[空调] ✅ 运行中，等待命令...\n")

            while self.running:
                time.sleep(1)

        except KeyboardInterrupt:
            print(f"\n[空调] 🛑 关闭")
        finally:
            self.running = False
            self.mqtt_client.loop_stop()
            self.mqtt_client.disconnect()


if __name__ == "__main__":
    ac = AirConditioner("ac_001", SECRET_KEY)
    ac.start()