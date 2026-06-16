# ============================================
# devices/smart_socket.py - 智能插座
# ============================================

import json
import time
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import paho.mqtt.client as mqtt
from config import BROKER_HOST, BROKER_PORT, TOPICS, SECRET_KEY, DEVICE_IDS
from crypto_utils import CryptoUtils


class SmartSocket:
    """智能插座设备"""

    def __init__(self, device_id: str, secret_key: bytes):
        self.device_id = device_id
        self.secret_key = secret_key

        # 设备状态
        self.is_on = False
        self.power_mode = "normal"  # normal, eco, timer
        self.power_consumption = 0  # 当前功耗 (W)

        self.mqtt_client = mqtt.Client()
        self.seq_num = 0
        self.running = True

        self.setup_mqtt_callbacks()

    def setup_mqtt_callbacks(self):
        self.mqtt_client.on_connect = self.on_connect
        self.mqtt_client.on_message = self.on_message

    def on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            print(f"[插座] ✅ 已连接到MQTT Broker")
            command_topic = f"device/{self.device_id}/command"
            self.mqtt_client.subscribe(command_topic)
            print(f"[插座] 已订阅: {command_topic}")
            self.register_device()
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
            if "command" in payload:
                self.handle_command(payload)
        except Exception as e:
            print(f"[插座] ❌ 异常: {e}")

    def handle_command(self, payload):
        command = payload.get("command")
        params = payload.get("params", {})

        print(f"[插座] 🎮 收到命令: {command}")

        if command == "on":
            self.is_on = True
            self.power_consumption = 50 if self.power_mode == "normal" else 20
            print(f"[插座] 🔌 插座已开启 (功耗: {self.power_consumption}W)")
        elif command == "off":
            self.is_on = False
            self.power_consumption = 0
            print(f"[插座] 🔴 插座已关闭")
        elif command == "set_power_mode":
            mode = params.get("mode", "normal")
            if mode in ["normal", "eco", "timer"]:
                self.power_mode = mode
                print(f"[插座] ⚡ 功率模式: {mode}")

        self.send_status()

    def send_status(self):
        status = {
            "device_id": self.device_id,
            "status": "online" if self.is_on else "standby",
            "properties": {
                "power": "on" if self.is_on else "off",
                "power_mode": self.power_mode,
                "power_consumption": self.power_consumption
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
        print(f"[插座] 📊 状态更新")

    def start(self):
        print(f"[插座] 🚀 启动智能插座: {self.device_id}")
        try:
            self.mqtt_client.connect(BROKER_HOST, BROKER_PORT, 60)
            self.mqtt_client.loop_start()
            print(f"[插座] ✅ 插座运行中...")
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            print(f"\n[插座] 🛑 关闭")
        finally:
            self.running = False
            self.mqtt_client.loop_stop()


if __name__ == "__main__":
    device_id = DEVICE_IDS["smart_socket"]
    ss = SmartSocket(device_id, SECRET_KEY)
    ss.start()