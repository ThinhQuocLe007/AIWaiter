# Mock test kịch bản kho — gửi lệnh cho simulation (không cần người nói)

Script `scripts/mock_test_robotlink.py` thay thế người nói: nó bắn từng câu trong kịch bản qua
UDP tới `RobotBridge` trên máy simulation, rồi bạn **nhìn xe chạy thật trên Gazebo**. Mỗi lệnh
được bridge đáp lại (ACK) nên script báo "robot nhận lệnh" hay "KHÔNG phản hồi".

Đường điều khiển (giống hệt demo thật, chỉ khác là lệnh tới từ script thay vì giọng nói):

```
script ──UDP──► RobotBridge (laptop, có Gazebo) ──► run_storage_pick.sh ──► xe chạy
```

## Chuẩn bị

- Máy simulation đã bật Gazebo + cầu UDP (theo mục C guide):
  ```bash
  cd ~/workshop/warehouse_agv_demo && ./run_demo.sh
  # terminal riêng, đã source ROS:
  python3 -m src.robot_link.bridge --demo-dir ~/workshop/warehouse_agv_demo --bind 0.0.0.0:45455
  ```
  Cầu phải in: `Nghe lệnh giọng nói trên udp://0.0.0.0:45455`
- Script nằm ở `scripts/mock_test_robotlink.py` (đã commit/push lên repo).

## Chạy — xe thật chạy trên simulation

Script phải chạy ở máy **có thể tới được cổng UDP 45455 của bridge** (laptop simulation, hoặc
Jetson — hai máy này có mặt trên Netbird/ZeroTier tới được laptop).

**Cách 1 — chạy luôn trên laptop simulation (đơn giản nhất):**
```bash
uv run python scripts/mock_test_robotlink.py --robot-host 127.0.0.1
```

**Cách 2 — chạy trên Jetson (bắn sang laptop qua Netbird):**
```bash
uv run python scripts/mock_test_robotlink.py --robot-host 100.66.149.248
```

Script sẽ lần lượt bắn kịch bản, mỗi lệnh chờ vài giây để bạn xem xe di chuyển:

```
>>> gửi: 'đi tới khu A'   (đi tới khu A)
    [OK] robot nhận lệnh
    ... chờ 3.0s để xem xe chạy trên simulation
>>> gửi: 'dừng lại'       (dừng lại giữa đường)
    [OK] robot nhận lệnh
    ... chờ 2.0s ...
>>> gửi: 'đổi sang khu B'  (đổi sang khu B)
...
```

Xe có chạy thật trên Gazebo hay không là do bạn nhìn máy simulation. Dòng `[NO ACK]` nghĩa là
bridge không đáp — kiểm bridge có chạy và `--robot-host` đúng IP.

## Các kịch bản có sẵn

Mỗi bước có khoảng chờ riêng (xem `SCENARIOS` trong script), quan trọng là "đi khu A" chỉ chờ
3s rồi mới "dừng lại" — để lệnh dừng/đổi ý xảy ra ĐÚNG LÚC xe đang chạy giữa đường:

| # | Câu (script gửi) | Bridge sẽ làm |
|---|---|---|
| 1 | đi tới khu A | chạy tới Khu A (`--route-only`, không gắp) |
| 2 | dừng lại | giữ /cmd_vel, xe đứng giữa đường |
| 3 | đổi sang khu B | hủy chuyến cũ, chạy tới Khu B |
| 4 | đi tiếp | bỏ giữ, chạy tiếp đích cũ |
| 5 | đổi sang khu C lấy hộp xanh | chạy tới Khu C, gắp hộp xanh (`--deliver`) |

Muốn sửa kịch bản: sửa danh sách `SCENARIOS` ở đầu script (thêm/bớt câu, đổi `wait` mỗi bước).

## Chạy headless — không cần Gazebo (`--local`)

Dùng trên server không có sim để check logic: script tự bật một `RobotBridge` giả lập
(`--no-ros --dry-run`) trên localhost, gửi kịch bản, và kiểm bridge dịch ra đúng lệnh Gazebo
(`pick_box.sh --storage B --route-only` …). Không điều khiển xe thật.

```bash
uv run python scripts/mock_test_robotlink.py --local
#  5/5 kịch bản PASS (bridge dịch đúng lệnh Gazebo)
```

## Lưu ý mạng

Theo setup demo: PC server chỉ ở ZeroTier, laptop sim ở Netbird, hai mạng không thông nhau. Nên
script **không chạy được từ PC server bắn thẳng sang laptop**. Chạy script trên laptop simulation
(`--robot-host 127.0.0.1`) hoặc trên Jetson. (Nếu laptop đã được đưa lên ZeroTier như bạn test
sáng nay, thì có thể chạy từ bất kỳ máy cùng ZeroTier tới được IP laptop.)
