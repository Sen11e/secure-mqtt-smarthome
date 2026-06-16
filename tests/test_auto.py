"""
自动化测试脚本 - 验证完整系统功能
"""
import json
import time
import sys
import os
import threading

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
import crypto_utils
import message_format
import paho.mqtt.client as mqtt


class TestClient:
    """测试用MQTT客户端"""

    def __init__(self, client_id: str):
        self.client_id = client_id
        self.messages = []
        self.client = mqtt.Client(client_id=client_id, callback_api_version=mqtt.CallbackAPIVersion.VERSION1)
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            print(f"[Test {self.client_id}] Connected to MQTT")
            client.subscribe(f"home/user_001/from_cloud")
        else:
            print(f"[Test {self.client_id}] MQTT connection failed, rc={rc}")

    def _on_message(self, client, userdata, msg):
        try:
            data = json.loads(msg.payload.decode())
            self.messages.append(data)
            print(f"[Test {self.client_id}] Received: {data.get('payload', {}).get('message', 'unknown')}")
        except Exception as e:
            print(f"[Test {self.client_id}] Error: {e}")

    def publish(self, topic, payload):
        self.client.publish(topic, json.dumps(payload))

    def connect(self):
        self.client.connect(config.BROKER_HOST, config.BROKER_PORT)
        self.client.loop_start()

    def disconnect(self):
        self.client.loop_stop()


def test_full_flow():
    print("="*60)
    print("自动化测试 - 完整流程")
    print("="*60)

    # 1. 连接测试客户端
    print("\n[1] 连接测试客户端...")
    test_client = TestClient("test_client_001")
    test_client.connect()
    time.sleep(1)

    # 2. 模拟用户绑定设备
    print("\n[2] 模拟用户绑定设备 (ac_001)...")
    bind_payload = message_format.create_bind_message("user_001", "ac_001")
    signed_msg = crypto_utils.create_signed_message(
        config.SECRET_KEY,
        message_format.seq_manager.get_next(),
        bind_payload
    )
    test_client.publish("home/user_001/to_cloud", signed_msg)
    time.sleep(1)

    # 3. 模拟用户发送控制命令
    print("\n[3] 模拟用户发送控制命令 (开启空调)...")
    control_payload = message_format.create_control_message(
        "ac_001",
        "on"
    )
    signed_msg = crypto_utils.create_signed_message(
        config.SECRET_KEY,
        message_format.seq_manager.get_next(),
        control_payload
    )
    test_client.publish("home/user_001/to_cloud", signed_msg)
    time.sleep(2)

    # 4. 检查收到的消息
    print("\n[4] 检查收到的消息...")
    if test_client.messages:
        print(f"  收到 {len(test_client.messages)} 条消息")
        for msg in test_client.messages:
            print(f"  - {msg}")
    else:
        print("  未收到任何消息")

    # 5. 测试防重放攻击 - 尝试重放旧消息
    print("\n[5] 测试防重放攻击 - 尝试重放旧消息...")
    old_seq = 1
    old_timestamp = int(time.time()) - 600  # 10分钟前
    old_payload = message_format.create_control_message("ac_001", "off")
    old_signature = crypto_utils.generate_signature(
        config.SECRET_KEY, old_seq, old_timestamp, old_payload
    )
    old_msg = {
        "seq_num": old_seq,
        "timestamp": old_timestamp,
        "payload": old_payload,
        "signature": old_signature
    }
    print(f"  重放序列号={old_seq}, 时间戳={old_timestamp} (10分钟前)")
    test_client.publish("home/user_001/to_cloud", old_msg)
    time.sleep(1)

    print("\n" + "="*60)
    print("测试完成!")
    print("="*60)
    print("\n预期结果:")
    print("  - 设备绑定成功")
    print("  - 设备控制命令被转发")
    print("  - 重放的消息被拒绝 (时间戳过期)")
    print("\n请查看云服务器和设备输出验证")

    test_client.disconnect()


if __name__ == "__main__":
    test_full_flow()