# robot_ws — ROS2 (Humble) workspace

Một colcon workspace duy nhất, `src/` chia theo **deployment target** chứ không phải
theo loại code. Mục đích: **build subset** cho từng máy, tránh kéo đồ mô phỏng nặng lên Jetson.

```
src/
├── common/   # chạy ở CẢ sim lẫn robot thật — build ở mọi profile
│   ├── ai_waiter_core/        # LLM/RAG orchestrator (brain)
│   ├── ai_waiter_nav/         # navigation (depends turtlebot4_navigation/_viz)
│   ├── turtlebot4_description/  turtlebot4_msgs/
│   ├── turtlebot4_navigation/  turtlebot4_viz/
│   └── turtlebot4_node/       # driver OLED/LED/nút — sim cũng build-depend qua bringup
│
├── sim/      # CHỈ mô phỏng — chỉ build trên PC (demo 1)
│   ├── ai_waiter_ros/         # worlds, models, sim_restaurant.launch
│   ├── turtlebot4_ignition_bringup/
│   └── turtlebot4_python_tutorials/   # node food_delivery
│
└── real/     # CHỈ robot thật — chỉ build trên Jetson (demo 2)
    └── ai_hw_bridge/          # cầu nối phần cứng (đang COLCON_IGNORE — stub)
```

## Build theo profile

```bash
# PC — demo 1: LLM + mô phỏng (gazebo/ignition)
source setup_env.sh sim     # = colcon build --base-paths src/common src/sim

# Jetson Orin Nano — demo 2: LLM + robot thật (nhẹ, không có sim)
source setup_env.sh real    # = colcon build --base-paths src/common src/real
```

Mỗi terminal mới phải `source setup_env.sh <profile>` lại trước khi `ros2 run/launch`.

## Lưu ý

- **Python/uv:** lớp ROS dùng `venv --system-site-packages` (xem `setup_env.sh`), **không** dùng
  `uv sync`. Phần LLM/RAG dev+eval dùng uv ở root repo. Hai môi trường tách nhau.
- **`ai_waiter_msgs`:** `sim/ai_waiter_ros/package.xml` đang depend package này nhưng **chưa tồn
  tại** trong workspace — cần tạo (hoặc bỏ dep) thì `ai_waiter_ros` mới build được. (Pre-existing.)
- **Docs:** [docs/DEV_GUIDE.md](docs/DEV_GUIDE.md) (food_delivery — đường dẫn trong đó giờ là
  `src/sim/turtlebot4_python_tutorials/...`), [docs/restaurant_positions.md](docs/restaurant_positions.md),
  [docs/PLANNING_RESTAURANT_SIMULATION.md](docs/PLANNING_RESTAURANT_SIMULATION.md).
- `turtlebot4_*` là code vendor (đã bỏ `.git` lồng). License upstream:
  [docs/TURTLEBOT4_UPSTREAM_LICENSE](docs/TURTLEBOT4_UPSTREAM_LICENSE).
