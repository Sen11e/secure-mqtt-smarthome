"""
用户客户端 - 命令行界面
"""
import json
import time
import paho.mqtt.client as mqtt
from typing import Dict, Any, Optional
import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import config
import crypto_utils
import message_format


class UserClient:
    """用户客户端"""

    def __init__(self, user_id: str, secret_key: str):
        self.user_id = user_id
        self.secret_key = secret_key
        self.devices: Dict[str, Dict[str, Any]] = {}  # device_id -> status
        self.last_seq: Optional[int] = None  # 防重放：最近一次接受的来自云端的序列号
        self._waiting_input = False

        self.client = mqtt.Client(client_id=f"user_{user_id}_{os.getpid()}", callback_api_version=mqtt.CallbackAPIVersion.VERSION1)
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            print(f"[User {self.user_id}] 连接MQTT成功")
            client.subscribe(f"home/{self.user_id}/from_cloud")
        else:
            print(f"[User {self.user_id}] 连接MQTT失败, rc={rc}")

    def _on_message(self, client, userdata, msg):
        try:
            data = json.loads(msg.payload.decode())
            topic = msg.topic

            if topic.endswith("/from_cloud"):
                self._handle_cloud_message(data)
        except Exception as e:
            print(f"[User {self.user_id}] 处理消息错误: {e}")

    def _handle_cloud_message(self, data: Dict[str, Any]):
        """处理云端消息"""
        seq_num = data.get("seq_num")
        timestamp = data.get("timestamp")
        payload = data.get("payload", {})
        signature = data.get("signature")

        # 验证签名（主要安全机制）
        if not crypto_utils.verify_signature(
            self.secret_key, seq_num, timestamp, payload, signature
        ):
            if not self._waiting_input:
                print(f"\n[User {self.user_id}] 签名验证失败!")
            return

        # 检查时间戳（防重放攻击）
        if not crypto_utils.check_timestamp(timestamp, config.TIME_WINDOW):
            if not self._waiting_input:
                print(f"\n[User {self.user_id}] 时间戳验证失败!")
            return

        # 检查序列号（防同窗口内重放）
        if not crypto_utils.check_seq_num(seq_num, self.last_seq):
            if not self._waiting_input:
                print(f"\n[User {self.user_id}] 重放消息: 序列号过期或重复 (seq={seq_num}, last={self.last_seq})")
            return
        self.last_seq = seq_num

        # 判断消息类型
        msg_type = payload.get("type")
        if msg_type == message_format.MessageType.DEVICE_STATUS.value:
            self._update_device_status(payload)
        elif "success" in payload:
            # 响应消息
            success = payload.get("success")
            message = payload.get("message")
            data = payload.get("data", {})
            if success:
                if not self._waiting_input:
                    print(f"\n[User {self.user_id}] success: {message}")
                # 如果是绑定成功，立即添加到本地设备列表
                if "绑定成功" in message:
                    device_id = data.get("device_id")
                    if device_id and device_id not in self.devices:
                        # 从配置反查设备类型，避免依赖异步状态更新
                        device_type = "unknown"
                        for dtype, did in config.DEVICE_IDS.items():
                            if did == device_id:
                                device_type = dtype
                                break
                        self.devices[device_id] = {"type": device_type, "status": {}}
                elif "解绑成功" in message:
                    device_id = data.get("device_id")
                    if device_id and device_id in self.devices:
                        del self.devices[device_id]
            else:
                if not self._waiting_input:
                    print(f"\n[User {self.user_id}] failed: {message}")

    def _update_device_status(self, payload: Dict[str, Any]):
        """更新设备状态（仅更新已绑定/已知设备）"""
        device_id = payload.get("device_id")
        if device_id not in self.devices:
            return
        device_type = payload.get("device_type")
        status = payload.get("status", {})

        self.devices[device_id] = {
            "type": device_type,
            "status": status
        }

        if not self._waiting_input:
            print(f"\n[User {self.user_id}] 收到设备状态更新:")
            print(f"  设备ID: {device_id}")
            print(f"  设备类型: {device_type}")
            print(f"  状态: {status}")

    def send_command(self, device_id: str, command: str, params: Dict[str, Any] = None):
        """发送控制命令"""
        payload = message_format.create_control_message(device_id, command, params)
        signed_msg = crypto_utils.create_signed_message(
            self.secret_key,
            message_format.seq_manager.get_next(),
            payload
        )
        self.client.publish(
            f"home/{self.user_id}/to_cloud",
            json.dumps(signed_msg)
        )

    def bind_device(self, device_id: str):
        """绑定设备"""
        payload = message_format.create_bind_message(self.user_id, device_id)
        signed_msg = crypto_utils.create_signed_message(
            self.secret_key,
            message_format.seq_manager.get_next(),
            payload
        )
        self.client.publish(
            f"home/{self.user_id}/to_cloud",
            json.dumps(signed_msg)
        )

    def unbind_device(self, device_id: str):
        """解绑设备"""
        payload = message_format.create_unbind_message(self.user_id, device_id)
        signed_msg = crypto_utils.create_signed_message(
            self.secret_key,
            message_format.seq_manager.get_next(),
            payload
        )
        self.client.publish(
            f"home/{self.user_id}/to_cloud",
            json.dumps(signed_msg)
        )

    def start(self):
        """启动客户端"""
        print(f"[User {self.user_id}] 启动用户客户端...")
        self.client.connect(config.BROKER_HOST, config.BROKER_PORT)
        self.client.loop_start()
        print(f"[User {self.user_id}] 用户客户端已启动")

    def stop(self):
        """停止客户端"""
        self.client.loop_stop()
        self.client.disconnect()
        print(f"[User {self.user_id}] 用户客户端已停止")

    def safe_input(self, prompt: str = "") -> str:
        """带输入保护标志的 input()，防止异步消息打印打断输入"""
        self._waiting_input = True
        try:
            return input(prompt)
        finally:
            self._waiting_input = False

    def print_menu(self):
        """打印菜单"""
        print(f"\n{'='*50}")
        print(f"用户 {self.user_id} 控制面板")
        print(f"{'='*50}")
        print("可用设备:")
        for device_id, info in self.devices.items():
            status = info.get("status", {})
            is_on = status.get("is_on", False)
            state = "ON" if is_on else "OFF"
            print(f"  [{state}] {device_id} ({info.get('type', 'unknown')})")

        print(f"\n操作选项:")
        print("  1. 绑定设备")
        print("  2. 解绑设备")
        print("  3. 控制设备")
        print("  4. 查看已绑定设备")
        print("  5. 刷新状态")
        print("  0. 退出")
        print(f"{'='*50}")


def main():
    """主函数"""
    print("="*50)
    print("物联网智能家居系统 - 用户端")
    print("="*50)
    print("\n可用用户ID:", config.USER_IDS)
    print("可用设备ID:", list(config.DEVICE_IDS.values()))

    # 选择用户ID
    user_id = input("\n请输入用户ID (例如 user_001): ").strip()  # 启动前不需要 safe_input
    if not user_id:
        user_id = "user_001"

    if user_id not in config.USER_IDS:
        print(f"警告: 用户 {user_id} 不在配置列表中, 将继续使用")

    client = UserClient(user_id, config.SECRET_KEY)
    client.start()

    print("\n已启动, 按菜单操作...")

    try:
        while True:
            client.print_menu()
            choice = client.safe_input("\n请选择操作: ").strip()

            if choice == "1":
                # 绑定设备
                print("\n可用设备:")
                for did in config.DEVICE_IDS.values():
                    print(f"  - {did}")
                device_id = client.safe_input("输入要绑定的设备ID: ").strip()
                if device_id:
                    client.bind_device(device_id)
                    time.sleep(0.5)
            elif choice == "2":
                # 解绑设备
                if not client.devices:
                    print("\n还没有绑定任何设备")
                    continue
                print("\n已绑定设备:")
                for did in client.devices.keys():
                    print(f"  - {did}")
                device_id = client.safe_input("输入要解绑的设备ID: ").strip()
                if device_id:
                    client.unbind_device(device_id)
                    time.sleep(0.5)
            elif choice == "3":
                # 控制设备
                if not client.devices:
                    print("\n还没有绑定任何设备,请先绑定设备")
                    continue
                print("\n已绑定设备:")
                for i, did in enumerate(client.devices.keys()):
                    print(f"  {i+1}. {did}")
                device_id = client.safe_input("输入设备ID: ").strip()
                if device_id not in client.devices:
                    print("设备未找到或未绑定")
                    continue

                device_type = client.devices[device_id].get("type", "")
                print(f"\n设备类型: {device_type}")
                print("命令选项:")

                if device_type == "air_conditioner":
                    print("  on - 开启")
                    print("  off - 关闭")
                    print("  set_temperature - 设置温度 (参数: temperature)")
                    cmd = client.safe_input("输入命令: ").strip()
                    if cmd == "set_temperature":
                        temp = client.safe_input("输入温度: ").strip()
                        client.send_command(device_id, cmd, {"temperature": int(temp)})
                    else:
                        client.send_command(device_id, cmd)
                    time.sleep(0.5)
                elif device_type == "light_bulb":
                    print("  on - 开启")
                    print("  off - 关闭")
                    print("  set_brightness - 设置亮度 (参数: brightness)")
                    cmd = client.safe_input("输入命令: ").strip()
                    if cmd == "set_brightness":
                        bright = client.safe_input("输入亮度(0-100): ").strip()
                        client.send_command(device_id, cmd, {"brightness": int(bright)})
                    else:
                        client.send_command(device_id, cmd)
                    time.sleep(0.5)
                elif device_type == "smart_socket":
                    print("  on - 开启")
                    print("  off - 关闭")
                    print("  set_power_mode - 设置功率模式 (参数: mode)")
                    cmd = client.safe_input("输入命令: ").strip()
                    if cmd == "set_power_mode":
                        mode = client.safe_input("输入模式(normal/eco): ").strip()
                        client.send_command(device_id, cmd, {"mode": mode})
                    else:
                        client.send_command(device_id, cmd)
                    time.sleep(0.5)
                else:
                    print(f"未知设备类型: {device_type}")
            elif choice == "4":
                # 查看已绑定设备
                if not client.devices:
                    print("\n还没有绑定任何设备")
                else:
                    print("\n已绑定设备:")
                    for did, info in client.devices.items():
                        print(f"  - {did} ({info.get('type', 'unknown')}): {info.get('status', {})}")
            elif choice == "5":
                # 刷新状态 - 发送空命令触发状态更新
                print("\n刷新设备状态...")
            elif choice == "0":
                break

    except KeyboardInterrupt:
        print("\n正在退出...")
    finally:
        client.stop()


if __name__ == "__main__":
    main()