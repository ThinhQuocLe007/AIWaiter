# Mock test kịch bản kho — gửi lệnh cho simulation (không cần người nói)

Script `scripts/mock_test_robotlink.py` thay thế người nói: nó bắn từng câu trong kịch bản qua
UDP tới `RobotBridge` trên máy simulation, rồi bạn **nhìn xe chạy thật trên Gazebo**. Mỗi lệnh
được bridge đáp lại (ACK) nên script báo "robot nhận lệnh" hay "KHÔNG phản hồi".

Đường điều khiển (giống hệt demo thật, chỉ khác là lệnh tới từ script thay vì giọng nói):

```
script ──UDP──► RobotBridge (laptop, có Gazebo) ──► run_storage_pick.sh ──► xe chạy
```

## Chuẩn bị

- **Máy simulation (laptop): một lệnh, không cần bật cầu UDP bằng tay.**
  ```bash
  cd ~/workshop/warehouse_agv_demo && ./run_demo.sh
  ```
  `run_demo.sh` tự bật cầu UDP trên `0.0.0.0:45455` cùng lifecycle với sa bàn. Nhưng **phải pull
  AIWaiter trên laptop**: `run_udp_command_bridge.sh` chỉ dùng bridge AIWaiter khi thấy
  `../AIWaiter/src/robot_link/bridge.py` (đổi chỗ khác thì set `AIWAITER_DIR`), không thấy thì nó
  rơi về bản built-in của sa bàn — bản đó không báo trạng thái xe và script sẽ lùi về đếm giờ.
  Cầu phải in: `Nghe lệnh giọng nói trên udp://0.0.0.0:45455` và `Giữ tốc độ: publisher ... sẵn
  sàng`. Terminal chạy cầu phải có sẵn cả `ros2` lẫn `gz` trong PATH — `pick_box.sh` gọi cả hai.

  **Chạy đúng bridge.** Sa bàn có sẵn một bridge thứ hai (`warehouse_agv_demo/scripts/
  udp_command_bridge.py`) nói cùng giao thức nhưng KHÔNG báo trạng thái xe, nên script sẽ không
  bao giờ thấy `moving` và lùi về đếm giờ như cũ. Nhìn dòng khởi động để biết đang chạy cái nào:
  `Nghe lệnh giọng nói trên udp://...` là bridge AIWaiter (đúng), `UDP bridge listening on
  udp://...` là bản built-in. Hai bridge cùng bind được cổng 45455 mà không báo lỗi — cái bind
  sau nhận hết — nên chỉ bật MỘT.
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

Script bám theo robot thật chứ không đếm giờ đoán mò: bridge trả trạng thái AGV (đọc `/odom`)
trong mỗi ack, nên script đứng chờ tới khi **bánh thật sự quay** rồi mới sang bước sau — Nav2/AMCL
trên xe này mất 6–8s mới ra path.

```
>>> gửi: 'đi tới khu A'   (đi tới khu A)
    [OK] robot nhận lệnh
    [MOVING] sau 7.4s
    ... xem xe chạy 4.0s rồi sang bước sau
>>> gửi: 'dừng lại'       (dừng lại giữa đường)
    [OK] robot nhận lệnh
    [STOPPED] sau 0.5s
>>> gửi: 'qua khu B lấy hàng rồi mang về trạm đóng gói'
    [OK] robot nhận lệnh
    [MOVING] sau 6.9s
    ... chờ xe làm xong nhiệm vụ (gắp hàng + mang về trạm đóng gói)
    [XONG] nhiệm vụ kết thúc sau 96s, xe đã về trạm
```

Đọc dòng hỏng: `[NO ACK]` = lệnh không tới được bridge (kiểm bridge có chạy và
`ROBOT_UDP_HOST`/`--robot-host` đúng IP). `[TIMEOUT]` = bridge nhận rồi nhưng xe không vào trạng
thái đó — xem log terminal bridge và output `pick_box.sh` trên máy sim.

## Kịch bản

| # | Câu (script gửi) | Bridge sẽ làm | Script chờ tới khi |
|---|---|---|---|
| 1 | đi tới khu A | `pick_box.sh --storage A --route-only` (chạy tới, không gắp) | xe lăn bánh (`moving`), rồi xem chạy 4s |
| 2 | dừng lại | giữ `/cmd_vel`, xe đứng giữa đường | xe đứng hẳn (`stopped`) |
| 3 | qua khu B lấy hàng rồi mang về | `pick_box.sh --storage B --deliver` | xe lăn bánh, rồi tới khi xong cả chuyến (`idle`) |

Bước 3 đã bao gồm "lấy xong đi về": `--deliver` là gắp rồi mang về trạm đóng gói. Không cần thêm
lệnh "về trạm sạc" — sa bàn neo trạm sạc chung với trạm đóng gói (xem `make caps`).

Muốn sửa kịch bản: sửa `SCENARIOS` ở đầu script. Mỗi dòng là
`(nhãn, loại, action, câu nói, giây xem xe chạy | None, trạng thái phải đạt)`; `None` nghĩa là chờ
tới khi nhiệm vụ chạy xong thay vì đếm giây. Máy sim chậm thì `--wait-scale 1.5`.

## Chạy tay từng lệnh (không dùng script kịch bản)

Ba lệnh, chạy trên server PC, gõ tới đâu xem xe tới đó. IP lấy từ `.env`, khỏi truyền tham số.

```bash
make say TEXT="đi tới khu A" TASK=goto        # 1. chạy tới khu A, không gắp
make say TEXT="dừng lại"                      # 2. dừng giữa đường (giữ nguyên đích cũ)
make say TEXT="qua khu B lấy hàng" TASK=fetch # 3. sang khu B gắp hàng rồi mang về trạm đóng gói
```

`TASK` ép việc ở đích, vì bộ đọc câu luôn đoán `fetch` cho mọi câu có tên khu — không có cách nói
tiếng Việt nào ra được "chạy tới thôi, đừng gắp". Các giá trị: `goto` (chỉ chạy tới), `fetch`
(gắp + mang về), `fetch_hold` (gắp, giữ trên khay), `deliver` (hàng đã trên khay, mang về nốt).
Thêm `DRY=1` để xem lệnh Gazebo sẽ chạy mà không gửi đi đâu.

Khác biệt với script kịch bản: `make say` bắn xong là xong, không chờ xác nhận xe đã lăn bánh —
nên sau lệnh 1 phải tự nhìn Gazebo, thấy xe chạy rồi mới gõ lệnh 2 (Nav2/AMCL mất 6–8s tìm đường).

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
