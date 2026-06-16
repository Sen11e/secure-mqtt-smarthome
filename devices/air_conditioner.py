# ============================================
# devices/air_conditioner.py - 完整修复版
# ============================================

import json
import time
import threading
import secrets
from typing import Dict, Any

import paho.mqtt.client as mqtt

# 添加父目录到路径
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import BROKER_HOST, BROKER_PORT, TOPICS, SECRET_KEY, DEVICE_IDS
from crypto_utils import CryptoUtils, check_timestamp, check_seq_num


class AirConditioner:
    """智能空调设备"""

    def __init__(self, device_id: str, secret_key: bytes):
        self.device_id = device_id
        self.secret_key = secret_key

        # 设备状态
        self.is_on = False
        self.temperature = 24  # 摄氏度
        self.mode = "cool"  # cool, heat, fan, auto
        self.fan_speed = "auto"  # auto, low, medium, high
        self.target_temperature = 24

        # MQTT 客户端
        self.mqtt_client = mqtt.Client()
        self.seq_num = 0
        self.setup_mqtt_callbacks()

        # 状态更新线程
        self.running = True
        self.status_thread = threading.Thread(target=self._periodic_status_update, daemon=True)

    def setup_mqtt_callbacks(self):
        """设置MQTT回调"""
        self.mqtt_client.on_connect = self.on_connect
        self.mqtt_client.on_message = self.on_message

    def on_connect(self, client, userdata, flags, rc):
        """连接成功回调"""
        if rc == 0:
            print(f"[空调] ✅ 已连接到MQTT Broker")
            # 订阅命令主题
            command_topic = f"device/{self.device_id}/command"
            self.mqtt_client.subscribe(command_topic)
            print(f"[空调] 已订阅: {command_topic}")

            # 发送注册消息
            self.register_device()
        else:
            print(f"[空调] ❌ 连接失败，错误码: {rc}")

    def register_device(self):
        """设备注册"""
        register_msg = {
            "device_id": self.device_id,
            "device_type": "air_conditioner",
            "mac": f"AC_{self.device_id[-6:]}",
            "product_key": "ac_product_001",
            "firmware_version": "1.0.0"
        }

        self.mqtt_client.publish(TOPICS["device_register"], json.dumps(register_msg))
        print(f"[空调] 📱 发送注册请求: {self.device_id}")

        # 订阅注册响应
        response_topic = f"device/{self.device_id}/register_response"
        self.mqtt_client.subscribe(response_topic)

    def on_message(self, client, userdata, msg):
        """处理接收到的消息"""
        try:
            payload = json.loads(msg.payload.decode())

            if "command" in payload:
                self.handle_command(payload)
            elif "response" in msg.topic:
                self.handle_response(payload)

        except json.JSONDecodeError:
            print(f"[空调] ❌ JSON解析失败: {msg.payload}")
        except Exception as e:
            print(f"[空调] ❌ 处理消息异常: {e}")

    def handle_command(self, payload: Dict):
        """处理控制命令"""
        command = payload.get("command")
        params = payload.get("params", {})

        print(f"[空调] 🎮 收到命令: {command} {params}")

        result = False
        if command == "on":
            result = self.turn_on()
        elif command == "off":
            result = self.turn_off()
        elif command == "set_temperature":
            temp = params.get("temperature", 24)
            result = self.set_temperature(temp)
        elif command == "set_mode":
            mode = params.get("mode", "cool")
            result = self.set_mode(mode)
        elif command == "set_fan_speed":
            speed = params.get("speed", "auto")
            result = self.set_fan_speed(speed)
        elif command == "get_status":
            result = self.send_status()

        # 发送命令响应
        response = {
            "device_id": self.device_id,
            "command": command,
            "result": result,
            "timestamp": time.time()
        }
        self.mqtt_client.publish(TOPICS["device_command_response"], json.dumps(response))

        # 发送状态更新
        self.send_status()

    def handle_response(self, payload: Dict):
        """处理响应消息"""
        if payload.get("success"):
            print(f"[空调] ✅ 注册成功: {payload.get('message')}")
        else:
            print(f"[空调] ❌ 注册失败: {payload.get('message')}")

    def turn_on(self) -> bool:
        """开启空调"""
        self.is_on = True
        print(f"[空调] 🔛 空调已开启")
        return True

    def turn_off(self) -> bool:
        """关闭空调"""
        self.is_on = False
        print(f"[空调] 🔴 空调已关闭")
        return True

    def set_temperature(self, temperature: int) -> bool:
        """设置温度"""
        if 16 <= temperature <= 30:
            self.target_temperature = temperature
            if self.is_on:
                self.temperature = temperature
            print(f"[空调] 🌡️ 温度设置为: {temperature}°C")
            return True
        else:
            print(f"[空调] ❌ 无效温度: {temperature} (有效范围: 16-30)")
            return False

    def set_mode(self, mode: str) -> bool:
        """设置模式"""
        valid_modes = ["cool", "heat", "fan", "auto"]
        if mode in valid_modes:
            self.mode = mode
            print(f"[空调] 🔄 模式设置为: {mode}")
            return True
        else:
            print(f"[空调] ❌ 无效模式: {mode}")
            return False

    def set_fan_speed(self, speed: str) -> bool:
        """设置风速"""
        valid_speeds = ["auto", "low", "medium", "high"]
        if speed in valid_speeds:
            self.fan_speed = speed
            print(f"[空调] 💨 风速设置为: {speed}")
            return True
        else:
            print(f"[空调] ❌ 无效风速: {speed}")
            return False

    def send_status(self) -> bool:
        """发送设备状态"""
        status = {
            "device_id": self.device_id,
            "status": "online" if self.is_on else "standby",
            "properties": {
                "power": "on" if self.is_on else "off",
                "temperature": self.target_temperature if self.is_on else self.temperature,
                "current_temperature": self.temperature,
                "mode": self.mode,
                "fan_speed": self.fan_speed
            },
            "timestamp": time.time()
        }

        # 添加安全签名
        self.seq_num += 1
        signature = CryptoUtils.sign_message(
            self.seq_num,
            status["timestamp"],
            status,
            self.secret_key
        )
        status["seq_num"] = self.seq_num
        status["signature"] = signature

        self.mqtt_client.publish(TOPICS["device_status"], json.dumps(status))
        print(f"[空调] 📊 发送状态: {'开启' if self.is_on else '关闭'} | {self.target_temperature}°C | {self.mode}模式")
        return True

    def _periodic_status_update(self):
        """定期发送状态更新"""
        while self.running:
            time.sleep(30)  # 每30秒发送一次
            if self.mqtt_client.is_connected():
                self.send_status()

    def start(self):
        """启动设备"""
        print(f"[空调] 🚀 启动空调设备: {self.device_id}")
        print(f"[空调] MQTT Broker: {BROKER_HOST}:{BROKER_PORT}")

        try:
            self.mqtt_client.connect(BROKER_HOST, BROKER_PORT, 60)
            self.mqtt_client.loop_start()
            self.status_thread.start()

            print(f"[空调] ✅ 空调运行中... (按 Ctrl+C 停止)")

            # 保持运行
            while True:
                time.sleep(1)

        except KeyboardInterrupt:
            print(f"\n[空调] 🛑 正在关闭...")
        except Exception as e:
            print(f"[空调] ❌ 连接失败: {e}")
            print(f"[空调] 请确保 MQTT Broker 正在运行")
        finally:
            self.running = False
            self.mqtt_client.loop_stop()
            self.mqtt_client.disconnect()
            print(f"[空调] 👋 已关闭")


if __name__ == "__main__":
    # 使用配置中的设备ID和密钥
    device_id = DEVICE_IDS["air_conditioner"]
    ac = AirConditioner(device_id, SECRET_KEY)
    ac.start()