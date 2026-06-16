# 物联网智能家居安全通信系统

基于MQTT协议的智能家居原型系统，支持加密通信和重放攻击防御。

## 系统架构

```
                    ┌──────────────────────────┐
                    │   Streamlit Web UI :8501  │
                    │   (演示 / 答辩用)          │
                    └────────────┬─────────────┘
                                 │ MQTT
┌────────────────────────────────┴────────────────────┐
│               MQTT Broker (Mosquitto) :1883          │
└────────────┬──────────────┬──────────────┬──────────┘
             │              │              │
    ┌────────┴────┐  ┌──────┴──────┐  ┌───┴──────────┐
    │ Cloud/      │  │   IoT       │  │    User       │
    │ Server      │  │   Devices   │  │    Client     │
    │ (认证/转发)  │  │ (空调/灯泡/ │  │  (CLI 控制台) │
    │             │  │  插座)      │  │               │
    └─────────────┘  └─────────────┘  └───────────────┘
```

## 功能特性

- **多用户支持**: 至少2个用户同时在线
- **多设备支持**: 3种设备类型（空调、灯泡、插座）
- **加密通信**: HMAC-SHA256签名验证
- **防重放攻击**:
  - 时间戳验证（5分钟窗口）
  - 序列号验证（不重复）
  - 消息签名（内容完整性）
- **Web 演示界面**: Streamlit 可视化仪表盘，实时安全监控面板，一键模拟重放攻击

## 文件结构

```
secure-mqtt-smarthome/
├── config.py              # 全局配置
├── cloud_server.py       # 云端服务器
├── user_client.py         # 用户客户端
├── crypto_utils.py       # 加密工具
├── message_format.py     # 消息格式
├── devices/
│   ├── __init__.py
│   ├── air_conditioner.py  # 空调设备
│   ├── light_bulb.py       # 灯泡设备
│   └── smart_socket.py     # 插座设备
├── run_all.py            # 快速启动脚本
├── web_ui.py             # Streamlit Web 演示界面
├── tests/
│   ├── test_replay_attack.py      # 重放攻击测试（纯函数层）
│   ├── test_replay_seq_handler.py # 重放攻击测试（handler 层）
│   ├── test_auto.py               # 自动化功能测试
│   └── test_e2e.py                # 端到端自动化测试
└── requirements.txt      # 依赖
```

## 快速开始

### 1. 环境准备

```bash
# 创建虚拟环境
python -m venv venv

# 激活虚拟环境
.\venv\Scripts\activate  # Windows
source venv/bin/activate  # Linux/Mac

# 安装依赖
pip install -r requirements.txt
```

### 2. 启动MQTT Broker

**Docker方式（推荐）：**
```bash
# 启动Mosquitto容器
docker run -d -p 1883:1883 --name mosquitto eclipse-mosquitto

# 查看运行状态
docker ps | grep mosquitto
查看运行状态（Windows 版本）
docker ps | findstr mosquitto

# 停止容器
docker stop mosquitto

# 重启容器
docker start mosquitto

# 查看日志
docker logs mosquitto
```

**手动安装方式：**
```bash
# Linux: sudo apt install mosquitto
sudo apt install mosquitto
mosquitto

# Windows: 下载并安装 https://mosquitto.org/download/
```

### 3. 运行系统

打开两个终端：

```bash
# 终端1：启动后端（云端 + 3 个设备）
python run_all.py

# 终端2：启动 Web UI
streamlit run web_ui.py
```

启动完成后浏览器访问 http://localhost:8501/，即可使用 Web 控制台（设备卡片、绑定/控制、实时安全监控、重放攻击模拟）。

> 不需要 Web 界面时，可以跳过终端 2，改跑 `python user_client.py` 用命令行控制。

如需手动启动（debug 用），各组件可独立运行：
```bash
python cloud_server.py
python devices/air_conditioner.py
python devices/light_bulb.py
python devices/smart_socket.py
python user_client.py      # 可选，CLI 客户端
```

### 4. 测试

```bash
# 端到端自动化测试（启动所有组件并模拟用户操作）
python tests/test_e2e.py

# 重放攻击防御 — 纯函数层（不需要 broker）
python tests/test_replay_attack.py

# 重放攻击防御 — handler 层（需要 broker,验证 seq 检查在生产路径中真实生效）
python tests/test_replay_seq_handler.py

# 自动化功能测试（需要已启动的系统）
python tests/test_auto.py
```

## 分布式部署说明

### 在不同计算机上部署

本系统支持在不同实体计算机或虚拟机上部署MQTT服务器与客户端，实现真正的分布式架构。

#### 部署架构示例

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   计算机A        │     │   计算机B        │     │   计算机C        │
│  (MQTT Broker)  │     │ (Cloud Server)  │     │ (User Client)   │
│                 │     │                 │     │                 │
│  Mosquitto      │◄───►│ cloud_server.py│◄───►│ user_client.py │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                                                        │
┌─────────────────┐                                      │
│   计算机D        │                                      │
│  (IoT Devices)  │──────────────────────────────────────┘
│                 │
│ air_conditioner │
│ light_bulb      │
│ smart_socket    │
└─────────────────┘
```

#### Step 1: 配置MQTT Broker (计算机A)

**Docker方式（推荐，无需配置文件）：**
```bash
# 直接运行，默认开放1883端口
docker run -d -p 1883:1883 --name mosquitto eclipse-mosquitto
```

**手动安装方式：**

```bash
# Windows: 下载并安装 https://mosquitto.org/download/
# Linux: sudo apt install mosquitto

# 配置文件位置：
#   Windows: 安装目录下创建 mosquitto.conf
#   Linux: /etc/mosquitto/mosquitto.conf 或创建 ~/.mosquitto/mosquitto.conf

# mosquitto.conf 内容:
# listener 1883
# allow_anonymous true
# persistence false

# 启动Broker
mosquitto -c mosquitto.conf -p 1883
```

#### Step 2: 修改config.py (所有计算机)

```python
# 将localhost改为MQTT Broker的实际IP地址
BROKER_HOST = "192.168.1.100"  # 计算机A的IP地址
BROKER_PORT = 1883
```

#### Step 3: 启动云端服务器 (计算机B)

```bash
# 安装依赖
pip install -r requirements.txt

# 启动云端服务器
python cloud_server.py
```

#### Step 4: 启动物联网设备 (计算机D)

```bash
# 启动设备
python devices/air_conditioner.py
python devices/light_bulb.py
python devices/smart_socket.py
```

#### Step 5: 启动用户客户端 (计算机C)

```bash
# 启动用户客户端
python user_client.py
```

### 虚拟机部署说明

| 模式 | 说明 |
|------|------|
| **NAT模式** | 虚拟机通过宿主机的IP上网，Broker地址填宿主机IP |
| **桥接模式** | 虚拟机与宿主机在同一网络，直接使用虚拟机IP |
| **Host-only模式** | 仅宿主机与虚拟机通信，需配置虚拟网络适配器 |

### 注意事项

1. **防火墙设置**: 确保1883端口对外部开放
2. **网络安全**: 生产环境应启用MQTT用户名密码认证
3. **时间同步**: 不同计算机的系统时间差异不超过5分钟，否则时间戳验证会失败

## 使用说明

### Web 界面（推荐）

启动 `streamlit run web_ui.py` 后，浏览器访问 http://localhost:8501：

- **左侧栏**: 用户选择、MQTT 连接、设备绑定/解绑、「模拟重放攻击」按钮、操作日志
- **设备控制面板**: 3 列设备卡片，开关按钮 + 温度/亮度/模式滑块
- **安全监控面板**: 实时消息流表格（签名验证 ✅/❌、时间戳检查、序号检查）、总消息/✅通过/❌拒绝/🚫应用层四列计数、最新消息签名详情

### 命令行客户端

1. **绑定设备**: 输入设备ID进行绑定
2. **控制设备**: 选择已绑定的设备发送命令
3. **查看状态**: 查看设备当前状态

### 设备命令

| 设备 | 命令 | 参数 |
|------|------|------|
| 空调 | on/off | - |
| 空调 | set_temperature | temperature: 16-30 |
| 灯泡 | on/off | - |
| 灯泡 | set_brightness | brightness: 0-100 |
| 插座 | on/off | - |
| 插座 | set_power_mode | mode: normal/eco |

## 防重放攻击原理

每条消息包含:
- `seq_num`: 序列号（递增）
- `timestamp`: 时间戳
- `signature`: HMAC-SHA256签名

签名内容: `序列号|时间戳|消息内容`

验证时依次检查:
1. 签名是否匹配
2. 时间戳是否在5分钟内
3. 序列号是否严格大于已处理的最大值（**`check_seq_num` 已在每个 handler 强制执行**）

三重防线缺一不可:仅靠签名+时间戳不能阻挡 5 分钟内的原样重放。
