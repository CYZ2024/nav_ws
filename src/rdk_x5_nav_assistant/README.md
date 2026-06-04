# rdk_x5_nav_assistant — robot-nav 导航板

导航专用 ROS2 包，**负责激光雷达、SLAM、定位、Nav2 导航、与 AI 板通信**。所有视觉处理和用户交互由 AI 板（`robot-ai`, 10.0.0.5）完成，导航板只负责：

- **激光雷达驱动**：YDLIDAR X3 (vp100_ros2) → `/scan`
- **Cartographer 2D SLAM**：建图 + 定位（无里程计纯激光雷达模式）
- **TF 发布**：`map → base_footprint → base_link → laser_link`
- **Nav2 导航**：全局路径规划、障碍物检测
- **导航桥接**：接收 AI 板的 `/shopping/nav_goal`，返回 `/shopping/nav_status` 和 `/shopping/robot_pose`

**不需要摄像头，不需要底盘。**

---

## 与 AI 板的分工

| 职责 | AI 板 (`robot-ai`) | 导航板 (`robot-nav`) |
|------|-------------------|---------------------|
| USB 摄像头 / MIPI 相机 | ✅ | ❌ |
| AprilTag / 商品识别 | ✅ | ❌ |
| 语音 ASR / TTS | ✅ | ❌ |
| 用户状态机 | ✅ | ❌ |
| **YDLIDAR X3 (vp100_ros2)** | ❌ | ✅ |
| **Cartographer 2D SLAM** | ❌ | ✅ |
| **Nav2 路径规划** | ❌ | ✅ |
| **导航指令桥接** | ❌ | ✅ |

### 跨板 Topic/Action 接口

**AI 板发布 → 导航板订阅：**

| Topic | 类型 | 说明 |
|-------|------|------|
| `/shopping/nav_goal` | `std_msgs/String` (JSON) | 导航目标请求 |
| `/shopping/nav_cancel` | `std_msgs/String` (JSON) | 取消导航请求 |

**导航板发布 → AI 板订阅：**

| Topic | 类型 | 说明 |
|-------|------|------|
| `/shopping/nav_status` | `std_msgs/String` (JSON) | 导航状态反馈 |
| `/shopping/robot_pose` | `std_msgs/String` (JSON) | 当前位姿 |

---

## 目录结构

```
nav_ws/
├── src/rdk_x5_nav_assistant/
│   ├── config/
│   │   ├── cartographer/
│   │   │   ├── cartographer_2d.lua              # Cartographer 2D 配置（建图模式）
│   │   │   └── cartographer_2d_localization.lua # Cartographer 2D 配置（纯定位模式）
│   │   ├── nav2/
│   │   │   └── nav2_params.yaml          # Nav2 参数（无里程计适配）
│   │   ├── product_catalog.yaml          # 商品库
│   │   ├── store_map.yaml                # 语义地图（waypoint、货架）
│   │   ├── demo_routes.yaml              # 演示路线
│   │   ├── safety.yaml                   # 安全配置
│   │   ├── vp100.yaml                    # VP100 参数（当前使用）
│   │   └── ydlidar_x3.yaml               # YDLIDAR X3 参数（保留备用）
│   ├── launch/
│   │   ├── nav_bringup.launch.py         # 一键启动（雷达+Cartographer+Nav2+桥接）
│   │   ├── cartographer_slam.launch.py   # 单独启动 Cartographer 建图
│   │   ├── cartographer_localization.launch.py  # 单独启动 Cartographer 纯定位
│   │   └── nav_assistant.launch.py       # 旧版启动（保留兼容）
│   ├── maps/                             # 保存的地图文件
│   ├── scripts/                          # 辅助启动脚本
│   └── rdk_x5_nav_assistant/
│       ├── localization_bridge.py        # 多源定位桥接（Cartographer/RTAB-Map/odom）
│       └── nav_goal_bridge.py            # Nav2 导航桥接（与 AI 板通信）
└── src/ydlidar_ros2_driver/              # YDLIDAR ROS2 驱动（源码编译，保留备用）
```

---

## 硬件前提

- **YDLIDAR X3** 通过 USB 连接到导航板
- 串口设备：`/dev/ydlidar`（建议建立 udev 规则固定设备名）
- 激光雷达安装在购物车顶部，高度约 25cm

---

## 编译

```bash
cd /home/sunrise/Project/nav_ws
source /opt/tros/humble/setup.bash

# 编译所有包（包括 ydlidar_ros2_driver 和 rdk_x5_nav_assistant）
colcon build --symlink-install
source install/setup.bash
```

---

## 使用方式

### 方式一：一键启动（推荐）

```bash
cd /home/sunrise/Project/nav_ws
source /opt/tros/humble/setup.bash
source install/setup.bash

# 完整导航启动（雷达 + Cartographer + Nav2 + 桥接）
ros2 launch rdk_x5_nav_assistant nav_bringup.launch.py
```

启动的节点：

- `vp100_ros2_node` → `/scan`
- `laser_tf_publisher` → `base_link → laser_link`
- `base_tf_publisher` → `base_footprint → base_link`
- `cartographer_node` → SLAM/定位 + TF
- `cartographer_occupancy_grid_node` → `/map`
- Nav2 lifecycle nodes → 路径规划 + 避障
- `nav_goal_bridge` → `/shopping/nav_goal` / `/shopping/nav_status` / `/shopping/robot_pose`

### 方式二：分步启动

**Step 1: 激光雷达**
```bash
ros2 launch rdk_x5_nav_assistant nav_bringup.launch.py use_cartographer:=false use_nav2:=false use_nav_bridge:=false
```

**Step 2: Cartographer 建图**
```bash
ros2 launch rdk_x5_nav_assistant cartographer_slam.launch.py
```

**Step 3: 保存地图**
```bash
# 另开一个终端，调用 Cartographer 的地图保存服务
ros2 service call /write_state cartographer_ros_msgs/srv/WriteState "filename: '/home/sunrise/Project/nav_ws/maps/supermarket.pbstream'"
```

**Step 4: 纯定位模式（加载已有地图）**
```bash
ros2 launch rdk_x5_nav_assistant cartographer_localization.launch.py load_state_filename:='/home/sunrise/Project/nav_ws/maps/supermarket.pbstream'
```

**Step 5: Nav2 导航**
```bash
ros2 launch rdk_x5_nav_assistant nav_bringup.launch.py use_lidar:=false use_cartographer:=false use_nav_bridge:=true
```

---

## TF 树

```
map
└── base_footprint          (Cartographer 发布，2D 定位结果)
    └── base_link           (static_transform_publisher)
        └── laser_link      (static_transform_publisher, YDLIDAR X3 frame_id)
```

- `base_footprint`：机器人在地面的投影点（导航参考点）
- `base_link`：机器人本体中心
- `laser_link`：激光雷达中心

---

## 与 AI 板的通信合约

### `/shopping/nav_goal`（AI → Nav）

```json
{
  "request_id": "20260528-0001",
  "product_id": "milk",
  "shelf_id": "shelf_a",
  "target_pose": {
    "frame_id": "map",
    "x": 1.25,
    "y": 2.40,
    "yaw": 1.57
  },
  "mode": "navigate_to_shelf"
}
```

### `/shopping/nav_cancel`（AI → Nav）

```json
{
  "request_id": "20260528-0001",
  "reason": "user_cancelled"
}
```

### `/shopping/nav_status`（Nav → AI）

```json
{
  "request_id": "20260528-0001",
  "state": "MOVING",
  "message": "navigating",
  "distance_remaining": 2.8,
  "eta_s": 9.3,
  "product_id": "milk",
  "shelf_id": "shelf_a"
}
```

状态枚举：`IDLE`、`ACCEPTED`、`MOVING`、`ARRIVED`、`FAILED`、`CANCELED`。

### `/shopping/robot_pose`（Nav → AI）

```json
{
  "frame_id": "map",
  "x": 0.52,
  "y": 1.23,
  "z": 0.0,
  "yaw": 0.78,
  "stamp_ns": 1716892800000000000
}
```

---

## 调试

```bash
# 查看激光雷达数据
ros2 topic echo /scan

# 查看 TF 树
ros2 run tf2_tools view_frames

# 查看 Cartographer 子图
ros2 topic echo /submap_list

# 查看地图
ros2 topic echo /map

# 手动发送导航目标（测试）
ros2 topic pub --once /shopping/nav_goal std_msgs/msg/String '{data: "{\"request_id\":\"test-001\",\"product_id\":\"milk\",\"shelf_id\":\"shelf_a\",\"target_pose\":{\"frame_id\":\"map\",\"x\":1.0,\"y\":0.5,\"yaw\":0.0}}"}'

# 查看导航状态
ros2 topic echo /shopping/nav_status

# 查看当前位姿
ros2 topic echo /shopping/robot_pose

# 保存 Cartographer 地图
ros2 service call /write_state cartographer_ros_msgs/srv/WriteState "filename: '/home/sunrise/map.pbstream'"
```

---

## 前提条件

- **ROS2 Humble / TogetheROS** 已安装
- **Cartographer ROS** 已安装：`ros-humble-cartographer-ros`
- **Nav2** 已安装（系统自带）
- **VP100 驱动**（`vp100_ros2`）已在 `/userdata/dev_ws` 中可用
- **YDLIDAR SDK** 和 **ydlidar_ros2_driver** 保留备用（源码已编译到 nav_ws）

---

## 购物车适配说明

由于购物车由人推动，没有底盘电机：

1. **无里程计**：Cartographer 配置 `use_odometry = false`，纯扫描匹配定位
2. **无 cmd_vel 执行**：Nav2 controller 仍会计算最优路径并发布 `cmd_vel`，但购物车不连接底盘，这些消息被忽略
3. **语音导航引导**：AI 板根据 `/shopping/nav_status` 中的 `distance_remaining` 和路径方向做语音引导
4. **避障检测**：Nav2 local_costmap 仍会根据激光雷达检测障碍物，状态通过 `/shopping/nav_status` 反馈
