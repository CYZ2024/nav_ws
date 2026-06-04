# nav_ws 开发工作日志

> 记录每次开发进度，方便恢复上下文。按时间倒序排列。

---

## 2026-06-03（当前会话）— 硬件确认、代码审计、问题修复、注释统一

**硬件真相确认：**
- ⚠️ 修正：雷达**确实是 YDLIDAR X3**（用户确认 + 协议分析），之前 WORKLOG 记录有误
- ✅ 协议分析：原始串口数据包含 `0xAA55` 包头，与 YDLIDAR 标准协议一致
- ✅ `ydlidar_ros2_driver` 失败原因：**扫描数据协议兼容，但设备初始化命令 (`A565`) 的响应格式不兼容**，SDK 拒绝启动
- ✅ `vp100_ros2`（nvilidar SDK）能工作是因为**不强制设备身份校验**，直接读扫描数据
- ✅ OriginBot 官方代码证实：实际 launch 使用的就是 `vp100_ros2`，README 里的 `ydlidar_ros2_driver` 只是通用说明

**代码修复：**
- ✅ `setup.py` 版本号 0.1.0 → 0.2.0（与 package.xml 同步）
- ✅ 补齐缺失的 `scripts/` 目录（start_mapping.sh / save_map.sh / start_navigation.sh / setup_env.sh）
- ✅ 创建 `config/cartographer/cartographer_2d_localization.lua`（纯定位模式配置）
- ✅ 更新 `cartographer_localization.launch.py` 默认使用 localization.lua
- ✅ 所有代码中 VP100 注释 → 统一改为 **YDLIDAR X3 (vp100_ros2)**

**对照 plan.md 阶段评估:**

| 阶段 | 目标 | 状态 | 说明 |
|------|------|------|------|
| 阶段0 | 清理和固定运行环境 | 🟡 部分 | WireGuard 已通，udev 规则已创建 |
| 阶段1 | 修复 robot-ai 主控 | 🔴 未开始 | 在 robot-ai (10.0.0.5) 上 |
| 阶段2 | robot-nav 雷达 bring-up | 🟢 完成 | YDLIDAR X3 + vp100_ros2，/scan 稳定 |
| 阶段3 | robot-nav 底盘 bring-up | ⚪ 跳过 | 购物车由人推 |
| 阶段4 | Cartographer 建图 | 🟢 完成 | 已成功启动建图 |
| 阶段5 | Nav2 导航闭环 | 🟡 配置就绪 | 参数、launch、桥接齐全，未实际测试 |
| 阶段6 | 双板任务闭环 | 🟡 代码就绪 | topic 合约已实现，未联调 |
| 阶段7 | 货架识别和商品确认 | 🔴 未开始 | 依赖 robot-ai |
| 阶段8 | 用户抓取引导 | 🔴 未开始 | 依赖阶段7 |

**已知问题:**
- `ydlidar_ros2_driver` 和 `config/ydlidar_x3.yaml` 保留备用（品牌原生驱动理论上可行，但需修改 SDK 源码跳过设备校验）
- Cartographer 偶发时间戳非单调警告（VP100 驱动固件限制，不影响功能）

**下一步（按优先级）:**
1. 🔴 **保存地图** — 运行中调用 `/write_state` 保存 .pbstream
2. 🔴 **测试纯定位模式** — 加载 .pbstream 启动 `cartographer_localization.launch.py`
3. 🔴 **Nav2 闭环测试** — 启动完整 bringup，发送导航目标
4. 🟡 **联调双板通信** — robot-ai 发 nav_goal，robot-nav 返回 nav_status
5. 🟡 **检查供电稳定性** — 用户用 5V/3A 充电宝，需确认实际运行中是否稳定

---

## 2026-06-03 — VP100 驱动成功，Cartographer 启动建图

**重大发现（⚠️ 后续已修正）：** ~~雷达实际型号是 VP100~~ → **实际是 YDLIDAR X3**，使用 `/userdata/dev_ws` 中的 `vp100_ros2`（nvilidar SDK）兼容驱动，波特率 230400。

**本次会话完成:**
- ✅ udev 规则创建：`/dev/ydlidar` → `/dev/ttyUSB0` (CH340)
- ✅ dialout 权限确认
- ✅ ydlidar_ros2_driver launch 文件修复：Humble API 兼容性
- ✅ 通过大量调试确认雷达不是 YDLIDAR（SDK 无法解析数据格式，无 `0xAA 0x55` 包头）
- ✅ **发现并使用 VP100 驱动**：`/userdata/dev_ws` 中已有 `vp100_ros2`，波特率 230400
- ✅ VP100 输出 /scan：833 点/帧，0.43° 角度分辨率，~3.4 Hz（sampling_rate=5, resolution_fixed=true）
- ✅ 更新 `nav_bringup.launch.py`：YDLIDAR → VP100
- ✅ 创建 `config/vp100.yaml`
- ✅ Cartographer 配置修复：移除重复的 `local_sampling_ratio`/`global_sampling_ratio`
- ✅ **Cartographer 成功启动并开始建图**（`Added trajectory with ID '0'`, `Inserted submap (0, 0)`）
- ✅ `/map` 话题正常发布

**已知问题:**
- VP100 驱动偶发 "Lidar Data Invalid!" 警告
- 时间戳偶尔非单调（1/4 帧），Cartographer 会丢弃部分数据点
- 这些可能是 VP100 固件/驱动的固有限制，不影响基本功能

**TF 树:**
```
map (Cartographer 发布)
└── base_footprint (Cartographer 发布，2D 定位)
    └── base_link (static_transform_publisher)
        └── laser_link (static_transform_publisher，VP100 frame_id)
```

**下一步:**
1. 在实际环境中测试 Cartographer 建图效果
2. 保存地图（.pbstream）
3. 测试纯定位模式（加载已有地图）
4. 启动 Nav2 导航闭环
5. 清理 YDLIDAR 相关代码/配置（改为 VP100）

---

## 2026-06-03 — 继续推进：驱动参数调试，数据格式兼容性问题

**本次会话完成:**
- ✅ udev 规则创建：`/dev/ydlidar` → `/dev/ttyUSB0` (CH340)
- ✅ dialout 权限确认：sunrise 已在 dialout 组
- ✅ ydlidar_ros2_driver launch 文件修复：Humble API 兼容性（node_executable→executable, node_name→name, node_namespace→namespace）
- ✅ ydlidar_ros2_driver 参数文件适配：根据 YDLIDAR SDK 文档调整 X3/X4 参数
- ✅ 下载并编译最新 YDLIDAR SDK (1.2.20)

**调试过程记录:**
1. 尝试了多种参数组合（波特率 115200/128000/230400、isSingleChannel true/false、support_motor_dtr true/false）
2. SDK 始终能连接雷达、健康检查通过、能启动扫描
3. 但扫描数据解析失败：`invalid data X too big, has cleared`，随后超时
4. 原始数据分析：数据中没有标准 YDLIDAR 包头 `0xAA 0x55` 或 `0xA5 0x5A`
5. 尝试了位反转、字节交换、XOR 解码等多种变换，均无法识别数据格式
6. SDK 源码分析：`YDlidarDriver::parseData()` 期望 `0xAA 0x55` 包头，`m_data.size() > 1024` 时清空缓冲区报 "too big"

**当前阻塞:**
- 雷达数据格式不被 YDLIDAR SDK 1.2.20 识别
- 可能原因：(a) 实际型号不是 YDLIDAR X3，(b) 固件版本特殊/非官方，(c) 需要其他驱动

**下一步方案:**
1. 确认雷达物理标签上的实际型号
2. 尝试 sllidar_ros2（思岚驱动）或其他社区驱动
3. 如确认是 YDLIDAR X3，可能需要更新固件或联系厂商

---

## 2026-06-01 — Cartographer 配置完成，YDLIDAR 硬件未识别

**已完成:**
- 安装 `ros-humble-cartographer-ros`, `ros-humble-cartographer-ros-msgs`
- 源码构建 YDLIDAR SDK → `/usr/local`
- 源码克隆 `ydlidar_ros2_driver` 到 `nav_ws/src/`，修复 Humble API 兼容性
- 创建 Cartographer 2D Lua 配置（纯激光雷达，无里程计）
- 创建 Nav2 参数配置
- 创建 ydlidar_x3.yaml 驱动参数
- 创建 3 个 launch 文件（bringup / slam / localization）
- 创建 nav_goal_bridge 节点
- 更新 localization_bridge 支持 Cartographer /tracked_pose
- 创建 start_mapping.sh / save_map.sh / start_navigation.sh 脚本
- 更新 setup.py, package.xml, README.md

**阻塞:** YDLIDAR X3 硬件未识别（系统无 /dev/ttyUSB*）

---
