# 物联网智能家居安全通信系统 - 四人小组协作指南

> 本系统基于MQTT协议，支持加密通信和重放攻击防御。以下指南专门为**4人小组**完成物联网安全课程作业而设计。

---

## 👥 四人分工速览

| 角色 | 负责人 | 核心职责 | 主要文件 |
|:---|:---|:---|:---|
| **A - 项目经理** | 成员1 | 进度管理、报告整合、PPT制作 | `README.md`, 实验报告 |
| **B - 后端开发** | 成员2 | 云端服务器、安全机制 | `cloud_server.py`, `crypto_utils.py` |
| **C - 设备开发** | 成员3 | 三个设备模拟、分布式部署 | `devices/*.py`, `config.py` |
| **D - 前端+测试** | 成员4 | Web界面、功能测试、安全评估 | `web_ui.py`, `tests/*.py` |

---

## 📅 两周执行计划

### 第1周：开发阶段

#### 第1天：环境搭建（全体集合）

**所有人同时执行：**
```bash
# 1. 克隆项目
git clone https://github.com/Sen11e/secure-mqtt-smarthome.git
cd secure-mqtt-smarthome

# 2. 创建虚拟环境
python -m venv venv
.\venv\Scripts\activate  # Windows
source venv/bin/activate  # Linux/Mac

# 3. 安装依赖
pip install -r requirements.txt

# 4. 验证Docker（A负责确认）
docker run hello-world
```

#### 第2天：熟悉代码结构（各自研读）

| 成员 | 重点研读文件 | 需要理解的内容 |
|:---|:---|:---|
| A | 整个项目结构 | 理解各模块关系，绘制架构图 |
| B | `crypto_utils.py`, `cloud_server.py` | HMAC签名、消息验证流程 |
| C | `devices/` 目录下三个设备文件 | 设备状态机、MQTT通信 |
| D | `web_ui.py`, `tests/` | Streamlit界面、测试框架 |

#### 第3-4天：代码修改与完善

**B（后端开发）任务清单：**
```python
# 1. 检查 crypto_utils.py 中的签名验证
# 2. 完善 cloud_server.py 中的权限检查
# 3. 确保序列号检查在所有handler中强制执行
```

**C（设备开发）任务清单：**
```bash
# 1. 确保三个设备能独立运行
python devices/air_conditioner.py
python devices/light_bulb.py
python devices/smart_socket.py

# 2. 测试设备状态上报
# 3. 准备分布式部署的虚拟机/电脑
```

**D（前端+测试）任务清单：**
```bash
# 1. 熟悉Streamlit界面
streamlit run web_ui.py

# 2. 运行现有测试
python tests/test_replay_attack.py
python tests/test_auto.py
```

#### 第5天：第一次集成（全体集合）

```bash
# 终端1：启动MQTT Broker
docker run -d -p 1883:1883 --name mosquitto eclipse-mosquitto

# 终端2：启动云端
python cloud_server.py

# 终端3-5：启动三个设备（C负责）
python devices/air_conditioner.py
python devices/light_bulb.py
python devices/smart_socket.py

# 终端6：启动Web界面（D负责）
streamlit run web_ui.py
```

**检查清单：**
- [ ] 云端显示"已连接到MQTT Broker"
- [ ] 三个设备显示"注册成功"
- [ ] Web界面能看到三个设备卡片
- [ ] 点击设备开关能控制设备

---

### 第2周：测试与报告

#### 第6-7天：功能测试与安全评估

**D（前端+测试）执行安全测试：**

```python
# tests/security_test.py - 新建测试文件
import paho.mqtt.client as mqtt
import time
import json

class SecurityTest:
    def test_replay_attack(self):
        """测试重放攻击防御"""
        # 1. 捕获一条合法控制命令
        # 2. 立即重放同一命令
        # 3. 预期：第二次被拒绝（序列号检查）
        print("测试重放攻击...")
    
    def test_unauthorized_access(self):
        """测试越权访问"""
        # user_001 尝试控制 user_002 的设备
        print("测试越权访问...")
```

**B（后端开发）配合修复发现的问题：**
- 如果重放攻击测试失败，检查 `check_seq_num` 函数
- 如果越权访问成功，检查 `cloud_server.py` 中的权限验证

#### 第8天：分布式部署测试（全体）

**使用桥接模式配置虚拟机：**

| 计算机 | IP地址 | 运行组件 | 负责人 |
|:---|:---|:---|:---|
| 电脑A | 192.168.1.100 | MQTT Broker | A |
| 电脑B | 192.168.1.101 | Cloud Server | B |
| 电脑C | 192.168.1.102 | 空调+灯泡 | C |
| 电脑D | 192.168.1.103 | Web UI | D |

**修改 config.py：**
```python
# 所有电脑的config.py都要改
BROKER_HOST = "192.168.1.100"  # 电脑A的IP
```

**截图要求（每人提供2-3张）：**
- [ ] 自己的电脑IP配置截图
- [ ] 成功连接MQTT的日志截图
- [ ] 多用户同时控制的截图

#### 第9-10天：报告撰写（分工协作）

**使用腾讯文档/飞书在线协作：**

| 章节 | 内容 | 负责人 | 页数 |
|:---|:---|:---|:---|
| 1-2 | 实验目标、组员分工 | A | 1 |
| 3-4 | 工具介绍、实验原理 | B | 2 |
| 5 | 实验步骤（带截图） | C | 3 |
| 6-7 | 问题解决、收获感悟 | D | 2 |
| 8 | 三个问题的回答 | B | 2 |
| 9 | 安全评估 | D | 2 |

#### 第11天：PPT制作与答辩演练（全体）

**PPT结构（10分钟汇报）：**

```
1. 封面（30秒）- A
2. 系统架构与分工（1分钟）- A
3. 核心功能演示（3分钟）- D（现场演示）
4. 安全机制与防重放（2分钟）- B
5. 安全评估结果（2分钟）- D
6. 遇到的问题与解决（1分钟）- C
7. 总结（30秒）- A
```

---

## 🔧 各成员详细操作指南

### 成员A（项目经理）- 不需要写代码，但要懂整体

**每日工作：**
- [ ] 9:00 在群里发今日任务提醒
- [ ] 21:00 组织15分钟站会（微信语音即可）
- [ ] 记录每个人的进度和遇到的问题

**站会模板：**
```
【今日站会】6月XX日
B：昨天完成了签名验证，今天做权限检查，无阻塞
C：昨天空调设备调通，今天做灯泡，需要帮忙看MQTT订阅
D：昨天界面完成80%，今天继续，无阻塞
A：注意分布式部署的截图要准备
```

**需要准备的报告内容：**
- 组员分工表（写清楚每个人做了什么）
- 时间线（什么时间完成了什么）
- 系统架构图（用draw.io画）

---

### 成员B（后端开发）- 核心代码维护

**你的核心文件：**
- `crypto_utils.py` - 加密签名
- `cloud_server.py` - 云端逻辑
- `message_format.py` - 消息格式

**启动命令（验证你的工作）：**
```bash
python cloud_server.py
# 应该看到：已连接到MQTT Broker，结果码: 0
```

**常见问题修复：**
```python
# 如果出现 ImportError，检查文件开头的导入
from crypto_utils import CryptoUtils  # 确保这个类存在

# 如果签名验证失败，检查密钥是否一致
# 设备和云端必须使用相同的 SECRET_KEY
```

---

### 成员C（设备开发）- 三个设备模拟

**你的核心文件：**
- `devices/air_conditioner.py`
- `devices/light_bulb.py`
- `devices/smart_socket.py`
- `config.py`（配置MQTT地址）

**启动命令（依次启动）：**
```bash
python devices/air_conditioner.py  # 终端1
python devices/light_bulb.py       # 终端2
python devices/smart_socket.py     # 终端3
```

**每个设备应该输出：**
```
[空调] ✅ 已连接到MQTT Broker
[空调] 📱 发送注册请求: ac_001
[空调] ✅ 注册成功
```

**截图任务：**
- 三个终端同时运行三个设备的截图
- 修改config.py中BROKER_HOST后的截图

---

### 成员D（前端+测试）- Web界面和测试

**你的核心文件：**
- `web_ui.py` - Streamlit界面
- `tests/test_e2e.py` - 端到端测试
- `tests/test_replay_attack.py` - 重放攻击测试

**启动命令：**
```bash
streamlit run web_ui.py
# 浏览器自动打开 http://localhost:8501
```

**测试命令：**
```bash
# 测试重放攻击防御
python tests/test_replay_attack.py
# 预期输出：重放攻击被成功防御

# 端到端测试
python tests/test_e2e.py
# 预期输出：所有测试通过
```

**安全评估报告内容：**
1. 重放攻击测试结果（截图）
2. 越权访问测试结果
3. 消息篡改测试结果
4. 威胁模型分析表

---

## 📸 需要准备的截图清单（每人负责自己的部分）

| 成员 | 截图内容 | 数量 |
|:---|:---|:---|
| A | 团队协作记录（微信群/站会截图）、项目进度看板 | 2 |
| B | cloud_server.py运行日志、签名验证成功/失败对比 | 3 |
| C | 三个设备同时运行的终端、config.py修改前后对比、虚拟机IP配置 | 4 |
| D | Web界面完整截图、重放攻击测试结果、安全监控面板 | 4 |

---

## ✅ 最终提交检查清单

**代码提交（GitHub）：**
- [ ] 所有代码已推送到GitHub仓库
- [ ] README.md已更新（包含四人分工说明）
- [ ] requirements.txt包含所有依赖

**实验报告：**
- [ ] 封面（姓名、学号、分工）
- [ ] 实验目标
- [ ] 组员分工（详细）
- [ ] 工具及编程库简介
- [ ] 实验原理（含架构图）
- [ ] 实验步骤（含截图）
- [ ] 遇到的问题及解决办法
- [ ] 收获与感悟
- [ ] 三个问题的回答
- [ ] 安全评估
- [ ] 源代码说明

**演示PPT：**
- [ ] 10页以内
- [ ] 包含现场演示环节
- [ ] 准备备用方案（录屏）

---

## 🆘 常见问题速查

| 问题 | 快速解决 | 负责人 |
|:---|:---|:---|
| Docker报错"Conflict" | `docker rm -f mosquitto` | A |
| 导入CryptoUtils失败 | 检查crypto_utils.py是否有这个类 | B |
| 设备连接不上Broker | 检查config.py中的BROKER_HOST | C |
| Streamlit打不开 | `pip install streamlit --upgrade` | D |
| 时间戳验证失败 | 同步系统时间 | B |
| 多用户无法同时登录 | 用不同端口启动：`streamlit run web_ui.py --server.port 8502` | D |

---

祝你们顺利完成实验！有问题随时在群里沟通。
