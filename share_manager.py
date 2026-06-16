# ============================================
# 4. share_manager.py - 设备分享模块
# ============================================
"""
设备分享管理模块
支持设备分享给其他用户、权限管理
"""

import secrets
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum


class SharePermission(Enum):
    """分享权限级别"""
    READ_ONLY = "read_only"  # 只读：只能查看状态
    CONTROL = "control"  # 可控：可以控制设备
    ADMIN = "admin"  # 管理：可以修改设备配置、分享给他人


@dataclass
class DeviceShare:
    """设备分享记录"""
    share_id: str
    device_id: str
    owner_id: str  # 设备所有者
    target_user_id: str  # 被分享的用户
    permission: SharePermission
    created_at: float
    expires_at: Optional[float] = None  # 过期时间，None表示永不过期
    notes: str = ""


@dataclass
class ShareInvitation:
    """分享邀请（待接受）"""
    invitation_id: str
    device_id: str
    device_name: str
    from_user_id: str
    from_username: str
    to_user_id: str
    permission: SharePermission
    created_at: float
    expires_at: float
    status: str  # pending, accepted, rejected, expired


class ShareManager:
    """设备分享管理器"""

    def __init__(self):
        self.shares: Dict[str, DeviceShare] = {}  # share_id -> DeviceShare
        self.device_shares: Dict[str, List[str]] = {}  # device_id -> [share_ids]
        self.user_shares: Dict[str, List[str]] = {}  # user_id -> [share_ids]
        self.invitations: Dict[str, ShareInvitation] = {}  # invitation_id -> Invitation

        # 添加示例分享记录
        self._init_example_shares()

    def _init_example_shares(self):
        """初始化示例分享记录"""
        pass

    def share_device(self, owner_id: str, target_user_id: str,
                     device_id: str, permission: SharePermission,
                     expires_in: int = None, notes: str = "") -> Optional[str]:
        """
        分享设备给其他用户
        返回: share_id (成功) 或 None (失败)
        """
        # 检查所有者是否有权限分享
        # （实际应该验证owner_id确实是设备所有者）

        share_id = f"share_{secrets.token_hex(8)}"
        expires_at = time.time() + expires_in if expires_in else None

        share = DeviceShare(
            share_id=share_id,
            device_id=device_id,
            owner_id=owner_id,
            target_user_id=target_user_id,
            permission=permission,
            created_at=time.time(),
            expires_at=expires_at,
            notes=notes
        )

        self.shares[share_id] = share

        # 建立索引
        if device_id not in self.device_shares:
            self.device_shares[device_id] = []
        self.device_shares[device_id].append(share_id)

        if target_user_id not in self.user_shares:
            self.user_shares[target_user_id] = []
        self.user_shares[target_user_id].append(share_id)

        print(f"[ShareManager] 设备分享: {owner_id} -> {target_user_id} 设备:{device_id}")
        return share_id

    def unshare_device(self, share_id: str, owner_id: str) -> bool:
        """取消设备分享"""
        share = self.shares.get(share_id)
        if not share or share.owner_id != owner_id:
            return False

        # 从索引中移除
        if share.device_id in self.device_shares:
            self.device_shares[share.device_id] = [
                sid for sid in self.device_shares[share.device_id] if sid != share_id
            ]

        if share.target_user_id in self.user_shares:
            self.user_shares[share.target_user_id] = [
                sid for sid in self.user_shares[share.target_user_id] if sid != share_id
            ]

        del self.shares[share_id]
        print(f"[ShareManager] 取消分享: {share_id}")
        return True

    def get_shared_devices(self, user_id: str) -> List[Dict]:
        """
        获取分享给某用户的所有设备
        """
        shared = []
        share_ids = self.user_shares.get(user_id, [])

        for share_id in share_ids:
            share = self.shares.get(share_id)
            if share:
                # 检查是否过期
                if share.expires_at and time.time() > share.expires_at:
                    continue

                shared.append({
                    "share_id": share.share_id,
                    "device_id": share.device_id,
                    "permission": share.permission.value,
                    "owner_id": share.owner_id,
                    "created_at": share.created_at,
                    "expires_at": share.expires_at
                })

        return shared

    def get_device_shares(self, device_id: str, owner_id: str) -> List[Dict]:
        """获取设备的所有分享信息"""
        shares = []
        share_ids = self.device_shares.get(device_id, [])

        for share_id in share_ids:
            share = self.shares.get(share_id)
            if share and share.owner_id == owner_id:
                shares.append({
                    "share_id": share.share_id,
                    "target_user_id": share.target_user_id,
                    "permission": share.permission.value,
                    "created_at": share.created_at
                })

        return shares

    def check_permission(self, user_id: str, device_id: str,
                         required_permission: SharePermission) -> bool:
        """
        检查用户是否有权限操作设备
        """
        # 先在DeviceManager中检查是否是所有者
        # 这里只检查分享权限

        share_ids = self.user_shares.get(user_id, [])
        for share_id in share_ids:
            share = self.shares.get(share_id)
            if share and share.device_id == device_id:
                if share.expires_at and time.time() > share.expires_at:
                    continue

                # 权限检查
                perm_order = {
                    SharePermission.READ_ONLY: 0,
                    SharePermission.CONTROL: 1,
                    SharePermission.ADMIN: 2
                }

                if perm_order.get(share.permission, -1) >= perm_order.get(required_permission, -1):
                    return True

        return False

    def create_invitation(self, from_user_id: str, to_user_id: str,
                          device_id: str, device_name: str,
                          permission: SharePermission,
                          expires_in: int = 86400) -> Optional[str]:
        """
        创建分享邀请
        """
        invitation_id = f"inv_{secrets.token_hex(8)}"

        invitation = ShareInvitation(
            invitation_id=invitation_id,
            device_id=device_id,
            device_name=device_name,
            from_user_id=from_user_id,
            from_username="",  # 需要填充用户名
            to_user_id=to_user_id,
            permission=permission,
            created_at=time.time(),
            expires_at=time.time() + expires_in,
            status="pending"
        )

        self.invitations[invitation_id] = invitation
        print(f"[ShareManager] 创建分享邀请: {invitation_id}")
        return invitation_id

    def accept_invitation(self, invitation_id: str, user_id: str) -> Optional[str]:
        """接受分享邀请"""
        invitation = self.invitations.get(invitation_id)
        if not invitation:
            return None

        if invitation.to_user_id != user_id:
            return None

        if invitation.status != "pending":
            return None

        if time.time() > invitation.expires_at:
            invitation.status = "expired"
            return None

        # 创建实际的分享
        share_id = self.share_device(
            owner_id=invitation.from_user_id,
            target_user_id=user_id,
            device_id=invitation.device_id,
            permission=invitation.permission
        )

        invitation.status = "accepted"
        print(f"[ShareManager] 接受分享邀请: {invitation_id}")
        return share_id

    def reject_invitation(self, invitation_id: str, user_id: str) -> bool:
        """拒绝分享邀请"""
        invitation = self.invitations.get(invitation_id)
        if not invitation or invitation.to_user_id != user_id:
            return False

        invitation.status = "rejected"
        print(f"[ShareManager] 拒绝分享邀请: {invitation_id}")
        return True

    def get_pending_invitations(self, user_id: str) -> List[Dict]:
        """获取待处理的分享邀请"""
        pending = []
        for inv in self.invitations.values():
            if inv.to_user_id == user_id and inv.status == "pending":
                if time.time() <= inv.expires_at:
                    pending.append({
                        "invitation_id": inv.invitation_id,
                        "device_id": inv.device_id,
                        "device_name": inv.device_name,
                        "from_user_id": inv.from_user_id,
                        "permission": inv.permission.value,
                        "created_at": inv.created_at
                    })
        return pending