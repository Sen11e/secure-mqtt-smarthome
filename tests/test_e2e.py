"""
端到端测试：启动所有组件，模拟用户操作，验证设备控制是否正常
"""
import subprocess
import time
import sys
import os
import json
import paho.mqtt.client as mqtt

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
import crypto_utils
import message_format

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VENV_PYTHON = os.path.join(BASE_DIR, "venv", "Scripts", "python.exe")

PASS = "[PASS]"
FAIL = "[FAIL]"

class TestUser:
    def __init__(self, user_id):
        self.user_id = user_id
        self.responses = []
        self.statuses = []
        self.client = mqtt.Client(
            client_id=f"test_user_{user_id}",
            callback_api_version=mqtt.CallbackAPIVersion.VERSION1
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
            if "seq_num" in data and "signature" in data:
                if not crypto_utils.verify_signature(
                    config.SECRET_KEY,
                    data["seq_num"], data["timestamp"], payload, data["signature"]
                ):
                    return
                if not crypto_utils.check_timestamp(data["timestamp"], config.TIME_WINDOW):
                    return
                msg_type = payload.get("type")
                if msg_type == "device_status":
                    self.statuses.append(payload)
                elif "success" in payload:
                    self.responses.append({
                        "success": payload["success"],
                        "message": payload["message"],
                    })
        except Exception:
            pass

    def connect(self):
        self.client.connect(config.BROKER_HOST, config.BROKER_PORT)
        self.client.loop_start()

    def disconnect(self):
        self.client.loop_stop()

    def send_signed(self, payload):
        signed = crypto_utils.create_signed_message(
            config.SECRET_KEY,
            message_format.seq_manager.get_next(),
            payload
        )
        self.client.publish(f"home/{self.user_id}/to_cloud", json.dumps(signed))

    def bind_device(self, device_id):
        self.responses.clear()
        self.statuses.clear()
        payload = message_format.create_bind_message(self.user_id, device_id)
        self.send_signed(payload)

    def unbind_device(self, device_id):
        self.responses.clear()
        self.statuses.clear()
        payload = message_format.create_unbind_message(self.user_id, device_id)
        self.send_signed(payload)

    def control_device(self, device_id, command, params=None):
        self.responses.clear()
        self.statuses.clear()
        payload = message_format.create_control_message(device_id, command, params)
        self.send_signed(payload)


def main():
    processes = []
    all_passed = True

    try:
        # 1. 启动后台组件
        print("=" * 60)
        print("[TEST] Starting components...")
        cloud = subprocess.Popen(
            [VENV_PYTHON, "cloud_server.py"],
            cwd=BASE_DIR,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        processes.append(("Cloud", cloud))
        time.sleep(2)
        print("[TEST] Cloud Server started")

        for name, script in [
            ("AC", "air_conditioner.py"),
            ("LB", "light_bulb.py"),
            ("SS", "smart_socket.py"),
        ]:
            p = subprocess.Popen(
                [VENV_PYTHON, f"devices/{script}"],
                cwd=BASE_DIR,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            processes.append((name, p))
            time.sleep(0.5)
        print("[TEST] 3 devices started")
        time.sleep(2)

        # 2. 测试用户
        print("\n" + "=" * 60)
        print("[TEST] Starting user simulation")
        print("=" * 60)

        user = TestUser("user_001")
        user.connect()
        time.sleep(1)

        # --- Test 1: Bind AC ---
        print("\n[TEST 1] Bind ac_001...")
        user.bind_device("ac_001")
        time.sleep(1)
        if user.responses:
            resp = user.responses[-1]
            print(f"  Cloud: success={resp['success']} msg={resp['message']}")
            if resp["success"]:
                print(f"  {PASS} Bind ac_001 OK")
            else:
                print(f"  {FAIL} Bind failed: {resp['message']}")
                all_passed = False
        else:
            print(f"  {FAIL} No response from cloud!")
            all_passed = False

        # --- Test 2: Turn on AC ---
        print("\n[TEST 2] Turn on ac_001...")
        user.control_device("ac_001", "on")
        time.sleep(1.5)

        found_ac = False
        for resp in user.responses:
            print(f"  Cloud response: {resp['message']}")
        for st in user.statuses:
            print(f"  Status: device={st.get('device_id')}, is_on={st['status'].get('is_on')}")
            if st.get('device_id') == 'ac_001':
                found_ac = True
                if st['status'].get('is_on'):
                    print(f"  {PASS} AC is ON")
                else:
                    print(f"  {FAIL} AC still OFF!")
                    all_passed = False
        if not found_ac:
            print(f"  {FAIL} No status update from AC! Device may not be running.")
            all_passed = False

        # --- Test 3: Set temperature ---
        print("\n[TEST 3] Set AC temperature to 22...")
        user.control_device("ac_001", "set_temperature", {"temperature": 22})
        time.sleep(1.5)
        for st in user.statuses:
            temp = st['status'].get('temperature')
            print(f"  Status: temperature={temp}")
            if temp == 22:
                print(f"  {PASS} Temperature set to 22")
            else:
                print(f"  {FAIL} Temperature is {temp}, expected 22")
                all_passed = False

        # --- Test 4: Bind and control LB ---
        print("\n[TEST 4] Bind and turn on lb_001...")
        user.bind_device("lb_001")
        time.sleep(1)
        for resp in user.responses:
            print(f"  Bind: {resp['message']}")

        user.control_device("lb_001", "on")
        time.sleep(1.5)
        found_lb = False
        for st in user.statuses:
            print(f"  Status: device={st.get('device_id')}, is_on={st['status'].get('is_on')}")
            if st.get('device_id') == 'lb_001':
                found_lb = True
                if st['status'].get('is_on'):
                    print(f"  {PASS} LightBulb is ON")
                else:
                    print(f"  {FAIL} LightBulb still OFF!")
                    all_passed = False
        if not found_lb:
            print(f"  {FAIL} No status from LightBulb")
            all_passed = False

        # --- Test 5: Set brightness ---
        print("\n[TEST 5] Set brightness to 50...")
        user.control_device("lb_001", "set_brightness", {"brightness": 50})
        time.sleep(1.5)
        for st in user.statuses:
            b = st['status'].get('brightness')
            print(f"  Status: brightness={b}")
            if b == 50:
                print(f"  {PASS} Brightness set to 50")
            else:
                print(f"  {FAIL} Brightness is {b}, expected 50")
                all_passed = False

        # --- Test 6: Bind and control SS ---
        print("\n[TEST 6] Bind and turn on ss_001...")
        user.bind_device("ss_001")
        time.sleep(1)
        user.control_device("ss_001", "on")
        time.sleep(1.5)
        for st in user.statuses:
            print(f"  Status: is_on={st['status'].get('is_on')}")
            if st['status'].get('is_on'):
                print(f"  {PASS} SmartSocket is ON")

        # --- Test 7: Set eco mode ---
        print("\n[TEST 7] Set power_mode to eco...")
        user.control_device("ss_001", "set_power_mode", {"mode": "eco"})
        time.sleep(1.5)
        for st in user.statuses:
            mode = st['status'].get('power_mode')
            print(f"  Status: power_mode={mode}")
            if mode == 'eco':
                print(f"  {PASS} Power mode set to eco")
            else:
                print(f"  {FAIL} Power mode is {mode}, expected eco")
                all_passed = False

        # --- Test 8: Unbind device ---
        print("\n[TEST 8] Unbind lb_001...")
        user.unbind_device("lb_001")
        time.sleep(1)
        for resp in user.responses:
            print(f"  Cloud: {resp['message']}")
            if resp["success"]:
                print(f"  {PASS} Unbind OK")
            else:
                print(f"  {FAIL} Unbind failed!")
                all_passed = False

        # Try to control unbound device - should fail
        user.control_device("lb_001", "on")
        time.sleep(1)
        for resp in user.responses:
            print(f"  Control after unbind: {resp['message']}")
            if not resp["success"]:
                print(f"  {PASS} Control of unbound device correctly rejected")
            else:
                print(f"  {FAIL} Should not allow control after unbind!")
                all_passed = False

        # --- Test 9: Turn off remaining ---
        print("\n[TEST 9] Turn off remaining devices...")
        for did in ["ac_001", "ss_001"]:
            user.control_device(did, "off")
            time.sleep(1)
        time.sleep(1)

        # --- Summary ---
        print("\n" + "=" * 60)
        if all_passed:
            print("[RESULT] ALL TESTS PASSED")
        else:
            print("[RESULT] SOME TESTS FAILED - check above")
        print("=" * 60)

        user.disconnect()

    except Exception as e:
        print(f"\n[TEST] Error: {e}")
        import traceback
        traceback.print_exc()
        all_passed = False

    finally:
        print("\n[TEST] Stopping processes...")
        for name, p in processes:
            p.terminate()
        time.sleep(1)
        for name, p in processes:
            if p.poll() is None:
                p.kill()
        print("[TEST] Cleanup done")

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
