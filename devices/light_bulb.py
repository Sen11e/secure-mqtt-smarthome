# ============================================
# devices/light_bulb.py - 灯泡设备
# ============================================

import json
import time
import threading
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import paho.mqtt.client as mqtt
from config import BROKER_HOST, BROKER_PORT, TOPICS, SECRET_KEY, DEVICE_IDS
from crypto_utils import CryptoUtils


class LightBulb:
    """智能灯泡设备"""

    def __init__(self, device_id: str, secret_key: bytes):
        self.device_id = device_id
        self.secret_key = secret_key

        # 设备状态
        self.is_on = False
        self.brightness = 80  # 0-100
        self.color = "white"  # white, warm, cool, rgb

        self.mqtt_client = mqtt.Client()
        self.seq_num = 0
        self.running = True

        self.setup_mqtt_callbacks()

    def setup_mqtt_callbacks(self):
        self.mqtt_client.on_connect = self.on_connect
        self.mqtt_client.on_message = self.on_message

    def on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            print(f"[灯泡] ✅ 已连接到MQTT Broker")
            command_topic = f"device/{self.device_id}/command"
            self.mqtt_client.subscribe(command_topic)
            print(f"[灯泡] 已订阅: {command_topic}")
            self.register_device()
        else:
            print(f"[灯泡] ❌ 连接失败")

    def register_device(self):
        register_msg = {
            "device_id": self.device_id,
            "device_type": "light_bulb",
            "mac": f"LB_{self.device_id[-6:]}",
            "product_key": "lb_product_001"
        }
        self.mqtt_client.publish(TOPICS["device_register"], json.dumps(register_msg))
        print(f"[灯泡] 📱 发送注册请求")

    def on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode())
            if "command" in payload:
                self.handle_command(payload)
        except Exception as e:
            print(f"[灯泡] ❌ 异常: {e}")

    def handle_command(self, payload):
        command = payload.get("command")
        params = payload.get("params", {})

        print(f"[灯泡] 🎮 收到命令: {command}")

        if command == "on":
            self.is_on = True
            print(f"[灯泡] 💡 灯泡已开启 (亮度: {self.brightness}%)")
        elif command == "off":
            self.is_on = False
            print(f"[灯泡] 🔴 灯泡已关闭")
        elif command == "set_brightness":
            brightness = params.get("brightness", 80)
            if 0 <= brightness <= 100:
                self.brightness = brightness
                print(f"[灯泡] 🌟 亮度设置为: {brightness}%")
        elif command == "set_color":
            color = params.get("color", "white")
            self.color = color
            print(f"[灯泡] 🎨 颜色设置为: {color}")

        self.send_status()

    def send_status(self):
        status = {
            "device_id": self.device_id,
            "status": "online" if self.is_on else "standby",
            "properties": {
                "power": "on" if self.is_on else "off",
                "brightness": self.brightness,
                "color": self.color
            },
            "timestamp": time.time()
        }

        self.seq_num += 1
        signature = CryptoUtils.sign_message(
            self.seq_num, status["timestamp"], status, self.secret_key
        )
        status["seq_num"] = self.seq_num
        status["signature"] = signature

        self.mqtt_client.publish(TOPICS["device_status"], json.dumps(status))
        print(f"[灯泡] 📊 状态更新")

    def start(self):
        print(f"[灯泡] 🚀 启动灯泡设备: {self.device_id}")
        try:
            self.mqtt_client.connect(BROKER_HOST, BROKER_PORT, 60)
            self.mqtt_client.loop_start()
            print(f"[灯泡] ✅ 灯泡运行中...")
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            print(f"\n[灯泡] 🛑 关闭")
        finally:
            self.running = False
            self.mqtt_client.loop_stop()


if __name__ == "__main__":
    device_id = DEVICE_IDS["light_bulb"]
    lb = LightBulb(device_id, SECRET_KEY)
    lb.start()