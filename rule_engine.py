# ============================================
# 3. rule_engine.py - 自动化规则引擎
# ============================================
"""
设备间自动化规则引擎
支持：如果-那么 规则，设备间联动
"""

import json
import threading
import time
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum


class Operator(Enum):
    """比较操作符"""
    EQ = "=="
    NE = "!="
    GT = ">"
    LT = "<"
    GTE = ">="
    LTE = "<="
    CHANGED = "changed"


class ActionType(Enum):
    """动作类型"""
    CONTROL_DEVICE = "control_device"  # 控制设备
    SEND_NOTIFICATION = "send_notification"  # 发送通知
    DELAY = "delay"  # 延迟执行
    TRIGGER_RULE = "trigger_rule"  # 触发另一个规则


@dataclass
class Condition:
    """规则条件"""
    device_id: str
    property_name: str  # 如 temperature, power_state
    operator: Operator
    value: Any


@dataclass
class Action:
    """规则动作"""
    action_type: ActionType
    target_device_id: Optional[str] = None
    command: Optional[str] = None
    params: Optional[Dict] = None
    delay_ms: int = 0  # 延迟执行（毫秒）
    notification: Optional[str] = None


@dataclass
class Rule:
    """自动化规则"""
    rule_id: str
    name: str
    enabled: bool
    conditions: List[Condition]
    actions: List[Action]
    created_by: str
    created_at: float
    trigger_count: int = 0


class RuleEngine:
    """规则引擎 - 处理设备间自动化联动"""

    def __init__(self):
        self.rules: Dict[str, Rule] = {}
        self.device_state_listeners: Dict[str, List[Callable]] = {}
        self._running = True
        self._action_queue = []
        self._lock = threading.Lock()

        # 启动后台线程处理延迟动作
        self._worker = threading.Thread(target=self._process_actions, daemon=True)
        self._worker.start()

        # 添加示例规则
        self._init_example_rules()

    def _init_example_rules(self):
        """初始化示例规则"""
        # 规则1: 温度过高自动开空调
        rule1 = Rule(
            rule_id="rule_001",
            name="高温自动开空调",
            enabled=True,
            conditions=[
                Condition(
                    device_id="temp_sensor_001",
                    property_name="temperature",
                    operator=Operator.GT,
                    value=28
                )
            ],
            actions=[
                Action(
                    action_type=ActionType.CONTROL_DEVICE,
                    target_device_id="ac_001",
                    command="on",
                    params={}
                ),
                Action(
                    action_type=ActionType.SEND_NOTIFICATION,
                    notification="温度超过28℃，已自动开启空调"
                )
            ],
            created_by="system",
            created_at=time.time()
        )
        self.rules[rule1.rule_id] = rule1

        # 规则2: 人走灯灭（模拟）
        rule2 = Rule(
            rule_id="rule_002",
            name="人走灯灭",
            enabled=False,  # 默认禁用，需要传感器
            conditions=[
                Condition(
                    device_id="motion_sensor_001",
                    property_name="motion_detected",
                    operator=Operator.EQ,
                    value=False
                ),
                Condition(
                    device_id="motion_sensor_001",
                    property_name="no_motion_duration",
                    operator=Operator.GTE,
                    value=300
                )
            ],
            actions=[
                Action(
                    action_type=ActionType.CONTROL_DEVICE,
                    target_device_id="lb_001",
                    command="off",
                    params={}
                )
            ],
            created_by="system",
            created_at=time.time()
        )
        self.rules[rule2.rule_id] = rule2

    def add_rule(self, rule: Rule) -> str:
        """添加规则"""
        self.rules[rule.rule_id] = rule
        print(f"[RuleEngine] 添加规则: {rule.name} ({rule.rule_id})")
        return rule.rule_id

    def remove_rule(self, rule_id: str) -> bool:
        """删除规则"""
        if rule_id in self.rules:
            del self.rules[rule_id]
            print(f"[RuleEngine] 删除规则: {rule_id}")
            return True
        return False

    def enable_rule(self, rule_id: str, enabled: bool) -> bool:
        """启用/禁用规则"""
        if rule_id in self.rules:
            self.rules[rule_id].enabled = enabled
            print(f"[RuleEngine] 规则 {rule_id} 启用状态: {enabled}")
            return True
        return False

    def on_device_state_change(self, device_id: str, property_name: str,
                               new_value: Any, old_value: Any = None):
        """
        设备状态变化时的回调
        触发规则评估
        """
        # 调用监听器
        if device_id in self.device_state_listeners:
            for listener in self.device_state_listeners[device_id]:
                listener(device_id, property_name, new_value, old_value)

        # 评估所有规则
        self._evaluate_rules(device_id, property_name, new_value, old_value)

    def _evaluate_rules(self, device_id: str, property_name: str,
                        new_value: Any, old_value: Any):
        """评估哪些规则被触发"""
        for rule in self.rules.values():
            if not rule.enabled:
                continue

            # 检查条件是否满足
            conditions_met = True
            for condition in rule.conditions:
                # 简化处理：只检查条件中涉及的设备
                if condition.device_id == device_id:
                    met = self._check_condition(condition, new_value, old_value)
                    if not met:
                        conditions_met = False
                        break
                # 其他设备的状态需要从设备管理器获取
                # 这里简化处理，实际需要查询设备当前状态

            if conditions_met:
                # 触发规则动作
                self._trigger_rule(rule)

    def _check_condition(self, condition: Condition, value: Any, old_value: Any) -> bool:
        """检查单个条件是否满足"""
        if condition.operator == Operator.CHANGED:
            return old_value is not None and value != old_value

        ops = {
            Operator.EQ: lambda v, c: v == c,
            Operator.NE: lambda v, c: v != c,
            Operator.GT: lambda v, c: v > c,
            Operator.LT: lambda v, c: v < c,
            Operator.GTE: lambda v, c: v >= c,
            Operator.LTE: lambda v, c: v <= c,
        }

        if condition.operator in ops:
            return ops[condition.operator](value, condition.value)

        return False

    def _trigger_rule(self, rule: Rule):
        """触发规则动作"""
        rule.trigger_count += 1
        print(f"[RuleEngine] 触发规则: {rule.name} (触发次数: {rule.trigger_count})")

        for action in rule.actions:
            self._execute_action(action)

    def _execute_action(self, action: Action):
        """执行动作"""
        if action.delay_ms > 0:
            # 延迟执行
            with self._lock:
                self._action_queue.append((action, time.time() + action.delay_ms / 1000))
        else:
            self._do_action(action)

    def _do_action(self, action: Action):
        """立即执行动作"""
        if action.action_type == ActionType.CONTROL_DEVICE:
            # 发送设备控制命令
            self._send_device_command(action.target_device_id, action.command, action.params)
        elif action.action_type == ActionType.SEND_NOTIFICATION:
            # 发送通知
            print(f"[RuleEngine][通知] {action.notification}")
        elif action.action_type == ActionType.DELAY:
            # 延迟已在外部处理
            pass
        elif action.action_type == ActionType.TRIGGER_RULE:
            # 触发另一个规则
            if action.target_device_id in self.rules:
                self._trigger_rule(self.rules[action.target_device_id])

    def _send_device_command(self, device_id: str, command: str, params: Dict):
        """发送设备控制命令（通过MQTT）"""
        # 实际实现中通过MQTT发布命令
        print(f"[RuleEngine] 发送设备命令: {device_id} -> {command} {params}")
        # 这里可以调用MQTT发布接口

    def _process_actions(self):
        """后台线程处理延迟动作"""
        while self._running:
            time.sleep(0.1)
            now = time.time()
            with self._lock:
                new_queue = []
                for action, execute_time in self._action_queue:
                    if now >= execute_time:
                        self._do_action(action)
                    else:
                        new_queue.append((action, execute_time))
                self._action_queue = new_queue

    def add_listener(self, device_id: str, listener: Callable):
        """添加设备状态监听器"""
        if device_id not in self.device_state_listeners:
            self.device_state_listeners[device_id] = []
        self.device_state_listeners[device_id].append(listener)

    def get_rules(self) -> List[Dict]:
        """获取所有规则"""
        return [
            {
                "rule_id": r.rule_id,
                "name": r.name,
                "enabled": r.enabled,
                "conditions": [
                    {"device_id": c.device_id, "property": c.property_name,
                     "operator": c.operator.value, "value": c.value}
                    for c in r.conditions
                ],
                "actions": [
                    {"type": a.action_type.value, "target": a.target_device_id,
                     "command": a.command, "notification": a.notification}
                    for a in r.actions
                ],
                "trigger_count": r.trigger_count,
                "created_by": r.created_by
            }
            for r in self.rules.values()
        ]