# ============================================
# devices/smart_socket.py
# ============================================

import json
import time
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import paho.mqtt.client as mqtt
from config import BROKER_HOST, BROKER_PORT, TOPICS, SECRET_KEY
from crypto_utils import CryptoUtils


class SmartSocket:
    def __init__(self, device_id: str, secret_key: bytes):
        self.device_id = device_id
        self.secret_key = secret_key

        self.power = "off"
        self.power_mode = "normal"

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
            print(f"[插座] ✅ 已连接到MQTT Broker")
            command_topic = f"device/{self.device_id}/command"
            self.mqtt_client.subscribe(command_topic)
            print(f"[插座] 已订阅: {command_topic}")
            print(f"{'=' * 50}\n")

            self.register_device()
            time.sleep(1)
            self.send_status()
        else:
            print(f"[插座] ❌ 连接失败")

    def register_device(self):
        register_msg = {
            "device_id": self.device_id,
            "device_type": "smart_socket",
            "mac": f"SS_{self.device_id[-6:]}",
            "product_key": "ss_product_001"
        }
        self.mqtt_client.publish(TOPICS["device_register"], json.dumps(register_msg))
        print(f"[插座] 📱 发送注册请求")

    def on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode())
            print(f"\n[插座] 📨 收到: {json.dumps(payload, ensure_ascii=False)}")

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

        except Exception as e:
            print(f"[插座] ❌ 异常: {e}")

    def execute_command(self, command, params):
        print(f"\n[插座] 🎮 执行: {command} {params}")

        changed = False

        if command == "on":
            self.power = "on"
            changed = True
            print(f"[插座] 🔌 已开启")

        elif command == "off":
            self.power = "off"
            changed = True
            print(f"[插座] 🔴 已关闭")

        elif command == "set_power_mode":
            mode = params.get("mode")
            if mode in ["normal", "eco"]:
                self.power_mode = mode
                changed = True
                print(f"[插座] ⚡ 模式: {mode}")

        self.send_status()

    def send_status(self):
        status = "online" if self.power == "on" else "standby"

        status_msg = {
            "device_id": self.device_id,
            "status": status,
            "properties": {
                "power": self.power,
                "power_mode": self.power_mode
            },
            "timestamp": time.time()
        }

        self.seq_num += 1
        signature = CryptoUtils.sign_message(
            self.seq_num, status_msg["timestamp"], status_msg, self.secret_key
        )
        status_msg["seq_num"] = self.seq_num
        status_msg["signature"] = signature

        self.mqtt_client.publish(TOPICS["device_status"], json.dumps(status_msg))

        power_text = "🟢 开启" if self.power == "on" else "🔴 关闭"
        print(f"[插座] 📤 上报: {power_text} | 模式: {self.power_mode}")

    def start(self):
        print(f"\n[插座] 🚀 启动设备: {self.device_id}\n")

        try:
            self.mqtt_client.connect(BROKER_HOST, BROKER_PORT, 60)
            self.mqtt_client.loop_start()
            print(f"[插座] ✅ 运行中...\n")
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            print(f"\n[插座] 🛑 关闭")
        finally:
            self.running = False
            self.mqtt_client.loop_stop()
            self.mqtt_client.disconnect()


if __name__ == "__main__":
    ss = SmartSocket("ss_001", SECRET_KEY)
    ss.start()