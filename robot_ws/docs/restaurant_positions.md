# Restaurant World — Vị Trí Robot & ArUco Markers

## Robot Spawn Position

| Trục | Giá trị | Ghi chú |
|------|---------|---------|
| x    | `-1.95` | |
| y    | `-8.0`  | |
| z    | `1.12`  | Trên mặt bàn bếp (kitchen counter) |
| yaw  | `1.5708` (~90°) | Quay về hướng `+Y` (WEST), nhìn vào ArUco marker ID 0 |

**Nguồn:** `turtlebot4_ignition.launch.py` — tham số mặc định `x`, `y`, `z`, `yaw`

---

## ArUco Markers

> Tất cả marker đều gắn ở độ cao `z = 1.25` (tương đương mặt bàn + giá đỡ).  
> Format pose trong SDF: `x y z roll pitch yaw`

| ID | Model SDF | x       | y      | z    | Yaw      | Hướng mặt marker | Vị trí gắn |
|----|-----------|---------|--------|------|----------|-------------------|------------|
| 0  | `q_dock`  | `-1.95` | `-7.01`| `1.25` | `0`    | `+Y` | Kitchen counter — điểm dock |
| 1  | `q1`      | `-3.293`| `-0.89`| `1.25` | `0`    | `+Y` | Bàn 1 (phía nam bàn) |
| 2  | `q2`      | `-2.3`  | `0.89` | `1.25` | `3.14` | `-Y` | Bàn 2 (phía bắc bàn) |
| 3  | `q3`      | `-1.3`  | `-0.89`| `1.25` | `0`    | `+Y` | Bàn 3 (phía nam bàn) |
| 4  | `q4`      | `1.3`   | `-0.89`| `1.25` | `0`    | `+Y` | Bàn 4 (phía nam bàn) |
| 5  | `q5`      | `2.3`   | `0.89` | `1.25` | `3.14` | `-Y` | Bàn 5 (phía bắc bàn) |
| 6  | `q6`      | `3.3`   | `-0.89`| `1.25` | `0`    | `+Y` | Bàn 6 (phía nam bàn) |

---

## Quy ước hướng Yaw

| Yaw (rad) | Hướng mặt marker | Robot tiếp cận từ phía |
|-----------|-------------------|------------------------|
| `0`       | `+Y`              | `y` âm (phía nam bàn)  |
| `1.5708`  | `+X`              | `x` âm (phía tây)      |
| `3.14159` | `-Y`              | `y` dương (phía bắc bàn) |
| `-1.5708` | `-X`              | `x` dương (phía đông)  |

---

## Sơ đồ mặt bằng (Top-view)

```
  Y+
  ^
  |
  |   [q2: ID2]    [q3: ID3]    [q4: ID4]    [q5: ID5]
  |     t2           t3           t4            t5
  |   [q1: ID1]               
  |     t1                       
  |
  +-------------------------------------------------> X+
  |
  |
  |
  |   [q_dock: ID0]   (kitchen, y = -7.01)
  |
  |   [ROBOT SPAWN]   (x=-1.95, y=-8.0, yaw=+Y)
```

> Ghi chú: Sơ đồ mang tính tương đối, không theo tỉ lệ.

---

## Bảng tọa độ đầy đủ các bàn (table center)

| Bàn | Model SDF | x      | y      | Marker gắn kèm |
|-----|-----------|--------|--------|----------------|
| t1  | `t1`      | `-3.3` | `-1.1` | ID 1 (`q1`)    |
| t2  | `t2`      | `-2.3` | `-1.1` | ID 2 (`q2`)    |
| t3  | `t3`      | `-1.3` | `1.1`  | ID 3 (`q3`)    |
| t4  | `t4`      | `1.3`  | `1.1`  | ID 4 (`q4`)    |
| t5  | `t5`      | `2.3`  | `-1.1` | ID 5 (`q5`)    |
| t6  | `t6`      | `3.3`  | `1.1`  | ID 6 (`q6`)    |

---

**Nguồn:** `turtlebot4_ignition_bringup/worlds/restaurant.sdf`
