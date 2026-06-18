# TurtleBot4 — Dev Guide (food_delivery)

Tài liệu này dành cho người tiếp tục code phần **food_delivery**. Mô tả cấu trúc source, cách
chạy, vị trí code cần sửa, và phần ArUco còn phải làm để test.

> Source đã được dọn gọn: từ 14 package còn **7 package**, chỉ giữ robot **standard**
> (đã bỏ model `lite`), bỏ GUI/HMI mô phỏng và các package tutorial không dùng.

---

## 1. Chạy thử (Quick start)

> Yêu cầu: ROS 2 **Humble** ở `/opt/ros/humble`, Ignition Gazebo.

```bash
cd ~/turtlebot4
source setup_env.sh        # (1) source ROS Humble  (2) tạo/active .venv  (3) colcon build  (4) source install/
```

`setup_env.sh` **đã tự build + source** rồi, nên không cần `colcon build` riêng. Sau khi source xong:

```bash
# Sim + Nav2 + localization (map restaurant) + RViz
ros2 launch turtlebot4_ignition_bringup turtlebot4_ignition.launch.py nav2:=true slam:=false localization:=true rviz:=true

# Chạy task giao đồ ăn (ở terminal khác — nhớ source setup_env.sh lại)
ros2 run turtlebot4_python_tutorials food_delivery
```

Hai lệnh trên là luồng chính để dev/test. Hai lệnh phụ khi cần:

```bash
ros2 launch turtlebot4_navigation slam.launch.py     # quét/tạo map mới
ros2 launch turtlebot4_viz view_robot.launch.py      # chỉ mở RViz xem robot
```

> ⚠️ Mỗi terminal mới đều phải `source setup_env.sh` (hoặc tối thiểu `source install/setup.bash`)
> trước khi `ros2 run/launch`, nếu không sẽ báo không tìm thấy `food_delivery`.

---

## 2. Cấu trúc source (`src/`)

7 package nằm phẳng trực tiếp dưới `src/`:

| Package | Vai trò |
|---|---|
| `turtlebot4_description` | URDF + mesh robot (chỉ model **standard**), `robot_state_publisher` |
| `turtlebot4_msgs` | Message tùy biến (vd `UserDisplay`) |
| `turtlebot4_node` | Node C++ giao diện vật lý robot (màn OLED / nút / LED) — **dùng cho robot thật** |
| `turtlebot4_navigation` | Launch **SLAM / Nav2 / localization** + config + **maps** + class `TurtleBot4Navigator` |
| `turtlebot4_viz` | RViz (`view_robot`) |
| `turtlebot4_ignition_bringup` | Mô phỏng Ignition: **worlds**, spawn robot, ROS↔IGN bridge, gui config |
| `turtlebot4_python_tutorials` | **Node `food_delivery`** (logic task của mình) |

Phụ thuộc chính của food_delivery: `turtlebot4_navigation.turtlebot4_navigator`
(`TurtleBot4Navigator`, `TurtleBot4Directions`).

---

## 3. Code task: `food_delivery`

File: [`src/turtlebot4_python_tutorials/turtlebot4_python_tutorials/food_delivery.py`](src/turtlebot4_python_tutorials/turtlebot4_python_tutorials/food_delivery.py)

Luồng hiện tại:

1. **Khởi tạo**: set init pose = spawn cố định. Bật camera quét ArUco marker **dock (ID 0)**;
   nếu không thấy thì xoay 1 vòng tìm; thấy thì align vào marker.
2. **Chọn bàn**: Nav2/AMCL đưa robot tới *approach pose* của bàn rồi dừng.
3. **Về Dock**: Nav2 đưa robot về spawn rồi dừng.

Các phần để mở rộng (gợi ý):
- Hàm `visual_align()` / `search_marker_360()` — căn chỉnh bằng camera (P-controller trên `/cmd_vel`).
- Bảng `TABLES` (ID 1–6 + approach pose) — sửa/thêm bàn ở đây.
- Quét ArUco tại bàn (hiện mới chỉ quét ở dock) — chỗ này còn để trống, có thể bổ sung.

> Lưu ý 2 hệ toạ độ: approach pose trong `food_delivery.py` ở **frame của map SLAM**;
> còn vị trí marker trong `restaurant_positions.md` ở **frame world SDF**. Hai cái lệch nhau vì
> map được tạo lúc robot đứng ở spawn. Khi code nav, dùng pose theo frame map.

Entry point khai báo ở [`setup.py`](src/turtlebot4_python_tutorials/setup.py) →
`food_delivery = ...food_delivery:main`. Thêm node mới thì thêm dòng vào `console_scripts`.

---

## 4. ArUco markers — phần cần làm để test

- Dictionary: **`cv2.aruco.DICT_4X4_50`**. Dùng **7 marker, ID 0–6**.
- **ID 0 = Dock** (bếp). **ID 1–6 = Bàn 1–6**.
- Vị trí chi tiet (toạ độ x/y/z/yaw từng marker) xem: [`restaurant_positions.md`](restaurant_positions.md).

**⚠️ Trạng thái hiện tại:** 7 file texture marker cũ (`aruco_marker_0..6.png`) **đã bị XÓA**
vì nội dung bị **sai**. `restaurant.sdf` vẫn giữ nguyên tham chiếu tên file + vị trí gắn
(các dòng `<albedo_map>aruco_marker_N.png</albedo_map>`), nên **chỉ cần tạo lại file mới đúng tên
là chạy được**. Hiện chạy sim chỗ marker sẽ bị trống/thiếu texture cho tới khi tạo lại.

**🔧 TODO — teammate tự tạo lại 7 marker:**
1. Sinh ảnh marker `DICT_4X4_50`, **ID 0 → 6** (vd `cv2.aruco.generateImageMarker`
   hoặc trang in marker online).
2. Lưu **đúng tên + đúng chỗ cũ**: `src/turtlebot4_ignition_bringup/worlds/aruco_marker_0.png`
   … `aruco_marker_6.png` (vị trí gắn trong `restaurant.sdf` đã đúng sẵn, **không cần sửa SDF**).
3. Mapping: **ID 0 = Dock/bếp**, **ID 1–6 = Bàn 1–6** (toạ độ xem `restaurant_positions.md`).
4. Khi lên **robot thật**: in marker ra giấy, dán đúng vị trí tương ứng, đảm bảo nằm trong tầm
   camera **OAK-D** (độ cao trong sim ~`z=1.25`), rồi chỉnh approach pose trong `TABLES`
   (food_delivery.py) cho khớp môi trường thật.

---

## 5. Tham khảo nhanh

| Cần gì | Ở đâu |
|---|---|
| Vị trí spawn + marker | [`restaurant_positions.md`](restaurant_positions.md) |
| Map đang dùng | `src/turtlebot4_navigation/maps/restaurant.{pgm,yaml}` |
| World sim | `src/turtlebot4_ignition_bringup/worlds/restaurant.sdf` |
| Helper điều hướng | `src/turtlebot4_navigation/turtlebot4_navigation/turtlebot4_navigator.py` |
| Config Nav2 / localization / slam | `src/turtlebot4_navigation/config/` |

> Build artifacts (`build/`, `install/`, `log/`, `.venv/`) đã được gitignore — không commit.
