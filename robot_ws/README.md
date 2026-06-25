# robot_ws — ROS 2 (Humble) workspace

Workspace `colcon` cho robot **TurtleBot 4** chạy task **giao đồ ăn (food_delivery)** trong
nhà hàng — cả ở **mô phỏng (Ignition Gazebo)** lẫn **robot thật (Jetson)**.

`sim/` và `real/` là **2 con robot KHÁC NHAU** (chỉ giống nhau về logic code), nên `src/` chia
theo **nơi triển khai** (deployment target) và **mỗi bên hoàn toàn độc lập — không có thư mục
`common/` dùng chung**. Mỗi máy chỉ build đúng phần nó cần (Jetson không phải build đồ mô phỏng nặng):

```
src/
├── sim/      # CHỈ build trên PC (mô phỏng) — TurtleBot4 đầy đủ
│   ├── turtlebot4_description/        # URDF + mesh robot
│   ├── turtlebot4_msgs/               # message tùy biến
│   ├── turtlebot4_navigation/         # SLAM / Nav2 / localization + maps + helper điều hướng
│   ├── turtlebot4_viz/                # RViz
│   ├── turtlebot4_node/               # driver OLED/LED/nút
│   ├── turtlebot4_ignition_bringup/   # worlds, spawn robot, ROS↔IGN bridge
│   └── turtlebot4_python_tutorials/   # node food_delivery (logic task)
│
└── real/     # CHỈ build trên Jetson (robot thật) — phần cứng riêng
```

---

## 1. Cài đặt (chỉ làm 1 lần)

Yêu cầu hệ thống:

- **Ubuntu 22.04**
- **ROS 2 Humble** cài tại `/opt/ros/humble` — [hướng dẫn cài](https://docs.ros.org/en/humble/Installation.html)
- **Ignition Gazebo** (cho mô phỏng)
- **python3.10-venv** (để `setup_env.sh` tạo được virtualenv):

```bash
sudo apt install python3.10-venv
```

> Nếu thiếu `python3.10-venv`, lần đầu chạy `setup_env.sh` sẽ báo lỗi
> *"ensurepip is not available"* và không tạo được `.venv`.

Sau đó clone repo và vào thư mục workspace:

```bash
git clone <repo-url>
cd <repo>/robot_ws
```

---

## 2. Chạy mô phỏng (PC)

### Build + source môi trường

```bash
cd robot_ws
source setup_env.sh sim
```

Một lệnh này làm 4 việc: (1) source ROS 2 Humble → (2) tạo/active `.venv` →
(3) `colcon build` các package trong `sim/` → (4) source `install/`.
**Không cần `colcon build` riêng.**

> ⚠️ **Mỗi terminal mới** đều phải `source setup_env.sh sim` lại trước khi `ros2 run/launch`,
> nếu không ROS sẽ báo không tìm thấy package (vd `food_delivery`).
> Khi chỉ sửa code (không thêm package) có thể dùng tối thiểu `source install/setup.bash`.

### ⚠️ Trước khi chạy: tạo 7 marker ArUco

World nhà hàng cần **7 ảnh marker ArUco**. Repo **không kèm sẵn** các file này (đã bị xóa vì nội
dung sai), nên **bạn phải tự tạo trước khi chạy sim**, nếu không các marker trong sim sẽ trống/thiếu
texture. `restaurant.sdf` đã trỏ sẵn tên file + vị trí gắn, nên **chỉ cần tạo đúng tên rồi thả vào
đúng thư mục là chạy được ngay — không cần sửa SDF**.

- **Dictionary:** `cv2.aruco.DICT_4X4_50`, 7 marker **ID 0 → 6** (ID 0 = Dock/bếp, ID 1–6 = Bàn 1–6).
- **Đặt tên:** `aruco_marker_0.png`, `aruco_marker_1.png`, … `aruco_marker_6.png`
- **Thả vào:** `src/sim/turtlebot4_ignition_bringup/worlds/`

Ví dụ sinh nhanh bằng OpenCV:

```python
import cv2
d = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
for i in range(7):
    img = cv2.aruco.generateImageMarker(d, i, 600)
    cv2.imwrite(f"src/sim/turtlebot4_ignition_bringup/worlds/aruco_marker_{i}.png", img)
```

Chi tiết toạ độ/hướng từng marker xem mục 5 và [`docs/restaurant_positions.md`](docs/restaurant_positions.md).

### Khởi động sim + điều hướng

```bash
# Sim + Nav2 + localization (map nhà hàng) + RViz
ros2 launch turtlebot4_ignition_bringup turtlebot4_ignition.launch.py \
  nav2:=true slam:=false localization:=true rviz:=true
```

```bash
# Terminal KHÁC (nhớ source setup_env.sh sim lại) — chạy task giao đồ ăn
ros2 run turtlebot4_python_tutorials food_delivery
```

Hai lệnh trên là luồng chính để dev/test. Lệnh phụ khi cần:

```bash
ros2 launch turtlebot4_navigation slam.launch.py    # quét/tạo map mới
ros2 launch turtlebot4_viz view_robot.launch.py     # chỉ mở RViz xem robot
```

---

## 3. Có những code gì (các package)

| Package | Thư mục | Vai trò |
|---|---|---|
| `turtlebot4_description` | `sim/` | URDF + mesh robot (model **standard**), `robot_state_publisher` |
| `turtlebot4_msgs` | `sim/` | Message tùy biến (vd `UserDisplay`) |
| `turtlebot4_navigation` | `sim/` | Launch **SLAM / Nav2 / localization** + config + **maps** + class `TurtleBot4Navigator` |
| `turtlebot4_viz` | `sim/` | RViz (`view_robot`) |
| `turtlebot4_node` | `sim/` | Node C++ giao diện vật lý (màn OLED / nút / LED) |
| `turtlebot4_ignition_bringup` | `sim/` | Mô phỏng Ignition: **worlds**, spawn robot, ROS↔IGN bridge, gui config |
| `turtlebot4_python_tutorials` | `sim/` | **Node `food_delivery`** — logic task chính |

`food_delivery` phụ thuộc chính vào `turtlebot4_navigation.turtlebot4_navigator`
(`TurtleBot4Navigator`, `TurtleBot4Directions`).

---

## 4. Code task: `food_delivery`

File: [`src/sim/turtlebot4_python_tutorials/turtlebot4_python_tutorials/food_delivery.py`](src/sim/turtlebot4_python_tutorials/turtlebot4_python_tutorials/food_delivery.py)

Luồng hiện tại:

1. **Khởi tạo** — set init pose = spawn cố định. Bật camera quét ArUco marker **dock (ID 0)**;
   không thấy thì xoay 1 vòng tìm, thấy thì align vào marker.
2. **Chọn bàn** — Nav2/AMCL đưa robot tới *approach pose* của bàn rồi dừng.
3. **Về Dock** — Nav2 đưa robot về spawn rồi dừng.

Chỗ để mở rộng:

- `visual_align()` / `search_marker_360()` — căn chỉnh bằng camera (P-controller trên `/cmd_vel`).
- Bảng `TABLES` (ID 1–6 + approach pose) — sửa/thêm bàn ở đây.
- Quét ArUco **tại bàn** (hiện mới chỉ quét ở dock) — còn để trống, có thể bổ sung.

> Lưu ý 2 hệ toạ độ: approach pose trong `food_delivery.py` ở **frame map SLAM**; còn vị trí
> marker trong `docs/restaurant_positions.md` ở **frame world SDF**. Hai cái lệch nhau vì map
> được tạo lúc robot đứng ở spawn. Khi code nav, dùng pose theo **frame map**.

Entry point khai báo ở [`src/sim/turtlebot4_python_tutorials/setup.py`](src/sim/turtlebot4_python_tutorials/setup.py)
→ `food_delivery = ...food_delivery:main`. Thêm node mới thì thêm dòng vào `console_scripts`.

---

## 5. ArUco markers — phần cần làm để test

- Dictionary **`cv2.aruco.DICT_4X4_50`**, dùng **7 marker ID 0–6**.
- **ID 0 = Dock (bếp)**, **ID 1–6 = Bàn 1–6**.
- Toạ độ chi tiết (x/y/z/yaw từng marker): [`docs/restaurant_positions.md`](docs/restaurant_positions.md).

> ⚠️ **Trạng thái:** 7 file texture marker cũ (`aruco_marker_0..6.png`) **đã bị xóa** vì nội dung
> sai. `restaurant.sdf` vẫn giữ nguyên tham chiếu tên file + vị trí gắn, nên **chỉ cần tạo lại file
> đúng tên là chạy được**. Tới khi tạo lại, chạy sim chỗ marker sẽ trống/thiếu texture.

**TODO — tạo lại 7 marker:**

1. Sinh ảnh marker `DICT_4X4_50`, ID 0 → 6 (vd `cv2.aruco.generateImageMarker` hoặc trang in online).
2. Lưu **đúng tên + đúng chỗ cũ**:
   `src/sim/turtlebot4_ignition_bringup/worlds/aruco_marker_0.png` … `aruco_marker_6.png`
   (vị trí gắn trong `restaurant.sdf` đã đúng sẵn — **không cần sửa SDF**).
3. Mapping: ID 0 = Dock/bếp, ID 1–6 = Bàn 1–6 (toạ độ xem `docs/restaurant_positions.md`).
4. Lên **robot thật**: in marker ra giấy, dán đúng vị trí, đảm bảo nằm trong tầm camera **OAK-D**
   (trong sim ~`z=1.25`), rồi chỉnh approach pose trong `TABLES` (food_delivery.py) cho khớp thực tế.

---

## 6. Chạy thực tế (Jetson)

Trên robot thật (Jetson Orin Nano) dùng profile `real` — **chỉ** build `real/`, **không**
build đồ mô phỏng:

```bash
cd robot_ws
source setup_env.sh real
```

Profile `real` build các driver phần cứng trong `src/real/`. Đây là con robot riêng (khác
TurtleBot4 ở `sim/`), nên các package điều hướng/driver của nó nằm gọn trong `real/`. Các marker
ArUco in ra giấy và dán đúng vị trí như mục 5.

---

## 7. Tham khảo nhanh

| Cần gì | Ở đâu |
|---|---|
| Vị trí spawn + marker | [`docs/restaurant_positions.md`](docs/restaurant_positions.md) |
| Map đang dùng | `src/sim/turtlebot4_navigation/maps/restaurant.{pgm,yaml}` |
| World sim | `src/sim/turtlebot4_ignition_bringup/worlds/restaurant.sdf` |
| Helper điều hướng | `src/sim/turtlebot4_navigation/turtlebot4_navigation/turtlebot4_navigator.py` |
| Config Nav2 / localization / slam | `src/sim/turtlebot4_navigation/config/` |
| License vendor turtlebot4 | [`docs/TURTLEBOT4_UPSTREAM_LICENSE`](docs/TURTLEBOT4_UPSTREAM_LICENSE) |

> Build artifacts (`build/`, `install/`, `log/`, `.venv/`) đã được gitignore — không commit.
</content>
</invoke>
