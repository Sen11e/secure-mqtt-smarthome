# ============================================
# tests/test_replay_attack.py
# ============================================
"""
重放攻击防御测试
测试系统的防重放攻击能力
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import time
import paho.mqtt.client as mqtt
from crypto_utils import CryptoUtils, check_timestamp, check_seq_num
from config import BROKER_HOST, BROKER_PORT

# 全局变量
captured_message = None
captured_seq_num = 0
last_seq_num = {}

def get_next_seq_num(device_id, user_id):
    """获取下一个序列号"""
    key = f"{device_id}:{user_id}"
    current = last_seq_num.get(key, 0)
    next_seq = current + 1
    last_seq_num[key] = next_seq
    return next_seq

def on_message(client, userdata, msg):
    """捕获消息"""
    global captured_message, captured_seq_num
    try:
        payload = json.loads(msg.payload.decode())
        captured_message = payload
        captured_seq_num = payload.get("seq_num", 0)
        print(f"\n[测试] 捕获到消息:")
        print(f"  主题: {msg.topic}")
        print(f"  序列号: {captured_seq_num}")
        print(f"  内容: {payload}")
    except Exception as e:
        print(f"[测试] 捕获失败: {e}")

def on_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        print("[测试] ✅ 已连接到MQTT Broker")
        # 订阅用户响应主题
        client.subscribe("user/response")
    else:
        print(f"[测试] ❌ 连接失败")

def test_replay_attack():
    """测试重放攻击防御"""
    print("\n" + "="*60)
    print("重放攻击测试")
    print("="*60)

    # 创建MQTT客户端
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.on_connect = on_connect
    client.on_message = on_message

    try:
        client.connect(BROKER_HOST, BROKER_PORT, 60)
        client.loop_start()
        time.sleep(1)

        # 步骤1: 发送一条正常消息
        print("\n[测试] 步骤1: 发送正常控制消息...")

        test_user = "user_001"
        test_device = "ac_001"

        # 构造正常消息
        normal_msg = {
            "type": "control_device",
            "user_id": test_user,
            "params": {
                "device_id": test_device,
                "command": "on",
                "params": {}
            },
            "reply_topic": "user/response",
            "timestamp": time.time()
        }

        client.publish("user/command", json.dumps(normal_msg))
        print(f"[测试] 已发送正常消息: {normal_msg}")

        # 等待消息被处理
        time.sleep(2)

        # 步骤2: 发送重放消息（相同内容）
        print("\n[测试] 步骤2: 发送重放攻击消息（相同内容）...")

        replay_msg = normal_msg.copy()
        client.publish("user/command", json.dumps(replay_msg))
        print(f"[测试] 已发送重放消息")

        time.sleep(2)

        print("\n" + "="*60)
        print("测试结果分析:")
        print("="*60)
        print("✅ 正常消息应该被接受")
        print("❌ 重放消息应该被拒绝（序列号验证失败）")
        print("\n请检查云端日志:")
        print("  - 正常消息: 应显示'命令已发送'")
        print("  - 重放消息: 应显示'序列号验证失败'或'无权控制'")

    except Exception as e:
        print(f"[测试] 异常: {e}")
    finally:
        client.loop_stop()
        client.disconnect()

def test_timestamp_validation():
    """测试时间戳验证"""
    print("\n" + "="*60)
    print("时间戳验证测试")
    print("="*60)

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.on_connect = on_connect

    try:
        client.connect(BROKER_HOST, BROKER_PORT, 60)
        client.loop_start()
        time.sleep(1)

        # 发送过期的消息（时间戳为10分钟前）
        print("\n[测试] 发送过期时间戳消息（10分钟前）...")

        expired_msg = {
            "type": "control_device",
            "user_id": "user_001",
            "params": {
                "device_id": "ac_001",
                "command": "off",
                "params": {}
            },
            "reply_topic": "user/response",
            "timestamp": time.time() - 600  # 10分钟前
        }

        client.publish("user/command", json.dumps(expired_msg))
        print(f"[测试] 已发送过期消息")

        time.sleep(2)

        print("\n测试结果:")
        print("✅ 过期消息应该被拒绝（时间戳验证失败）")

    except Exception as e:
        print(f"[测试] 异常: {e}")
    finally:
        client.loop_stop()
        client.disconnect()

def test_seq_num_validation():
    """测试序列号验证"""
    print("\n" + "="*60)
    print("序列号验证测试")
    print("="*60)

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.on_connect = on_connect

    try:
        client.connect(BROKER_HOST, BROKER_PORT, 60)
        client.loop_start()
        time.sleep(1)

        # 发送两条相同序列号的消息
        print("\n[测试] 发送相同序列号的消息...")

        base_msg = {
            "type": "control_device",
            "user_id": "user_001",
            "params": {
                "device_id": "ac_001",
                "command": "on",
                "params": {}
            },
            "reply_topic": "user/response",
            "timestamp": time.time()
        }

        # 第一次发送
        client.publish("user/command", json.dumps(base_msg))
        print("[测试] 第一次发送")
        time.sleep(1)

        # 第二次发送相同内容
        client.publish("user/command", json.dumps(base_msg))
        print("[测试] 第二次发送（相同内容）")
        time.sleep(2)

        print("\n测试结果:")
        print("✅ 第一次消息应该被接受")
        print("❌ 第二次消息应该被拒绝（序列号重复）")

    except Exception as e:
        print(f"[测试] 异常: {e}")
    finally:
        client.loop_stop()
        client.disconnect()

if __name__ == "__main__":
    print("\n" + "="*60)
    print("物联网安全测试套件 - 防重放攻击测试")
    print("="*60)
    print("\n注意: 请确保以下服务正在运行:")
    print("  1. MQTT Broker (docker start mosquitto)")
    print("  2. 云端服务器 (python cloud_server.py)")
    print("  3. 至少一个设备 (python devices/air_conditioner.py)")
    print("\n" + "="*60)

    input("\n按 Enter 键开始测试...")

    # 运行测试
    test_replay_attack()
    test_timestamp_validation()
    test_seq_num_validation()

    print("\n" + "="*60)
    print("测试完成!")
    print("="*60)