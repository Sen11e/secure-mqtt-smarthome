"""
物联网智能家居安全通信系统 - Web 演示界面
streamlit run web_ui.py
"""
import streamlit as st
import json
import time
import sys
import os
import threading
from datetime import datetime

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import paho.mqtt.client as mqtt
import config
import crypto_utils
import message_format

# ── Page config ──────────────────────────────────────────
st.set_page_config(
    page_title="智能家居安全通信系统",
    page_icon="🏠",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Styles ───────────────────────────────────────────────
st.markdown("""
<style>
    .device-card {
        border: 1px solid #e0e0e0; border-radius: 12px; padding: 20px;
        margin-bottom: 12px; background: #fafafa;
    }
    .device-card.on { border-color: #4caf50; background: #f1f8e9; }
    .device-card.off { border-color: #e0e0e0; background: #fafafa; }
    .stButton button { width: 100%; }
</style>
""", unsafe_allow_html=True)

# ── Session state init ───────────────────────────────────
DEFAULTS = {
    "mqtt_ready": False,
    "user_id": "user_001",
    "devices": {},
    "messages": [],
    "bind_results": [],
    "last_seq": None,  # 防重放：最近一次接受的来自云端的序列号
}

for k, v in DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v


# ── Bridge (MQTT callbacks → st.session_state) ───────────
# CRITICAL: 必须存储在 st.session_state 中，不能作为模块级变量！
# Streamlit 每次 rerun 会重新执行脚本，模块级变量会被重建，
# 而 MQTT 回调函数在首次绑定时捕获的是旧的 bridge 引用。

def _get_bridge():
    if "_bridge" not in st.session_state:
        st.session_state._bridge = {
            "lock": threading.Lock(),
            "connected": False,
            "items": [],
            "last_seq": None,  # 防重放：与 st.session_state.last_seq 同步
        }
    return st.session_state._bridge


def _bridge_push(key, value):
    b = _get_bridge()
    with b["lock"]:
        b["items"].append((key, value))
        if key == "connected":
            b["connected"] = value


def drain_bridge():
    """处理 MQTT 消息并将桥接数据写入 st.session_state。每次 rerun 顶部调用。"""
    client = getattr(st.session_state, "_mqtt_client", None)
    if client is not None and st.session_state.get("mqtt_ready"):
        for _ in range(5):
            client.loop(timeout=0.01)
    b = _get_bridge()
    with b["lock"]:
        items, b["items"] = b["items"], []
    for key, value in items:
        if key == "error":
            st.error(value)
        elif key == "connected":
            st.session_state._mqtt_connected = value
        elif key == "disconnected":
            st.session_state._mqtt_connected = False
        elif key == "log":
            st.session_state.messages.append(value)
            if len(st.session_state.messages) > 50:
                st.session_state.messages = st.session_state.messages[-50:]
        elif key == "status":
            if not value.get("seq_ok", True):
                continue
            did = value.get("device_id", "")
            if did in st.session_state.devices:
                st.session_state.devices[did]["type"] = value.get("device_type", "")
                st.session_state.devices[did]["status"] = value.get("status", {})
        elif key == "response":
            if not value.get("seq_ok", True):
                continue
            st.session_state.bind_results.append(value)
            msg = value.get("message", "")
            df = value.get("data", {}) or {}
            if df and ("绑定成功" in msg or "设备已绑定" in msg):
                did = df.get("device_id")
                if did and did not in st.session_state.devices:
                    dtype = "unknown"
                    for dt, d in config.DEVICE_IDS.items():
                        if d == did:
                            dtype = dt
                            break
                    st.session_state.devices[did] = {"type": dtype, "status": {}}
            if "解绑成功" in msg and df:
                did = df.get("device_id")
                if did and did in st.session_state.devices:
                    del st.session_state.devices[did]

    # 把 bridge 里的 last_seq 同步到 session_state（一次性，跨 rerun 持久化）
    b = _get_bridge()
    with b["lock"]:
        st.session_state.last_seq = b["last_seq"]


# ── MQTT Client ──────────────────────────────────────────
def init_mqtt():
    if st.session_state.mqtt_ready:
        return

    user_id = st.session_state.user_id
    client = mqtt.Client(
        client_id=f"webui_{user_id}_{int(time.time())}",
        callback_api_version=mqtt.CallbackAPIVersion.VERSION1,
        userdata={"user_id": user_id},
    )
    client.on_connect = _on_connect
    client.on_disconnect = _on_disconnect
    client.on_message = _on_message
    client.reconnect_delay_set(min_delay=1, max_delay=5)

    try:
        client.connect(config.BROKER_HOST, config.BROKER_PORT)
        for _ in range(30):
            client.loop(timeout=0.1)
            if _get_bridge()["connected"]:
                break
        else:
            st.warning("MQTT 连接超时")
        # 不使用 loop_start()，改为在 drain_bridge 中手动调用 client.loop()
        st.session_state._mqtt_client = client
        st.session_state.mqtt_ready = True
    except Exception as e:
        st.error(f"MQTT 连接失败: {e}")


def _on_connect(client, userdata, flags, rc):
    if rc == 0:
        client.subscribe(f"home/{userdata['user_id']}/from_cloud")
        _bridge_push("connected", True)
    else:
        _bridge_push("error", f"MQTT 连接失败 (rc={rc})")
        _bridge_push("connected", False)


def _on_disconnect(client, userdata, rc):
    _bridge_push("disconnected", rc)
    if rc != 0:
        try:
            client.reconnect()
        except Exception:
            pass


def _on_message(client, userdata, msg):
    data = json.loads(msg.payload.decode())
    payload = data.get("payload", {})
    seq_num = data.get("seq_num", 0)
    timestamp = data.get("timestamp", 0)
    signature = data.get("signature", "")

    sig_ok = crypto_utils.verify_signature(
        config.SECRET_KEY, seq_num, timestamp, payload, signature
    )
    ts_ok = crypto_utils.check_timestamp(timestamp, config.TIME_WINDOW)

    # 序列号检查：跨线程共享 last_seq，用 bridge 锁保护。
    b = _get_bridge()
    with b["lock"]:
        last_seq = b["last_seq"]
    seq_ok = crypto_utils.check_seq_num(seq_num, last_seq)
    if sig_ok and ts_ok and seq_ok:
        with b["lock"]:
            b["last_seq"] = seq_num

    _bridge_push("log", {
        "time": datetime.now().strftime("%H:%M:%S"),
        "seq": seq_num, "ts": timestamp,
        "sig": signature[:16] + "...",
        "sig_ok": sig_ok, "ts_ok": ts_ok, "seq_ok": seq_ok,
        "payload": str(payload.get("message", payload.get("command", "")))[:40],
        "type": payload.get("type", "response"),
    })

    msg_type = payload.get("type")
    if msg_type == "device_status":
        _bridge_push("status", {
            "device_id": payload.get("device_id", ""),
            "device_type": payload.get("device_type", ""),
            "status": payload.get("status", {}),
            "seq_ok": seq_ok,
        })

    if "success" in payload:
        _bridge_push("response", {
            "time": datetime.now().strftime("%H:%M:%S"),
            "success": payload["success"],
            "message": payload.get("message", ""),
            "data": payload.get("data"),
            "seq_ok": seq_ok,
        })


# ── Helpers ──────────────────────────────────────────────
def _send_signed(payload_dict):
    client = getattr(st.session_state, "_mqtt_client", None)
    if client is None:
        return False, "MQTT 客户端未初始化"
    if not client.is_connected():
        try:
            client.reconnect()
            time.sleep(0.3)
        except Exception:
            pass
        if not client.is_connected():
            return False, "MQTT 未连接，请检查 Broker 是否运行"

    signed = crypto_utils.create_signed_message(
        config.SECRET_KEY,
        message_format.seq_manager.get_next(),
        payload_dict,
    )
    topic = f"home/{st.session_state.user_id}/to_cloud"
    result = client.publish(topic, json.dumps(signed))
    if result.rc == mqtt.MQTT_ERR_SUCCESS:
        for _ in range(10):
            client.loop(timeout=0.1)
            drain_bridge()
        st.rerun()
    return False, f"发送失败: rc={result.rc}"


# ── Drain bridge at start of every rerun ─────────────────
drain_bridge()

# ── Sidebar ──────────────────────────────────────────────
with st.sidebar:
    st.title("🏠 智能家居")
    st.caption("物联网安全通信系统")
    st.divider()

    st.selectbox(
        "当前用户", config.USER_IDS,
        key="user_id",
        disabled=st.session_state.mqtt_ready,
    )

    if not st.session_state.mqtt_ready:
        if st.button("🔗 连接到 MQTT Broker", use_container_width=True):
            init_mqtt()
            st.session_state._mqtt_connected = True
            st.rerun()
    else:
        connected = getattr(st.session_state, "_mqtt_connected", False)
        if connected:
            st.success("✅ MQTT 已连接")
        else:
            st.warning("⏳ 正在连接...")

        st.divider()
        st.subheader("📱 设备管理")

        available = [d for d in config.DEVICE_IDS.values()
                     if d not in st.session_state.devices]
        if available:
            bind_target = st.selectbox("绑定设备", available, key="bind_select")
            if st.button("🔗 绑定", use_container_width=True):
                ok, err = _send_signed(
                    message_format.create_bind_message(st.session_state.user_id, bind_target)
                )
                if ok:
                    st.toast(f"已发送绑定请求: {bind_target}", icon="🔗")
                else:
                    st.error(err)
        else:
            st.caption("所有设备已绑定")

        if st.session_state.devices:
            bound_list = list(st.session_state.devices.keys())
            unbind_target = st.selectbox("解绑设备", bound_list, key="unbind_select")
            if st.button("🔓 解绑", use_container_width=True):
                ok, err = _send_signed(
                    message_format.create_unbind_message(st.session_state.user_id, unbind_target)
                )
                if ok:
                    st.toast(f"已发送解绑请求: {unbind_target}", icon="🔓")
                else:
                    st.error(err)

        st.divider()
        st.subheader("🛡️ 安全测试")
        st.caption("模拟重放攻击：发送过期时间戳")

        replay_device = st.selectbox(
            "目标设备", config.DEVICE_IDS.values(), key="replay_device"
        )
        if st.button("🚨 模拟重放攻击", use_container_width=True, type="primary"):
            old_ts = int(time.time()) - 600
            payload = message_format.create_control_message(replay_device, "on")
            sig = crypto_utils.generate_signature(config.SECRET_KEY, 9999, old_ts, payload)
            replay_msg = {
                "seq_num": 9999, "timestamp": old_ts,
                "payload": payload, "signature": sig,
            }
            client = getattr(st.session_state, "_mqtt_client", None)
            if client:
                client.publish(
                    f"home/{st.session_state.user_id}/to_cloud",
                    json.dumps(replay_msg),
                )
                st.toast("已发送重放攻击消息（过期时间戳）", icon="🚨")
            else:
                st.error("MQTT 未连接")

        with st.expander("📋 最近操作日志"):
            for r in reversed(st.session_state.bind_results[-10:]):
                icon = "✅" if r["success"] else "❌"
                st.caption(f"{icon} {r['time']} {r['message']}")


# ── Main ─────────────────────────────────────────────────
st.title("🏠 物联网智能家居安全通信系统")
st.caption("基于 MQTT + HMAC-SHA256 签名的防重放攻击演示")

if not st.session_state.mqtt_ready:
    st.info("👈 请在左侧面板点击「连接到 MQTT Broker」开始")
    st.stop()

# ── Device cards ─────────────────────────────────────────
st.subheader("📱 设备控制面板")
cols = st.columns(3)

DEVICE_LIST = [
    ("ac_001", "air_conditioner", "❄️ 空调"),
    ("lb_001", "light_bulb", "💡 灯泡"),
    ("ss_001", "smart_socket", "🔌 智能插座"),
]

for i, (did, dtype, label) in enumerate(DEVICE_LIST):
    with cols[i]:
        info = st.session_state.devices.get(did, {})
        status = info.get("status", {})
        is_on = status.get("is_on", False)
        card_class = "on" if is_on else "off"

        st.markdown(
            f'<div class="device-card {card_class}">'
            f'<h3>{label}</h3>'
            f'<p style="color:#999;font-size:0.8rem;">{did}</p>'
            f'</div>',
            unsafe_allow_html=True,
        )

        if did not in st.session_state.devices:
            st.caption("⚠️ 未绑定")
            if st.button("🔗 一键绑定", key=f"quickbind_{did}"):
                ok, err = _send_signed(
                    message_format.create_bind_message(st.session_state.user_id, did)
                )
                if ok:
                    st.toast(f"已发送绑定请求: {did}", icon="🔗")
                else:
                    st.error(err)
            continue

        # Status display
        if dtype == "air_conditioner":
            st.metric("温度", f"{status.get('temperature', 26)}°C")
            st.caption(f"模式: {status.get('mode', 'cool')} | "
                       f"状态: {'🟢 开启' if is_on else '⚫ 关闭'}")
        elif dtype == "light_bulb":
            st.metric("亮度", f"{status.get('brightness', 100)}%")
            st.caption(f"状态: {'🟢 开启' if is_on else '⚫ 关闭'}")
        elif dtype == "smart_socket":
            st.metric("功率", f"{status.get('power', 0)}W")
            st.caption(f"模式: {status.get('power_mode', 'normal')} | "
                       f"状态: {'🟢 开启' if is_on else '⚫ 关闭'}")

        # On/Off buttons
        c1, c2 = st.columns(2)
        with c1:
            if st.button("🔛 开启", key=f"on_{did}", use_container_width=True, disabled=is_on):
                ok, err = _send_signed(message_format.create_control_message(did, "on"))
                st.toast(f"{label}: 已发送开启命令") if ok else st.error(err)
        with c2:
            if st.button("🔚 关闭", key=f"off_{did}", use_container_width=True, disabled=not is_on):
                ok, err = _send_signed(message_format.create_control_message(did, "off"))
                st.toast(f"{label}: 已发送关闭命令") if ok else st.error(err)

        # Device-specific controls
        if dtype == "air_conditioner":
            temp = st.slider("温度设置", 16, 30, value=status.get("temperature", 26), key=f"temp_{did}")
            if st.button("🌡️ 设置温度", key=f"settemp_{did}"):
                ok, err = _send_signed(message_format.create_control_message(
                    did, "set_temperature", {"temperature": temp}
                ))
                st.toast(f"温度 → {temp}°C") if ok else st.error(err)

            mode = st.selectbox("模式", ["cool", "heat"],
                                index=0 if status.get("mode", "cool") == "cool" else 1,
                                key=f"mode_{did}")
            if st.button("🔄 切换模式", key=f"setmode_{did}"):
                ok, err = _send_signed(message_format.create_control_message(
                    did, "set_power_mode", {"mode": mode}
                ))
                st.toast(f"模式 → {mode}") if ok else st.error(err)

        elif dtype == "light_bulb":
            bright = st.slider("亮度", 0, 100, value=status.get("brightness", 100), key=f"bright_{did}")
            if st.button("💡 设置亮度", key=f"setbright_{did}"):
                ok, err = _send_signed(message_format.create_control_message(
                    did, "set_brightness", {"brightness": bright}
                ))
                st.toast(f"亮度 → {bright}%") if ok else st.error(err)

        elif dtype == "smart_socket":
            pmode = st.selectbox("功率模式", ["normal", "eco"],
                                 index=0 if status.get("power_mode", "normal") == "normal" else 1,
                                 key=f"pmode_{did}")
            if st.button("⚡ 设置模式", key=f"setpmode_{did}"):
                ok, err = _send_signed(message_format.create_control_message(
                    did, "set_power_mode", {"mode": pmode}
                ))
                st.toast(f"模式 → {pmode}") if ok else st.error(err)

# ── Security monitor ─────────────────────────────────────
st.divider()
st.subheader("🛡️ 安全监控面板")

col_log, col_detail = st.columns([2, 1])

with col_log:
    st.caption("实时消息流 — 每条消息都经过签名验证 + 时间戳检查 + 序列号检查")
    msgs = st.session_state.messages
    if msgs:
        rows = []
        for m in reversed(msgs[-15:]):
            rows.append({
                "时间": m["time"], "序列号": m["seq"], "内容": m["payload"],
                "签名": "✅" if m["sig_ok"] else "❌",
                "时间戳": "✅" if m["ts_ok"] else "❌",
                "序号检查": "✅" if m.get("seq_ok") else "❌",
            })
        st.dataframe(rows, use_container_width=True)
    else:
        st.info("等待消息...")

with col_detail:
    st.caption("安全机制说明")
    total = len(msgs)
    passed = sum(1 for m in msgs if m["sig_ok"] and m["ts_ok"] and m.get("seq_ok"))
    rejected = total - passed
    app_rejected = sum(1 for r in st.session_state.bind_results if not r.get("success", True))

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("总消息", total)
    c2.metric("✅ 通过", passed)
    c3.metric("❌ 拒绝", rejected, delta=None if rejected == 0 else f"-{rejected}")
    c4.metric("🚫 应用层", app_rejected, delta=None if app_rejected == 0 else f"+{app_rejected}")

    st.divider()
    st.markdown("""
    **三重防护机制（全部已实现）：**
    1. **HMAC-SHA256 签名** — 确保消息内容未被篡改
    2. **时间戳窗口（5分钟）** — 防止过期消息重放
    3. **序列号单调递增** — 防止 5 分钟内原样重放

    **应用层拒绝** — 消息签名/时间戳/序列号均通过，但业务逻辑（重放攻击/未授权/设备未绑定等）拒绝

    **消息格式：**
    ```
    {seq_num, timestamp, payload, signature}
    ```
    签名 = HMAC(seq|ts|payload)
    """)

    if msgs:
        st.divider()
        st.caption("最新消息详情")
        latest = msgs[-1]
        st.markdown(f"**签名片段:** `{latest['sig']}`")
        st.markdown(f"**签名验证:** {'✅ 通过' if latest['sig_ok'] else '❌ 失败'}")
        st.markdown(f"**时间戳验证:** {'✅ 有效' if latest['ts_ok'] else '❌ 过期'}")
        st.markdown(f"**序列号验证:** {'✅ 新颖' if latest.get('seq_ok') else '❌ 重放/重复'}")

# ── Footer ───────────────────────────────────────────────
st.divider()
st.caption(
    "物联网安全大作业 · 基于 MQTT + HMAC-SHA256 · "
    f"Broker: {config.BROKER_HOST}:{config.BROKER_PORT}"
)
