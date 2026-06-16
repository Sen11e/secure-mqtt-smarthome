"""
快速启动所有组件的脚本
"""
import subprocess
import sys
import os
import time

def get_venv_python():
    """获取虚拟环境中的Python路径"""
    if os.name == 'nt':
        return os.path.join('venv', 'Scripts', 'python.exe')
    return os.path.join('venv', 'bin', 'python')

def main():
    print("="*60)
    print("物联网智能家居系统 - MQTT加密通信")
    print("="*60)
    print("\n启动顺序:")
    print("  1. MQTT Broker (Mosquitto)")
    print("  2. 云端服务器 (Cloud Server)")
    print("  3. 物联网设备 (3个设备)")
    print("  4. 用户客户端 (User Client)")
    print("\n" + "="*60)

    processes = []

    try:
        # 启动云端服务器
        print("\n[1] 启动云端服务器...")
        p1 = subprocess.Popen(
            [get_venv_python(), "cloud_server.py"],
            cwd=os.path.dirname(os.path.abspath(__file__))
        )
        processes.append(("Cloud Server", p1))
        time.sleep(1)

        # 启动设备
        print("[2] 启动物联网设备...")
        devices = ["air_conditioner.py", "light_bulb.py", "smart_socket.py"]
        for device_file in devices:
            p = subprocess.Popen(
                [get_venv_python(), f"devices/{device_file}"],
                cwd=os.path.dirname(os.path.abspath(__file__))
            )
            processes.append((device_file, p))
            time.sleep(0.5)

        # 启动用户客户端
        print("[3] 启动用户客户端...")
        p4 = subprocess.Popen(
            [get_venv_python(), "user_client.py"],
            cwd=os.path.dirname(os.path.abspath(__file__))
        )
        processes.append(("User Client", p4))

        print("\n" + "="*60)
        print("所有组件已启动!")
        print("按 Ctrl+C 停止所有服务")
        print("="*60)

        # 等待所有进程
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        print("\n\n正在停止所有服务...")
        for name, p in processes:
            print(f"  停止 {name}...")
            p.terminate()
        print("所有服务已停止")

if __name__ == "__main__":
    main()