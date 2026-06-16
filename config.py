# ============================================
# config.py
# ============================================

# MQTT Broker 配置
BROKER_HOST = "localhost"
BROKER_PORT = 1883

# 密钥（所有设备必须使用相同的密钥）
SECRET_KEY = b"smart-home-secret-key-2024"

# MQTT 主题 - 统一定义
TOPICS = {
    # 设备相关
    "device_command": "device/command",
    "device_status": "device/status",
    "device_register": "device/register",
    "device_register_response": "device/register/response",

    # 用户相关
    "user_command": "user/command",
    "user_command_response": "user/response",
}

# 设备ID配置
DEVICE_IDS = {
    "air_conditioner": "ac_001",
    "light_bulb": "lb_001",
    "smart_socket": "ss_001",
}