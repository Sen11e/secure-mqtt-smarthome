# ============================================
# 2. device_manager.py - 设备管理模块
# ============================================
"""
设备管理模块
支持设备注册、配网流程、设备发现
"""

import secrets
import time
from typing import Dict, Optional, List, Any
from dataclasses import dataclass, field
from enum import Enum


class DeviceType(Enum):
    """设备类型"""
    AIR_CONDITIONER = "air_conditioner"
    LIGHT_BULB = "light_bulb"
    SMART_SOCKET = "smart_socket"
    SENSOR = "sensor"
    OTHER = "other"


class DeviceStatus(Enum):
    """设备状态"""
    UNREGISTERED = "unregistered"  # 未注册
    PROVISIONING = "provisioning"  # 配网中
    ONLINE = "online"  # 在线
    OFFLINE = "offline"  # 离线
    DISABLED = "disabled"  # 已禁用


@dataclass
class Device:
    """设备数据结构"""
    device_id: str
    device_name: str
    device_type: DeviceType
    mac_address: str
    product_key: str  # 产品密钥
    device_secret: str  # 设备密钥（用于通信加密）
    status: DeviceStatus
    registered_at: float
    last_seen: float
    owner_id: Optional[str] = None  # 所有者用户ID
    shared_with: Dict[str, str] = field(default_factory=dict)  # user_id -> permission
    wifi_ssid: Optional[str] = None  # 配网信息
    firmware_version: str = "1.0.0"
    properties: Dict[str, Any] = field(default_factory=dict)  # 设备属性


@dataclass
class ProvisioningSession:
    """配网会话"""
    session_id: str
    device_id: str
    wifi_ssid: str
    wifi_password: str
    created_at: float
    expires_at: float


class DeviceManager:
    """设备管理器 - 支持注册、配网、发现"""

    def __init__(self):
        self.devices: Dict[str, Device] = {}
        self.provisioning_sessions: Dict[str, ProvisioningSession] = {}
        self._init_default_devices()

    def _init_default_devices(self):
        """初始化默认设备（向后兼容）"""
        default_devices = [
            ("ac_001", "客厅空调", DeviceType.AIR_CONDITIONER, "AA:BB:CC:DD:EE:01",
             "product_ac_001", secrets.token_hex(16)),
            ("lb_001", "卧室灯泡", DeviceType.LIGHT_BULB, "AA:BB:CC:DD:EE:02",
             "product_lb_001", secrets.token_hex(16)),
            ("ss_001", "智能插座", DeviceType.SMART_SOCKET, "AA:BB:CC:DD:EE:03",
             "product_ss_001", secrets.token_hex(16)),
        ]

        for device_id, name, dtype, mac, pk, secret in default_devices:
            if device_id not in self.devices:
                self.devices[device_id] = Device(
                    device_id=device_id,
                    device_name=name,
                    device_type=dtype,
                    mac_address=mac,
                    product_key=pk,
                    device_secret=secret,
                    status=DeviceStatus.ONLINE,
                    registered_at=time.time(),
                    last_seen=time.time()
                )

    def register_device(self, mac_address: str, device_type: DeviceType,
                        product_key: str, device_name: str = None) -> Optional[str]:
        """
        设备注册 - 设备首次上线时调用
        返回: device_id (成功) 或 None (失败)
        """
        # 检查设备是否已注册
        for device in self.devices.values():
            if device.mac_address == mac_address:
                # 已注册设备重新上线
                if device.status == DeviceStatus.UNREGISTERED:
                    device.status = DeviceStatus.ONLINE
                device.last_seen = time.time()
                print(f"[DeviceManager] 设备重新上线: {device.device_id}")
                return device.device_id

        # 新设备注册
        device_id = f"dev_{secrets.token_hex(4)}"
        if device_name is None:
            device_name = f"{device_type.value}_{device_id[-4:]}"

        device_secret = secrets.token_hex(32)

        device = Device(
            device_id=device_id,
            device_name=device_name,
            device_type=device_type,
            mac_address=mac_address,
            product_key=product_key,
            device_secret=device_secret,
            status=DeviceStatus.ONLINE,
            registered_at=time.time(),
            last_seen=time.time()
        )

        self.devices[device_id] = device
        print(f"[DeviceManager] 新设备注册: {device_id} ({device_name}) MAC:{mac_address}")
        return device_id

    def start_provisioning(self, device_id: str, wifi_ssid: str,
                           wifi_password: str) -> Optional[str]:
        """
        启动设备配网流程
        返回: session_id (成功) 或 None (失败)
        """
        device = self.get_device(device_id)
        if not device:
            return None

        session_id = secrets.token_urlsafe(16)
        session = ProvisioningSession(
            session_id=session_id,
            device_id=device_id,
            wifi_ssid=wifi_ssid,
            wifi_password=wifi_password,
            created_at=time.time(),
            expires_at=time.time() + 300  # 5分钟过期
        )

        self.provisioning_sessions[session_id] = session
        device.status = DeviceStatus.PROVISIONING
        device.wifi_ssid = wifi_ssid

        print(f"[DeviceManager] 启动配网: {device_id} -> WiFi:{wifi_ssid}")
        return session_id

    def complete_provisioning(self, session_id: str, device_id: str) -> bool:
        """
        完成配网 - 设备连接WiFi后调用
        """
        session = self.provisioning_sessions.get(session_id)
        if not session:
            return False

        if session.device_id != device_id:
            return False

        if time.time() > session.expires_at:
            # 会话过期
            del self.provisioning_sessions[session_id]
            return False

        device = self.get_device(device_id)
        if device:
            device.status = DeviceStatus.ONLINE
            device.last_seen = time.time()

        del self.provisioning_sessions[session_id]
        print(f"[DeviceManager] 配网完成: {device_id}")
        return True

    def get_device(self, device_id: str) -> Optional[Device]:
        """获取设备信息"""
        return self.devices.get(device_id)

    def get_device_by_mac(self, mac_address: str) -> Optional[Device]:
        """通过MAC地址获取设备"""
        for device in self.devices.values():
            if device.mac_address == mac_address:
                return device
        return None

    def list_devices(self, user_id: str = None) -> List[Device]:
        """
        列出设备
        如果提供user_id，只返回该用户拥有或分享的设备
        """
        if user_id is None:
            return list(self.devices.values())

        accessible = []
        for device in self.devices.values():
            # 设备所有者
            if device.owner_id == user_id:
                accessible.append(device)
            # 设备被分享给该用户
            elif user_id in device.shared_with:
                accessible.append(device)

        return accessible

    def update_device_status(self, device_id: str, status: DeviceStatus) -> bool:
        """更新设备状态"""
        device = self.get_device(device_id)
        if device:
            device.status = status
            device.last_seen = time.time()
            return True
        return False

    def get_device_secret(self, device_id: str) -> Optional[str]:
        """获取设备密钥（用于通信加密）"""
        device = self.get_device(device_id)
        return device.device_secret if device else None

    def discover_devices(self, timeout: int = 5) -> List[Dict]:
        """
        设备发现 - 模拟扫描局域网内的新设备
        实际实现中可以通过UDP广播或mDNS实现
        """
        # 模拟发现新设备
        discovered = []
        # 扫描未注册的设备（这里用模拟数据）
        mock_new_devices = [
            {"mac": "11:22:33:44:55:66", "type": DeviceType.SENSOR, "name": "温湿度传感器"},
            {"mac": "77:88:99:AA:BB:CC", "type": DeviceType.OTHER, "name": "智能门锁"},
        ]

        for mock in mock_new_devices:
            existing = self.get_device_by_mac(mock["mac"])
            if not existing:
                discovered.append(mock)

        return discovered