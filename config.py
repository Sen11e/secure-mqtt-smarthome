# ============================================
# config.py - 完整配置
# ============================================

# MQTT Broker 配置
BROKER_HOST = "localhost"  # 本机测试，部署时改为实际IP
BROKER_PORT = 1883

# MQTT 主题
TOPICS = {
    # 设备相关
    "device_command": "device/command",
    "device_command_response": "device/command/response",
    "device_status": "device/status",
    "device_register": "device/register",
    "device_register_response": "device/register/response",
    "device_provisioning": "device/provisioning",
    "device_provisioning_response": "device/provisioning/response",

    # 用户相关
    "user_command": "user/command",
    "user_command_response": "user/response",
    "user_login": "user/login",
    "user_logout": "user/logout",

    # 系统相关
    "system_broadcast": "system/broadcast",
}

# 设备ID配置（向后兼容）
DEVICE_IDS = {
    "air_conditioner": "ac_001",
    "light_bulb": "lb_001",
    "smart_socket": "ss_001",
}

# 设备类型
DEVICE_TYPES = {
    "ac_001": "air_conditioner",
    "lb_001": "light_bulb",
    "ss_001": "smart_socket",
}

# 密钥（生产环境需更改）
SECRET_KEY = b"smart-home-secret-key-2024"

# 安全配置
HMAC_KEY = b"smart-home-hmac-key-2024"
TIME_WINDOW = 300  # 5分钟时间窗口

# 日志配置
LOG_LEVEL = "INFO"
LOG_FILE = "smart_home.log"

# 数据库配置（可选）
DATABASE_URL = "sqlite:///smart_home.db"

# Web UI 配置
WEB_HOST = "0.0.0.0"
WEB_PORT = 8501