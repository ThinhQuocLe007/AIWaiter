# 🤖 TurtleBot4 Restaurant Simulation - Planning Guide

> **Mục tiêu**: Xây dựng bản đồ mới → Navigation → Mô phỏng nhà hàng giao đồ ăn → Port sang robot thực tế

---

## 📂 Tổng quan Source Code Structure

```
turtlebot4_ws/src/
├── turtlebot4/                          # [CORE] Packages chính cho robot
│   ├── turtlebot4_description/          # URDF/model robot
│   ├── turtlebot4_msgs/                 # Custom ROS2 messages
│   ├── turtlebot4_navigation/           # ⭐ Navigation, SLAM, Localization
│   └── turtlebot4_node/                 # Node C++ chính của robot
│
├── turtlebot4_desktop/                  # Visualization tools
│   ├── turtlebot4_desktop/              # Metapackage
│   └── turtlebot4_viz/                  # ⭐ RViz launch & config
│
├── turtlebot4_simulator/               # ⭐ Simulation packages
│   ├── turtlebot4_ignition_bringup/     # Launch, worlds, config
│   ├── turtlebot4_ignition_gui_plugins/ # Ignition GUI plugins
│   ├── turtlebot4_ignition_toolbox/     # Bridge tools (HMI node)
│   └── turtlebot4_simulator/            # Metapackage
│
└── turtlebot4_tutorials/               # ⭐ Example code tham khảo
    ├── turtlebot4_python_tutorials/     # Python navigation examples
    ├── turtlebot4_cpp_tutorials/        # C++ example
    ├── turtlebot4_openai_tutorials/     # AI navigation
    └── turtlebot4_tutorials/            # Metapackage
```

---

## 🔴 PHASE 1: Khởi động Simulation (FILES BẮT BUỘC)

### 1.1 Launch files - Khởi tạo môi trường Gazebo

| File | Đường dẫn | Vai trò | Bắt buộc? |
|------|-----------|---------|-----------|
| `turtlebot4_ignition.launch.py` | `turtlebot4_simulator/turtlebot4_ignition_bringup/launch/` | **Entry point chính** - Khởi động Gazebo world + spawn robot | ✅ BẮT BUỘC |
| `ignition.launch.py` | `turtlebot4_simulator/turtlebot4_ignition_bringup/launch/` | Khởi tạo Ignition Gazebo, set resource path, clock bridge | ✅ BẮT BUỘC (gọi bởi file trên) |
| `turtlebot4_spawn.launch.py` | `turtlebot4_simulator/turtlebot4_ignition_bringup/launch/` | Spawn robot + dock, khởi động ROS bridge, hỗ trợ SLAM/Nav2/Localization flags | ✅ BẮT BUỘC (gọi bởi file trên) |
| `ros_ign_bridge.launch.py` | `turtlebot4_simulator/turtlebot4_ignition_bringup/launch/` | Cầu nối topics giữa Ignition ↔ ROS2 (LiDAR, Camera, HMI) | ✅ BẮT BUỘC (gọi bởi spawn) |
| `turtlebot4_nodes.launch.py` | `turtlebot4_simulator/turtlebot4_ignition_bringup/launch/` | Khởi chạy turtlebot4_node + HMI node | ✅ BẮT BUỘC (gọi bởi spawn) |

### 1.2 World files - Môi trường 3D

| File | Đường dẫn | Mô tả |
|------|-----------|-------|
| `warehouse.sdf` | `turtlebot4_ignition_bringup/worlds/` | **World mặc định** - Kho hàng với shelves, bàn, ghế, người |
| `maze.sdf` | `turtlebot4_ignition_bringup/worlds/` | Mê cung |
| `depot.sdf` | `turtlebot4_ignition_bringup/worlds/` | Bãi đỗ |

> [!IMPORTANT]
> **Cho mô phỏng nhà hàng**: Bạn cần tạo file **`restaurant.sdf`** mới trong `turtlebot4_ignition_bringup/worlds/` hoặc chỉnh sửa `warehouse.sdf` thêm bàn ăn, quầy bếp, etc.

### 1.3 Config files

| File | Đường dẫn | Vai trò |
|------|-----------|---------|
| `turtlebot4_node.yaml` | `turtlebot4_ignition_bringup/config/` | Cấu hình buttons, menu, controller cho sim |
| `gui.config` (lite) | `turtlebot4_ignition_bringup/gui/lite/` | Giao diện Gazebo cho model lite |
| `gui.config` (standard) | `turtlebot4_ignition_bringup/gui/standard/` | Giao diện Gazebo cho model standard |

### 1.4 Robot Description (URDF/Xacro)

| File | Đường dẫn | Vai trò |
|------|-----------|---------|
| `turtlebot4.urdf.xacro` (lite) | `turtlebot4_description/urdf/lite/` | Model robot lite |
| `turtlebot4.urdf.xacro` (standard) | `turtlebot4_description/urdf/standard/` | Model robot standard + HMI tower |
| `rplidar.urdf.xacro` | `turtlebot4_description/urdf/sensors/` | Sensor LiDAR |
| `oakd.urdf.xacro` | `turtlebot4_description/urdf/sensors/` | Camera OAK-D |
| `robot_description.launch.py` | `turtlebot4_description/launch/` | Publish robot description URDF |

### Lệnh khởi động:
```bash
# Khởi động simulation cơ bản (warehouse world, model standard)
ros2 launch turtlebot4_ignition_bringup turtlebot4_ignition.launch.py

# Hoặc với tùy chọn
ros2 launch turtlebot4_ignition_bringup turtlebot4_ignition.launch.py \
    world:=warehouse model:=standard rviz:=true
```

---

## 🟡 PHASE 2: Xây dựng Bản đồ mới (SLAM)

### 2.1 Files cần thiết cho SLAM

| File | Đường dẫn | Vai trò | Bắt buộc? |
|------|-----------|---------|-----------|
| `slam.launch.py` | `turtlebot4_navigation/launch/` | Launch SLAM Toolbox (sync hoặc async) | ✅ BẮT BUỘC |
| `slam.yaml` | `turtlebot4_navigation/config/` | Tham số SLAM: resolution, loop closure, scan matching | ✅ BẮT BUỘC |
| `nav2.launch.py` | `turtlebot4_navigation/launch/` | Launch Nav2 stack (cần cho di chuyển khi mapping) | ✅ BẮT BUỘC |
| `nav2.yaml` | `turtlebot4_navigation/config/` | Tham số Nav2: controller, planner, costmap, behavior | ✅ BẮT BUỘC |

### 2.2 Quy trình tạo bản đồ:

```bash
# Bước 1: Khởi động simulation VỚI SLAM + Nav2
ros2 launch turtlebot4_ignition_bringup turtlebot4_ignition.launch.py \
    slam:=true nav2:=true rviz:=true

# Bước 2: Điều khiển robot bằng teleop (di chuyển khắp nhà hàng)
ros2 run teleop_twist_keyboard teleop_twist_keyboard

# Bước 3: Lưu bản đồ khi hoàn tất
ros2 run nav2_map_server map_saver_cli -f ~/turtlebot4_ws/src/turtlebot4/turtlebot4_navigation/maps/restaurant
```

### 2.3 Output sau khi tạo bản đồ:

Sẽ tạo ra 2 file trong `turtlebot4_navigation/maps/`:
- `restaurant.pgm` - Ảnh bản đồ (occupancy grid)
- `restaurant.yaml` - Metadata bản đồ (resolution, origin, thresholds)

### Maps có sẵn (tham khảo):

| File | Mô tả |
|------|-------|
| `warehouse.pgm` + `warehouse.yaml` | Bản đồ warehouse (mặc định) |
| `maze.pgm` + `maze.yaml` | Bản đồ mê cung |
| `depot.pgm` + `depot.yaml` | Bản đồ depot |

---

## 🟢 PHASE 3: Navigation với bản đồ đã tạo

### 3.1 Files cần thiết cho Navigation

| File | Đường dẫn | Vai trò | Bắt buộc? |
|------|-----------|---------|-----------|
| `localization.launch.py` | `turtlebot4_navigation/launch/` | Chạy AMCL - định vị robot trên bản đồ | ✅ BẮT BUỘC |
| `localization.yaml` | `turtlebot4_navigation/config/` | Tham số AMCL: particle filter, scan matching | ✅ BẮT BUỘC |
| `nav2.launch.py` | `turtlebot4_navigation/launch/` | Launch Nav2 navigation stack | ✅ BẮT BUỘC |
| `nav2.yaml` | `turtlebot4_navigation/config/` | Tham số đầy đủ Nav2 | ✅ BẮT BUỘC |
| `restaurant.yaml` + `.pgm` | `turtlebot4_navigation/maps/` | Bản đồ nhà hàng (tạo ở Phase 2) | ✅ BẮT BUỘC |

### 3.2 Navigation API (thư viện chính)

| File | Đường dẫn | Vai trò | Bắt buộc? |
|------|-----------|---------|-----------|
| `turtlebot4_navigator.py` | `turtlebot4_navigation/turtlebot4_navigation/` | **⭐ API CHÍNH** - Kế thừa `BasicNavigator` của Nav2, cung cấp: | ✅ BẮT BUỘC |

**Các phương thức quan trọng trong `TurtleBot4Navigator`:**

| Phương thức | Chức năng |
|-------------|-----------|
| `getPoseStamped([x, y], direction)` | Tạo goal pose từ tọa độ [x,y] và hướng |
| `setInitialPose(pose)` | Set vị trí ban đầu của robot trên map |
| `waitUntilNav2Active()` | Chờ Nav2 stack sẵn sàng |
| `startToPose(pose)` | Di chuyển đến 1 vị trí cụ thể |
| `startThroughPoses(poses)` | Di chuyển qua nhiều điểm liên tiếp |
| `startFollowWaypoints(poses)` | Đi theo waypoints tuần tự |
| `dock()` / `undock()` | Dock/Undock từ trạm sạc |
| `getDockedStatus()` | Kiểm tra trạng thái dock |
| `createPath()` | Tạo đường đi bằng RViz tool |

**Hướng di chuyển `TurtleBot4Directions`:**

| Hằng số | Giá trị (độ) |
|---------|--------------|
| `NORTH` | 0 |
| `NORTH_WEST` | 45 |
| `WEST` | 90 |
| `SOUTH_WEST` | 135 |
| `SOUTH` | 180 |
| `SOUTH_EAST` | 225 |
| `EAST` | 270 |
| `NORTH_EAST` | 315 |

### 3.3 Lệnh khởi động Navigation:

```bash
# Khởi động simulation VỚI localization + Nav2 + bản đồ restaurant
ros2 launch turtlebot4_ignition_bringup turtlebot4_ignition.launch.py \
    localization:=true nav2:=true rviz:=true \
    map:=$(ros2 pkg prefix turtlebot4_navigation)/share/turtlebot4_navigation/maps/restaurant.yaml
```

---

## 🔵 PHASE 4: Mô phỏng Nhà hàng & Giao đồ ăn

### 4.1 Files tham khảo từ tutorials

| File | Đường dẫn | Mô tả | Tham khảo cho |
|------|-----------|-------|---------------|
| `mail_delivery.py` ⭐ | `turtlebot4_python_tutorials/` | **Mẫu delivery service** - Chọn vị trí → di chuyển đến | Giao đồ ăn đến bàn |
| `nav_to_pose.py` | `turtlebot4_python_tutorials/` | Di chuyển đến 1 vị trí | Giao 1 đơn |
| `follow_waypoints.py` | `turtlebot4_python_tutorials/` | Đi theo nhiều waypoints | Giao nhiều bàn liên tiếp |
| `nav_through_poses.py` | `turtlebot4_python_tutorials/` | Qua nhiều poses không dừng | Di chuyển tối ưu |
| `patrol_loop.py` | `turtlebot4_python_tutorials/` | Tuần tra + quản lý pin | Robot chờ đơn + sạc pin |
| `create_path.py` | `turtlebot4_python_tutorials/` | Tạo path từ RViz | Tạo đường đi bằng tay |
| `setup.py` | `turtlebot4_python_tutorials/` | Entry points đăng ký scripts | Đăng ký script mới |

### 4.2 Files CẦN TẠO MỚI cho Restaurant Simulation

#### 📁 Cấu trúc đề xuất:

```
turtlebot4_ws/src/
├── restaurant_robot/                    # [NEW] Package mới cho nhà hàng
│   ├── package.xml
│   ├── setup.py
│   ├── setup.cfg
│   ├── resource/restaurant_robot
│   ├── config/
│   │   └── restaurant_tables.yaml       # Cấu hình vị trí các bàn ăn
│   ├── worlds/
│   │   └── restaurant.sdf              # World Gazebo cho nhà hàng
│   ├── maps/
│   │   ├── restaurant.pgm              # Bản đồ (tạo bằng SLAM)
│   │   └── restaurant.yaml             # Metadata bản đồ
│   ├── launch/
│   │   ├── restaurant_simulation.launch.py   # Launch mô phỏng nhà hàng
│   │   └── restaurant_delivery.launch.py     # Launch node giao đồ ăn
│   └── restaurant_robot/
│       ├── __init__.py
│       ├── food_delivery_node.py        # ⭐ Node chính giao đồ ăn
│       ├── order_manager.py             # Quản lý đơn hàng
│       └── table_positions.py           # Vị trí các bàn (tọa độ)
│
└── ... (các packages gốc giữ nguyên)
```

#### 📄 File: `config/restaurant_tables.yaml`
```yaml
# Vị trí các bàn ăn trên bản đồ (x, y, hướng)
kitchen:
  position: [0.0, 0.0]
  direction: "NORTH"  # Nơi nhận đồ ăn

tables:
  table_1:
    position: [3.0, 2.0]
    direction: "EAST"
    name: "Bàn 1"
  table_2:
    position: [3.0, 5.0]
    direction: "EAST"
    name: "Bàn 2"
  table_3:
    position: [-3.0, 2.0]
    direction: "WEST"
    name: "Bàn 3"
  table_4:
    position: [-3.0, 5.0]
    direction: "WEST"
    name: "Bàn 4"

dock_station:
  position: [-1.0, -1.0]
  direction: "NORTH"
```

#### 📄 File: `food_delivery_node.py` (dựa trên `mail_delivery.py`)
```python
#!/usr/bin/env python3
"""
Restaurant Food Delivery Node
Dựa trên mail_delivery.py, mở rộng cho nhà hàng
Logic này GIỮ NGUYÊN khi port sang robot thực tế
"""
import rclpy
from turtlebot4_navigation.turtlebot4_navigator import (
    TurtleBot4Directions, TurtleBot4Navigator
)

# Mapping string → enum
DIRECTION_MAP = {
    'NORTH': TurtleBot4Directions.NORTH,
    'SOUTH': TurtleBot4Directions.SOUTH,
    'EAST': TurtleBot4Directions.EAST,
    'WEST': TurtleBot4Directions.WEST,
    # ... thêm các hướng khác
}

def main(args=None):
    rclpy.init(args=args)
    navigator = TurtleBot4Navigator()

    # Dock và set initial pose
    if not navigator.getDockedStatus():
        navigator.dock()

    initial_pose = navigator.getPoseStamped([0.0, 0.0], TurtleBot4Directions.NORTH)
    navigator.setInitialPose(initial_pose)
    navigator.waitUntilNav2Active()
    navigator.undock()

    # Định nghĩa vị trí bàn (sẽ đọc từ YAML khi hoàn thiện)
    tables = {
        'kitchen': navigator.getPoseStamped([0.0, 0.0], TurtleBot4Directions.NORTH),
        'table_1': navigator.getPoseStamped([3.0, 2.0], TurtleBot4Directions.EAST),
        'table_2': navigator.getPoseStamped([3.0, 5.0], TurtleBot4Directions.EAST),
        'table_3': navigator.getPoseStamped([-3.0, 2.0], TurtleBot4Directions.WEST),
        'table_4': navigator.getPoseStamped([-3.0, 5.0], TurtleBot4Directions.WEST),
    }

    navigator.info('=== RESTAURANT DELIVERY SERVICE ===')

    while True:
        print('\nChọn bàn giao đồ ăn:')
        print('  0. Quay về bếp (Kitchen)')
        print('  1. Bàn 1')
        print('  2. Bàn 2')
        print('  3. Bàn 3')
        print('  4. Bàn 4')
        print('  5. Thoát')

        try:
            choice = int(input('Lựa chọn: '))
        except ValueError:
            navigator.error('Vui lòng nhập số!')
            continue

        if choice == 5:
            break
        elif choice == 0:
            navigator.info('Đang quay về bếp...')
            navigator.startToPose(tables['kitchen'])
        elif 1 <= choice <= 4:
            table_key = f'table_{choice}'
            navigator.info(f'Đang giao đồ ăn đến {table_key}...')
            navigator.startToPose(tables[table_key])
            navigator.info(f'Đã đến {table_key}! Đợi 5 giây...')
            import time; time.sleep(5)
            navigator.info('Quay về bếp...')
            navigator.startToPose(tables['kitchen'])
        else:
            navigator.error('Lựa chọn không hợp lệ!')

    navigator.dock()
    rclpy.shutdown()

if __name__ == '__main__':
    main()
```

---

## 🟣 PHASE 5: Port sang Robot thực tế

### 5.1 Phân tích khả năng Port

| Layer | Files | Port? | Ghi chú |
|-------|-------|-------|---------|
| **Navigation Logic** | `food_delivery_node.py`, `order_manager.py`, `table_positions.py` | ✅ **GIỮ NGUYÊN 100%** | Dùng `TurtleBot4Navigator` API - hoạt động cả sim & thực |
| **Navigation API** | `turtlebot4_navigator.py` | ✅ **GIỮ NGUYÊN** | Kế thừa BasicNavigator, tương thích cả 2 |
| **Navigation Config** | `nav2.yaml`, `localization.yaml`, `slam.yaml` | ⚠️ **TINH CHỈNH** | Cần tune tham số cho robot thực (velocity, costmap radius, sensor params) |
| **Table Positions** | `restaurant_tables.yaml` | ⚠️ **CẬP NHẬT** | Tọa độ bàn phải đo lại trên bản đồ thực |
| **Map** | `restaurant.pgm` + `.yaml` | 🔄 **TẠO LẠI** | Phải SLAM lại bản đồ trong nhà hàng thực |
| **Simulation** | `turtlebot4_ignition_bringup/*` | ❌ **KHÔNG CẦN** | Chỉ dùng cho simulation |
| **World SDF** | `restaurant.sdf` | ❌ **KHÔNG CẦN** | Chỉ dùng cho Gazebo |
| **ROS Bridge** | `ros_ign_bridge.launch.py` | ❌ **KHÔNG CẦN** | Robot thực dùng drivers gốc |
| **URDF/Xacro** | `turtlebot4_description/*` | ✅ **CÓ SẴN** | Đã nằm trong firmware robot |
| **Robot Node** | `turtlebot4_node/*` (C++) | ✅ **CÓ SẴN** | Đã nằm trong firmware robot |

### 5.2 Cụ thể: Files cần thay đổi khi port

```
Chỉ cần thay đổi:
┌──────────────────────────────────────────────────────────┐
│  1. Tạo bản đồ mới bằng SLAM trong nhà hàng thực       │
│  2. Cập nhật tọa độ bàn trong restaurant_tables.yaml    │
│  3. Đổi use_sim_time: true → false trong config files   │
│  4. Tune nav2.yaml cho robot thực (nếu cần)             │
└──────────────────────────────────────────────────────────┘

KHÔNG cần thay đổi:
┌──────────────────────────────────────────────────────────┐
│  ✅ food_delivery_node.py    (giữ nguyên logic)          │
│  ✅ order_manager.py         (giữ nguyên logic)          │
│  ✅ turtlebot4_navigator.py  (API tương thích)           │
│  ✅ localization.launch.py   (chỉ đổi use_sim_time)     │
│  ✅ nav2.launch.py           (chỉ đổi use_sim_time)     │
│  ✅ slam.launch.py           (chỉ đổi use_sim_time)     │
└──────────────────────────────────────────────────────────┘
```

### 5.3 Lệnh chạy trên robot thực:

```bash
# SLAM (tạo bản đồ nhà hàng thực)
ros2 launch turtlebot4_navigation slam.launch.py use_sim_time:=false

# Navigation với bản đồ thực
ros2 launch turtlebot4_navigation localization.launch.py \
    use_sim_time:=false map:=/path/to/real_restaurant.yaml
ros2 launch turtlebot4_navigation nav2.launch.py use_sim_time:=false

# Chạy food delivery node (CODE GIỐNG HỆT trong sim)
ros2 run restaurant_robot food_delivery_node
```

---

## 📋 Checklist tổng hợp theo thứ tự thực hiện

### Phase 1: Setup Simulation
- [ ] Build workspace: `colcon build`
- [ ] Chạy thử simulation mặc định: `ros2 launch turtlebot4_ignition_bringup turtlebot4_ignition.launch.py`
- [ ] Click Play ▶️ trong Gazebo

### Phase 2: Tạo World nhà hàng
- [ ] Tạo file `restaurant.sdf` (copy/modify `warehouse.sdf`)
- [ ] Thêm model bàn, ghế, quầy bếp vào world
- [ ] Test launch với world mới: `world:=restaurant`

### Phase 3: SLAM - Xây dựng bản đồ
- [ ] Launch simulation với `slam:=true nav2:=true`
- [ ] Điều khiển robot khám phá toàn bộ nhà hàng
- [ ] Lưu bản đồ bằng `map_saver_cli`
- [ ] Kiểm tra file `.pgm` + `.yaml` đã tạo

### Phase 4: Navigation Test
- [ ] Launch với `localization:=true nav2:=true` + map file
- [ ] Test `nav_to_pose.py` với các tọa độ trong nhà hàng
- [ ] Xác định tọa độ chính xác cho từng bàn ăn

### Phase 5: Food Delivery System
- [ ] Tạo package `restaurant_robot`
- [ ] Tạo file `restaurant_tables.yaml` với tọa độ bàn
- [ ] Phát triển `food_delivery_node.py`
- [ ] Đăng ký entry_point trong `setup.py`
- [ ] Build và test: `colcon build && ros2 run restaurant_robot food_delivery_node`

### Phase 6: Port sang Robot thực
- [ ] Tạo bản đồ thực bằng SLAM (use_sim_time:=false)
- [ ] Đo lại tọa độ bàn trên bản đồ thực
- [ ] Cập nhật `restaurant_tables.yaml`
- [ ] Test từng bàn một
- [ ] Test full delivery loop

---

## 🗺️ Dependency Graph - File nào gọi file nào

```
turtlebot4_ignition.launch.py (ENTRY POINT)
├── ignition.launch.py
│   ├── ros_ign_gazebo (ign_gazebo.launch.py)  [external]
│   ├── warehouse.sdf / restaurant.sdf         [world]
│   └── gui.config                             [GUI]
│
└── turtlebot4_spawn.launch.py
    ├── robot_description.launch.py            [URDF]
    │   └── turtlebot4.urdf.xacro
    │       ├── rplidar.urdf.xacro
    │       └── oakd.urdf.xacro
    ├── ros_ign_bridge.launch.py               [Bridge]
    ├── turtlebot4_nodes.launch.py             [Nodes]
    │   └── turtlebot4_node.yaml
    ├── create3_nodes.launch.py                [external]
    ├── create3_ignition_nodes.launch.py       [external]
    ├── dock_description.launch.py             [external]
    │
    ├── (optional) localization.launch.py
    │   └── localization.yaml
    │       └── map: restaurant.yaml + .pgm
    │
    ├── (optional) slam.launch.py
    │   └── slam.yaml
    │
    ├── (optional) nav2.launch.py
    │   └── nav2.yaml
    │
    └── (optional) view_robot.launch.py        [RViz]
        └── robot.rviz
```

```
food_delivery_node.py (YOUR CODE)
└── turtlebot4_navigator.py (API)
    └── BasicNavigator (nav2_simple_commander) [external]
        ├── Nav2 stack (planner, controller, costmap, behavior)
        ├── AMCL (localization)
        └── map_server
```

---

## ⚡ Quick Reference - Lệnh thường dùng

```bash
# === BUILD ===
cd ~/turtlebot4_ws && colcon build --symlink-install
source install/setup.bash

# === SIMULATION ===
# Chỉ simulation
ros2 launch turtlebot4_ignition_bringup turtlebot4_ignition.launch.py

# Simulation + SLAM + Nav2 (để tạo bản đồ)
ros2 launch turtlebot4_ignition_bringup turtlebot4_ignition.launch.py \
    slam:=true nav2:=true rviz:=true

# Simulation + Localization + Nav2 (dùng bản đồ có sẵn)
ros2 launch turtlebot4_ignition_bringup turtlebot4_ignition.launch.py \
    localization:=true nav2:=true rviz:=true

# === MAP ===
# Lưu bản đồ
ros2 run nav2_map_server map_saver_cli -f ~/turtlebot4_ws/src/turtlebot4/turtlebot4_navigation/maps/restaurant

# === TELEOP ===
ros2 run teleop_twist_keyboard teleop_twist_keyboard

# === NAVIGATION ===
ros2 run turtlebot4_python_tutorials nav_to_pose
ros2 run turtlebot4_python_tutorials mail_delivery
ros2 run turtlebot4_python_tutorials follow_waypoints
```

---

> **Tác giả**: Auto-generated planning document
> **Ngày tạo**: 2026-03-28
> **Target**: TurtleBot4 Restaurant Delivery Simulation → Real Robot

