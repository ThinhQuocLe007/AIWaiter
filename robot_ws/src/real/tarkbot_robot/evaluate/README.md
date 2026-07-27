# Evaluate scripts — Chapter 5 robot navigation

Script ROS2 để thu thập **log + metrics thật** cho các bảng thực nghiệm navigation trong luận văn (odometry, map/localization, nav + docking). Không bịa số: chạy trên robot với map/`rtabmap.db` hiện có, rồi dán kết quả vào `docs/thesis/05-experiments/chapter5-robot-navigation.md`.

## Yêu cầu trước khi chạy

1. Robot đặt tại **dock (ArUco 6)**.
2. Database localize khớp map đã export: `~/.ros/rtabmap.db` (cùng nguồn với `maps/restaurant.pgm` / `restaurant.yaml`).
3. `config/floorplan.json` đã khảo sát (dock + Table 1).
4. Làn phục vụ trống; dừng khẩn bằng Ctrl-C.
5. Workspace đã build + source (**nên dùng symlink-install** để log ghi vào `evaluate/logs/` trong source tree):

```bash
cd robot_ws
colcon build --packages-select tarkbot_robot --symlink-install
source install/setup.bash
```

Tuỳ chọn: đặt thư mục log tường minh:

```bash
export TARKBOT_EVAL_LOG_DIR=/path/to/tarkbot_robot/evaluate/logs
```

## Bring-up (2 terminal)

**T1 — localization (RTAB-Map + EKF + sensors):**

```bash
ros2 launch tarkbot_robot rtabmap_localization.launch.py
```

**T2 — Nav2** (sau khi `/map` và TF `map→odom` ổn định):

```bash
ros2 launch tarkbot_robot navigation.launch.py use_rviz:=true
```

Mỗi bài test chạy ở **T3**. Mặc định **N=5** (đổi bằng `-p n_trials:=N`).

Log mỗi lần chạy: `evaluate/logs/YYYYMMDD_HHMMSS_<test>/`

| File | Nội dung |
|------|----------|
| `metrics.jsonl` | Từng trial (JSON một dòng) |
| `summary.json` | mean ± std / tỷ lệ thành công |
| `console.log` | stdout/stderr |
| `trajectories/trial_XX.csv` | (odometry) quỹ đạo `/odometry/filtered` cho Figure 5.2 |

---

## 1. Map summary (offline, Table 5.2)

Không cần robot. Đọc `restaurant.yaml` + `rtabmap.db`:

```bash
ros2 run tarkbot_robot eval_map_summary -- \
  --db ~/.ros/rtabmap.db \
  --map-yaml $(ros2 pkg prefix tarkbot_robot)/../src/real/tarkbot_robot/maps/restaurant.yaml \
  --duration-min 12 \
  --consistency "lane walls continuous; dock revisit closed"
```

Hoặc từ thư mục package (khi đang ở source tree):

```bash
ros2 run tarkbot_robot eval_map_summary -- \
  --map-yaml robot_ws/src/real/tarkbot_robot/maps/restaurant.yaml \
  --map-pgm robot_ws/src/real/tarkbot_robot/maps/restaurant.pgm \
  --duration-min 12
```

Điền tay **duration** (phút quét map) và ghi chú consistency nếu muốn.

---

## 2. Odometry return-to-start (Table 5.1)

Đường: dock → Table 1 → dock. Chỉ chấm điểm bằng `/odometry/filtered` (không dùng map TF).

```bash
ros2 run tarkbot_robot eval_odometry --ros-args \
  -p n_trials:=5 \
  -p table_id:=1
```

Mỗi trial ghi thêm quỹ đạo `/odometry/filtered` vào `trajectories/trial_XX.csv` (dùng cho Figure 5.2).

---

## 3. Localization drift (Table 5.3)

So TF `map→base_footprint` với approach trong `floorplan.json` tại Table 1 và dock.

```bash
ros2 run tarkbot_robot eval_localization --ros-args \
  -p n_trials:=5 \
  -p table_id:=1
```

---

## 4. Navigation + docking (Tables 5.4 / 5.5)

Hai batch (mỗi batch N=5). Metrics bàn lấy từ ArUco sau Nav2 (`[Arrival]`) hoặc sau align.

**Có visual align (Table 5.4):**

```bash
ros2 run tarkbot_robot eval_navigation --ros-args \
  -p n_trials:=5 \
  -p table_id:=1 \
  -p enable_visual_align:=true \
  -p return_dock:=true \
  -p standoff_m:=0.8
```

**Không visual align (Table 5.5):**

```bash
ros2 run tarkbot_robot eval_navigation --ros-args \
  -p n_trials:=5 \
  -p table_id:=1 \
  -p enable_visual_align:=false \
  -p return_dock:=true \
  -p standoff_m:=0.8
```

Cùng param cũng dùng được với demo thường:

```bash
ros2 run tarkbot_robot deliver_test --ros-args -p table_id:=1 -p enable_visual_align:=false
```

---

## 5. Gộp bảng luận văn

```bash
ros2 run tarkbot_robot eval_summarize
```

Tạo:

- `evaluate/logs/thesis_tables.md` — markdown sẵn dán
- `evaluate/logs/thesis_tables.csv` — bản CSV

Script lấy **run mới nhất** theo từng loại test.

---

## 6. Vẽ figure luận văn (5.2 / 5.3)

Offline, cần `matplotlib`:

```bash
pip install matplotlib
```

**Figure 5.2** (overlay đường odometry) + **Figure 5.3** (occupancy + dock/Table 1):

```bash
# Cả hai (5.2 lấy run odometry mới nhất có trajectories/)
ros2 run tarkbot_robot eval_plot_figures

# Chỉ 5.2 từ một run cụ thể
ros2 run tarkbot_robot eval_plot_figures -- \
  --only 5.2 \
  --odom-run evaluate/logs/YYYYMMDD_HHMMSS_odometry

# Chỉ 5.3 (không cần chạy robot)
ros2 run tarkbot_robot eval_plot_figures -- --only 5.3
```

Ảnh ra `evaluate/figures/`:

- `figure_5_2_odometry_paths.png`
- `figure_5_3_occupancy_grid.png`

**Figure 5.1** (Gazebo sim) vẫn chụp tay từ simulation — không nằm trong evaluate.

---

## Ánh xạ bảng / hình luận văn

| Mục | Script | Metric / asset |
|------|--------|----------------|
| Table 5.1 | `eval_odometry` | `pos_err_cm`, `abs_yaw_err_deg` |
| Figure 5.2 | `eval_odometry` + `eval_plot_figures` | `trajectories/*.csv` |
| Table 5.2 | `eval_map_summary` | resolution, loop closures geom/ArUco |
| Table 5.3 | `eval_localization` | `|Δx|`, `|Δy|`, `|Δψ|` vs floorplan |
| Figure 5.3 | `eval_plot_figures --only 5.3` | `restaurant.pgm` + `floorplan.json` |
| Tables 5.4 / 5.5 | `eval_navigation` | success %, trip time, lateral / range / yaw |
| Table 5.6 | `eval_summarize` | tổng hợp |

---

## An toàn

- Luôn có người theo robot; giữ tay gần e-stop / Ctrl-C.
- Không chạy N lớn khi pin yếu hoặc sàn trơn.
- Nếu localization lệch: đặt lại robot ở dock, publish lại initial pose (eval gọi `startup_sequence` một lần lúc đầu).
