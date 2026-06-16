# ============================================
# tests/attack_simulator.py - 简化版
# ============================================

import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import time
import random
import paho.mqtt.client as mqtt
from config import BROKER_HOST, BROKER_PORT


class AttackSimulator:
    def __init__(self):
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)

    def connect(self):
        try:
            self.client.connect(BROKER_HOST, BROKER_PORT, 60)
            self.client.loop_start()
            time.sleep(1)
            print("[攻击者] ✅ 已连接到MQTT Broker")
            return True
        except Exception as e:
            print(f"[攻击者] ❌ 连接失败: {e}")
            return False

    def disconnect(self):
        self.client.loop_stop()
        self.client.disconnect()

    # ========== 攻击1: 重放攻击 ==========
    def replay_attack(self):
        print("\n" + "=" * 60)
        print("攻击1: 重放攻击 (Replay Attack)")
        print("=" * 60)

        print("[攻击] 发送第一条正常命令...")
        msg = {
            "type": "control_device",
            "user_id": "user_001",
            "params": {"device_id": "ac_001", "command": "on", "params": {}},
            "reply_topic": "user/response",
            "timestamp": time.time()
        }
        self.client.publish("user/command", json.dumps(msg))
        time.sleep(0.5)

        print("[攻击] 发送相同的命令（重放攻击）...")
        self.client.publish("user/command", json.dumps(msg))
        time.sleep(0.5)

        print("\n✅ 重放攻击测试完成，请查看UI安全面板")

    # ========== 攻击2: 篡改用户ID ==========
    def tamper_attack_user(self):
        print("\n" + "=" * 60)
        print("攻击2: 消息篡改攻击 - 伪造用户ID")
        print("=" * 60)

        msg = {
            "type": "control_device",
            "user_id": "fake_hacker_123",
            "params": {"device_id": "ac_001", "command": "off", "params": {}},
            "reply_topic": "user/response",
            "timestamp": time.time()
        }
        self.client.publish("user/command", json.dumps(msg))
        print("[攻击] 发送伪造用户ID的消息")
        time.sleep(0.5)
        print("\n✅ 篡改攻击测试完成，请查看UI安全面板")

    # ========== 攻击3: 越权访问 ==========
    def privilege_attack(self):
        print("\n" + "=" * 60)
        print("攻击3: 越权访问攻击")
        print("=" * 60)

        msg = {
            "type": "control_device",
            "user_id": "user_002",
            "params": {"device_id": "ac_001", "command": "off", "params": {}},
            "reply_topic": "user/response",
            "timestamp": time.time()
        }
        self.client.publish("user/command", json.dumps(msg))
        print("[攻击] user_002 尝试控制 ac_001")
        time.sleep(0.5)
        print("\n✅ 越权攻击测试完成，请查看UI安全面板")

    # ========== 攻击4: 设备伪造 ==========
    def device_spoofing(self):
        print("\n" + "=" * 60)
        print("攻击4: 设备伪造攻击")
        print("=" * 60)

        msg = {
            "device_id": "ac_001",
            "device_type": "air_conditioner",
            "mac": "FAKE:MAC:ADDRESS",
            "product_key": "fake_key"
        }
        self.client.publish("device/register", json.dumps(msg))
        print("[攻击] 尝试伪造 ac_001 设备注册")
        time.sleep(0.5)
        print("\n✅ 设备伪造测试完成，请查看UI安全面板")

    # ========== 攻击5: 时间戳攻击 ==========
    def timestamp_attack(self):
        print("\n" + "=" * 60)
        print("攻击5: 时间戳攻击")
        print("=" * 60)

        msg = {
            "type": "control_device",
            "user_id": "user_001",
            "params": {"device_id": "ac_001", "command": "on", "params": {}},
            "reply_topic": "user/response",
            "timestamp": time.time() - 600
        }
        self.client.publish("user/command", json.dumps(msg))
        print("[攻击] 发送过期时间戳的消息（10分钟前）")
        time.sleep(0.5)
        print("\n✅ 时间戳攻击测试完成，请查看UI安全面板")

    # ========== 攻击6: DoS攻击 ==========
    def dos_attack(self, duration=2):
        print("\n" + "=" * 60)
        print("攻击6: 拒绝服务攻击 (DoS)")
        print("=" * 60)

        print(f"[攻击] 开始DoS攻击，持续 {duration} 秒...")
        start = time.time()
        count = 0
        while time.time() - start < duration:
            msg = {
                "type": "control_device",
                "user_id": f"attacker_{random.randint(1, 100)}",
                "params": {"device_id": f"device_{random.randint(1, 10)}", "command": "on", "params": {}},
                "reply_topic": "user/response",
                "timestamp": time.time()
            }
            self.client.publish("user/command", json.dumps(msg))
            count += 1
            time.sleep(0.01)

        print(f"[攻击] 发送了 {count} 条恶意消息")
        print("\n✅ DoS攻击测试完成，请查看UI安全面板")


def main():
    print("\n" + "=" * 60)
    print("🦹 物联网安全测试 - 攻击模拟器")
    print("=" * 60)
    print("\n本工具模拟以下攻击类型:")
    print("  1. 重放攻击 (发送重复命令)")
    print("  2. 消息篡改攻击 (伪造用户ID)")
    print("  3. 越权访问攻击 (未授权设备控制)")
    print("  4. 设备伪造攻击 (重复注册)")
    print("  5. 时间戳攻击 (过期时间戳)")
    print("  6. 拒绝服务攻击 (大量消息)")
    print("\n⚠️ 请确保以下服务正在运行:")
    print("  - MQTT Broker")
    print("  - 云端服务器")
    print("  - Web UI")
    print("=" * 60)

    input("\n按 Enter 键开始攻击测试...")

    attacker = AttackSimulator()
    if not attacker.connect():
        print("[错误] 无法连接到MQTT Broker")
        return

    attacker.replay_attack()
    time.sleep(1)

    attacker.tamper_attack_user()
    time.sleep(1)

    attacker.privilege_attack()
    time.sleep(1)

    attacker.device_spoofing()
    time.sleep(1)

    attacker.timestamp_attack()
    time.sleep(1)

    print("\n是否执行DoS攻击？")
    choice = input("输入 y 执行，其他键跳过: ")
    if choice.lower() == 'y':
        attacker.dos_attack(duration=2)

    attacker.disconnect()

    print("\n" + "=" * 60)
    print("✅ 攻击测试完成！")
    print("请查看 Web UI 的安全监控面板")
    print("=" * 60)


if __name__ == "__main__":
    main()