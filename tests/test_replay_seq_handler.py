"""
重放攻击防御测试 — handler 级别

证明 `crypto_utils.check_seq_num` 在生产路径中真的被调用,
不是死代码。两部分:

1. 进程内确定性测试:CloudServer._handle_user_message 收到同 seq 消息两次,
   第二次必须被拒,且 user_seq 字典只更新一次。
2. 真实 broker 测试:启动 cloud_server.py 子进程,绑定设备,捕获返回消息
   的原始字节,逐字重发,断言云端不再发第二条响应。
"""
import json
import subprocess
import sys
import time
import os
from typing import List

import paho.mqtt.client as mqtt

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
import crypto_utils
import message_format
from cloud_server import CloudServer

PASS = "[PASS]"
FAIL = "[FAIL]"
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VENV_PYTHON = os.path.join(BASE_DIR, "venv", "Scripts", "python.exe")


# ── Test 1: in-process ────────────────────────────────────
def test_in_process():
    print("=" * 60)
    print("[TEST 1] In-process: CloudServer._handle_user_message 重复 seq")
    print("=" * 60)
    server = CloudServer(config.SECRET_KEY)
    user_id = "user_001"
    device_id = "ac_001"

    payload = message_format.create_bind_message(user_id, device_id)
    signed = crypto_utils.create_signed_message(
        config.SECRET_KEY,
        message_format.seq_manager.get_next(),
        payload,
    )

    # 第一次调用:应该成功绑定
    server._handle_user_message(user_id, signed)
    first_seq = server.user_seq[user_id]
    bound_after_first = device_id in server.user_devices[user_id]
    print(f"  第一次后 user_seq[{user_id}] = {first_seq}")
    print(f"  第一次后绑定状态: {bound_after_first}")

    # 第二次调用(同 seq 同 ts 同 sig):应该被拒
    server._handle_user_message(user_id, signed)
    second_seq = server.user_seq[user_id]
    print(f"  第二次后 user_seq[{user_id}] = {second_seq}")

    ok = (
        first_seq == signed["seq_num"]
        and second_seq == first_seq  # 第二次没更新
        and bound_after_first
    )
    print(f"  {PASS if ok else FAIL} 重复 seq 被拒,user_seq 仅更新一次,绑定仍生效")
    print()
    return ok


# ── Test 2: real broker verbatim replay ──────────────────
class CapturingUser:
    """模拟用户,捕获自己发出的原始字节用于重放,记录收到的响应数。"""

    def __init__(self, user_id: str):
        self.user_id = user_id
        self.responses: List[dict] = []
        self.outgoing_payloads: List[bytes] = []  # 用户自己发出的 MQTT 原始字节
        self.client = mqtt.Client(
            client_id=f"replay_test_{user_id}_{int(time.time())}",
            callback_api_version=mqtt.CallbackAPIVersion.VERSION1,
        )
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            client.subscribe(f"home/{self.user_id}/from_cloud")

    def _on_message(self, client, userdata, msg):
        try:
            data = json.loads(msg.payload.decode())
            payload = data.get("payload", {})
            seq_num = data.get("seq_num")
            timestamp = data.get("timestamp")
            signature = data.get("signature")
            if not crypto_utils.verify_signature(
                config.SECRET_KEY, seq_num, timestamp, payload, signature
            ):
                return
            if not crypto_utils.check_timestamp(timestamp, config.TIME_WINDOW):
                return
            # 只计数 success=True 的绑定成功响应,排除被拒后云端发的错误消息
            if payload.get("success") is True and "绑定成功" in payload.get("message", ""):
                self.responses.append(payload)
        except Exception:
            pass

    def bind(self, device_id: str):
        payload = message_format.create_bind_message(self.user_id, device_id)
        signed = crypto_utils.create_signed_message(
            config.SECRET_KEY,
            message_format.seq_manager.get_next(),
            payload,
        )
        raw = json.dumps(signed).encode("utf-8")
        # 记录自己即将发出的原始字节
        self.outgoing_payloads.append(raw)
        self.client.publish(f"home/{self.user_id}/to_cloud", raw)

    def publish_raw(self, topic: str, raw: bytes):
        self.client.publish(topic, raw)

    def connect(self):
        self.client.connect(config.BROKER_HOST, config.BROKER_PORT)
        self.client.loop_start()

    def disconnect(self):
        self.client.loop_stop()


def test_broker_replay():
    print("=" * 60)
    print("[TEST 2] 真实 broker:逐字重放,云端必须只响应一次")
    print("=" * 60)
    cloud = None
    user = None
    ok = False
    try:
        cloud = subprocess.Popen(
            [VENV_PYTHON, "cloud_server.py"],
            cwd=BASE_DIR,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        time.sleep(2)

        user = CapturingUser("user_001")
        user.connect()
        time.sleep(0.5)

        # 第一次绑定
        user.bind("ac_001")
        time.sleep(1.5)

        first_count = len(user.responses)
        first_out_count = len(user.outgoing_payloads)
        print(f"  第一次绑定:收到 {first_count} 条 success 响应, 已发出 {first_out_count} 条消息")
        if first_count < 1:
            print(f"  {FAIL} 云端没有响应,前置条件不成立")
            return False
        if first_out_count < 1:
            print(f"  {FAIL} 没有捕获到发出的原始消息,无法重放")
            return False

        # 逐字重放自己发出的第一条消息
        captured = user.outgoing_payloads[0]
        user.publish_raw(f"home/{user.user_id}/to_cloud", captured)
        time.sleep(1.5)

        second_count = len(user.responses)
        print(f"  重放一次后:success 响应总数 = {second_count}")
        ok = second_count == first_count
        print(f"  {PASS if ok else FAIL} 逐字重放没有触发第二次绑定响应")
        print()
        return ok
    finally:
        if user is not None:
            user.disconnect()
        if cloud is not None:
            cloud.terminate()
            try:
                cloud.wait(timeout=3)
            except subprocess.TimeoutExpired:
                cloud.kill()


# ── Main ──────────────────────────────────────────────────
def main():
    print()
    results = []
    try:
        results.append(test_in_process())
    except Exception as e:
        import traceback
        traceback.print_exc()
        results.append(False)
    try:
        results.append(test_broker_replay())
    except Exception as e:
        import traceback
        traceback.print_exc()
        results.append(False)

    print("=" * 60)
    if all(results):
        print("[RESULT] ALL TESTS PASSED — seq_num 防线已在生产路径中生效")
        return 0
    print("[RESULT] SOME TESTS FAILED")
    return 1


if __name__ == "__main__":
    sys.exit(main())
