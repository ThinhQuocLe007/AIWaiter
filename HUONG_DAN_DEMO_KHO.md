# Mock test kịch bản kho — gửi lệnh cho simulation (không cần người nói)

Script `scripts/mock_test_robotlink.py` thay thế người nói: nó bắn từng câu trong kịch bản qua
UDP tới `RobotBridge` trên máy simulation, rồi bạn **nhìn xe chạy thật trên Gazebo**. Mỗi lệnh
được bridge đáp lại (ACK) nên script báo "robot nhận lệnh" hay "KHÔNG phản hồi".

Đường điều khiển (giống hệt demo thật, chỉ khác là lệnh tới từ script thay vì giọng nói):

```
script ──UDP──► RobotBridge (laptop, có Gazebo) ──► run_storage_pick.sh ──► xe chạy
```

## Chuẩn bị

- **Máy simulation (laptop): KHÔNG cần pull repo.** Chỉ cần giữ nguyên những gì đã bật sáng nay:
  Gazebo (`run_demo.sh`) và cầu UDP:
  ```bash
  cd ~/workshop/warehouse_agv_demo && ./run_demo.sh
  # terminal riêng, đã source ROS:
  python3 -m src.robot_link.bridge --demo-dir ~/workshop/warehouse_agv_demo --bind 0.0.0.0:45455
  ```
  Cầu phải in: `Nghe lệnh giọng nói trên udp://0.0.0.0:45455`. Nếu sáng nay tắt rồi thì bật lại
  bằng đúng 2 lệnh đó (đã có sẵn trên laptop, **không đổi code, không pull repo**).
- **Server PC:** pull repo mới nhất (chứa `scripts/mock_test_robotlink.py`), rồi chạy script ở đó.
  Code chỉ sửa trên server.

## Chạy — trên server PC, xe chạy trên máy simulation

Script chạy trên **server PC**, bắn UDP sang bridge trên laptop (cùng ZeroTier nên thông nhau).
Laptop không cần repo, chỉ cần bridge đang chạy.

Cách 1 — set `ROBOT_UDP_HOST` trong `.env` của server PC = IP ZeroTier của laptop:
```ini
# .env (trên server PC)
ROBOT_UDP_HOST=172.25.x.x   # IP ZeroTier của laptop (cùng mạng ZeroTier với PC)
```
rồi chạy (không cần truyền tham số):
```bash
uv run python scripts/mock_test_robotlink.py
```

Cách 2 — truyền thẳng IP, không sửa `.env`:
```bash
uv run python scripts/mock_test_robotlink.py --robot-host <IP_ZeroTier_laptop>
```
(Dùng `127.0.0.1` chỉ khi chạy script ngay trên laptop simulation.)

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
bridge không đáp — kiểm bridge có chạy trên laptop và `ROBOT_UDP_HOST`/`--robot-host` đúng IP.

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

Laptop đã được đưa lên **ZeroTier** (test sáng nay ổn), còn server PC cũng ở ZeroTier → hai máy
thông nhau. Nên script **CHẠY TỪ SERVER PC** bắn thẳng sang bridge trên laptop được. Không cần
chạy script trên laptop, và laptop không cần pull repo — chỉ cần bridge trên laptop đang lắng nghe
(đã bật sáng nay, với `--bind 0.0.0.0:45455` nên nghe cả interface ZeroTier).
