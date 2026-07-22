# Runbook — demo robot THẬT end-to-end (web + nav + voice)

> Bật cả hệ thống, đặt robot ở dock, seat một bàn trên web, robot tự chạy tới bàn — rồi về dock.
> Bản **thao tác**, có chỗ dừng kiểm tra sau mỗi tầng để bắt lỗi đúng chỗ.
>
> Giải thích tại sao nav lại thiết kế như vậy: [jetson-nav-merge-vi.md](jetson-nav-merge-vi.md).
> Chỉ test voice/web không cần nav: [e2e-voice-web-runbook-vi.md](e2e-voice-web-runbook-vi.md).
> Vận hành voice hằng ngày: [jetson-boot-runbook-vi.md](jetson-boot-runbook-vi.md).

## 0. Ba máy chạy gì

| Máy | Netbird IP | Chạy | Mở trình duyệt |
|---|---|---|---|
| **Server** (ducduy-pc) | `100.66.165.221` | `ollama serve` · `make backend` · `make agent` · web (xem ①) | — |
| **Jetson** (robot) | `100.66.177.150` | `make hwstack` · `make voice` · **Firefox** kiosk | customer_ui |
| **Laptop** | `100.66.242.168` | *(chỉ trình duyệt)* | panel · kiosk |

URL cụ thể tuỳ server đang serve web kiểu nào — bảng ở bước ①.

```
                    ┌── ollama :11434 ──┐
SERVER   backend :8000 (REST + WS hub + serve cả 3 web)   agent :8100
             ▲                    │                          ▲
    WS role=robot          task.assign / release       HTTP /chat
             │                    ▼                          │
JETSON   make hwstack ── RTAB-Map + Nav2 + ArUco ── bánh xe chạy
         make voice ──── mic → STT ─────────────────────────┘ → TTS + customer_ui
```

**Điểm khác bản cũ:** `make hwstack` bật LUÔN base driver (`robot_node`), lidar, camera, EKF.
**Đừng chạy `ros2 run tarkbot_robot robot_node` ở terminal riêng nữa** — hai instance sẽ tranh
cổng serial của STM32 và cả hai cùng hỏng.

---

## ① SERVER — bật trước

```bash
cd ~/AIWaiter
ollama serve      # T0
make backend      # T1 — :8000 — REST + WS hub
make agent        # T2 — :8100, chờ in "Agent ready." (lần đầu build embeddings, lâu)
```

Rồi **chọn một trong hai cách phục vụ web** — đây là chỗ hay lẫn:

### Cách A — bản build tĩnh (khuyên dùng khi demo)

```bash
make build        # rồi RESTART make backend (nó mount dist/ lúc khởi động)
```

Backend tự serve cả 3 app **cùng một origin `:8000`**, không cần `make frontend`, không cần Node
trên Jetson/laptop, không dính CORS:

| App | URL |
|---|---|
| customer_ui (màn robot) | `http://100.66.165.221:8000/` |
| kiosk | `http://100.66.165.221:8000/kiosk` |
| panel | `http://100.66.165.221:8000/panel` |

### Cách B — dev server (khi đang sửa giao diện, cần hot-reload)

```bash
make frontend     # 3 vite dev server: 5173 / 5174 / 5175, tự proxy /api + /ws về :8000
```

URL **khác hẳn**, và kiosk/panel **phải có phần đuôi** (vite config đặt `base: '/kiosk/'`,
`'/panel/'`) — thiếu là trang trắng:

| App | URL |
|---|---|
| customer_ui | `http://100.66.165.221:5173/` |
| kiosk | `http://100.66.165.221:5174/kiosk/` |
| panel | `http://100.66.165.221:5175/panel/` |

Cả 3 đều bind `0.0.0.0` nên máy khác trong Netbird vào được. `make backend` vẫn **bắt buộc** —
dev server chỉ proxy chứ không có API.

### Dừng kiểm tra — cả 4 dòng phải đúng trước khi đụng tới robot

```bash
curl -s  http://127.0.0.1:8000/health          # {"status":"ok"}
curl -s  http://127.0.0.1:8100/health          # agent sống
curl -sI http://127.0.0.1:8000/ | head -1      # 200 = đang ở cách A · 404 = phải dùng cách B
curl -s  http://127.0.0.1:8000/layout | head -c 200
```

Dòng thứ 3 chính là **cách biết server đang ở chế độ nào** — khỏi phải nhớ.

Dòng cuối là thứ **mới** phải để ý: nó trả về map + bàn của minimap. Trong log khởi động của
`make backend` phải thấy

```
floorplan: .../tarkbot_robot/config/floorplan.json (map: .../tarkbot_robot/maps)
```

Nếu `map:` trỏ vào `turtlebot4_navigation/maps` thì backend đang rơi về **map sim** — minimap sẽ vẽ
sàn Gazebo trong khi robot gửi toạ độ sàn thật. Sửa: chạy `make map` trên Jetson rồi copy
`restaurant.pgm` + `restaurant.yaml` sang server, restart backend.

---

## ② ĐẶT ROBOT Ở DOCK — làm bằng tay, trước khi bật hwstack

Quy ước demo: **lúc khởi động robot LUÔN đứng ở dock (ArUco 6)**. Bridge tự bơm pose đó vào
`/initialpose`, nên không phải bấm "2D Pose Estimate" trong RViz nữa.

Đặt sao cho đúng:

1. Robot đứng ở **đúng chỗ đã khảo sát**: `x = -2.417, y = -2.069, yaw = -65.2°`
   (tức là cách mã ArUco 6 khoảng **0.8 m**, **mũi xe quay thẳng vào mã**).
2. Camera **nhìn thấy rõ mã ArUco 6** — không bị che, không quá xéo.
3. Mã dán chắc, cạnh **đúng 0.15 m**, đúng bộ **DICT_4X4_50**. Mã in sai cỡ = PnP ra khoảng cách
   sai theo tỉ lệ.

Đứng lệch vài cm thì không sao (RTAB-Map kéo lại được bằng landmark + lidar); đứng **sai hẳn chỗ**
hoặc quay lưng vào mã thì localization xuất phát sai và mọi thứ sau đó lệch theo.

---

## ③ JETSON — 2 terminal

```bash
# ── T1: cả stack robot (base driver + lidar + camera + EKF + RTAB-Map + Nav2 + RViz + bridge)
cd ~/ptd_workspace/AIWaiter
make hwstack SERVER_HOST=100.66.165.221:8000 ID=robo-1
```

Thứ tự log phải thấy, **theo đúng trình tự này**:

| Chờ thấy | Nghĩa là |
|---|---|
| `[ArUco] tracker up` | camera + TF sống |
| `[STARTUP] /initialpose = dock (ArUco 6) x=-2.417 …` | đã bơm pose dock |
| *(hết dòng `waiting for map->base_footprint`)* | RTAB-Map relocalize xong |
| `[STARTUP] Nav2 ACTIVE — ready for tasks.` | Nav2 sẵn sàng |
| `WS connected → ws://100.66.165.221:8000/…` | nối được backend |
| `task_bridge ready — waiting for dispatcher tasks` | **xong, chờ việc** |

Trong RViz: chấm robot phải nằm **đúng góc dock trên map**, không trôi. Nếu nó nhảy lung tung hoặc
nằm giữa tường → localization sai, tắt đi đặt lại robot (bước ②) rồi bật lại.

```bash
# ── T2: voice (chỉ cần nếu muốn test nói chuyện; robot vẫn chạy tới bàn khi không có nó)
cd ~/ptd_workspace/AIWaiter
make voice        # chờ "[READY] đã kết nối backend (robo-1)"
```

Trình duyệt trên màn robot — **dùng Firefox (bản deb)**. `chromium-browser` trên rig này là bản
snap mà snapd đã chết (`/run/snapd.socket` không có), mở là treo. Gõ qua SSH thì cần 2 dòng
`export`; gõ thẳng trên desktop robot thì bỏ:

```bash
export DISPLAY=:0
export XAUTHORITY=/run/user/1000/gdm/Xauthority
firefox --kiosk http://100.66.165.221:8000/     # cách A
# cách B (dev server):  firefox --kiosk http://100.66.165.221:5173/
```

Thoát kiosk: `Ctrl+W` hoặc `Alt+F4`.

---

## ④ Chạy thử — bốn bước, mỗi bước một thứ để nhìn

Mở `http://100.66.165.221:8000/panel` trên laptop và để đó suốt.

**1 — Robot lên panel.** Ngay khi T1 báo `WS connected`:
- Robot board: `robo-1` · **Đang ở dock** · **pin thật** (số %, không phải `—`).
- Minimap: **chấm robot nằm ở dock**, trên nền **sàn thật** của nhà hàng.

Pin có mà chấm chưa có = localization chưa xong, chờ thêm (bridge cố ý gửi pin trước, pose sau).

**2 — Gọi robot ra bàn.** Mở `:8000/kiosk` → **seat một bàn bất kỳ** (bàn 3 cũng được).
- Panel: task mới, robot chuyển **Đang tới bàn 3**.
- T1: `task.assign #N go_to_table → bàn 3` rồi
  `task 42: bàn 3 chưa khảo sát → chạy tới Table 1 (demo một bàn)`.
- **Robot chạy thật**: Nav2 tới waypoint bàn 1 → `[Arrival] err_x=…` → `[Align] locked` → dừng,
  mũi xe quay vào mã.
- Panel: **Đang phục vụ · Bàn 3**; backend log `voice bound to robo-1`.

> Sàn demo mới khảo sát một bàn nên **mọi bàn trên web đều dẫn tới ArUco 1**. Id bàn thật vẫn giữ
> nguyên ở server — đó là thứ bind tablet + mic, nên khách bàn 3 vẫn nói chuyện với bàn 3 của họ.
> Khảo sát thêm bàn (`ros2 launch tarkbot_robot pose_survey.launch.py`) rồi thêm vào
> `floorplan.json` là bàn đó có đích riêng, không phải sửa code.

**3 — Nói chuyện.** Trên màn robot bấm **"Nói chuyện với AI"** → T2 in `[LISTENING]` → nói tiếng
Việt → `[HEARD @ … | bàn 3]` → `[WAITER]: …` + loa đọc + customer_ui hiện hội thoại.

**4 — Đặt món rồi robot tự về.** Đặt món trên customer_ui (hoặc thanh toán).
- Backend: `released robot robo-1 from table 3 — heading home`.
- T1: `task.release` → Nav2 chạy về dock → `[Align] locked` trên ArUco 6 → `at_dock`.
- Panel: **Đang về dock** → **Đang ở dock**. Chấm minimap về đúng góc dock.

Chạy hết 4 bước là **end-to-end đã thông**.

---

## ⑤ Bảng chờ (dán lên tường)

| # | Máy | Lệnh | Chờ tới khi |
|---|---|---|---|
| 1 | server | `ollama serve` | `ollama list` ra model |
| 2 | server | `make backend` | `/health` OK · log `map:` trỏ `tarkbot_robot/maps` |
| 3 | server | `make agent` | `Agent ready.` |
| 4 | server | `make build` + restart backend **hoặc** `make frontend` | `curl -sI :8000/` ra 200 (cách A) |
| 5 | — | **đặt robot ở dock, camera thấy ArUco 6** | mắt thường |
| 6 | jetson | `make hwstack SERVER_HOST=… ID=robo-1` | `task_bridge ready` + chấm dock trên panel |
| 7 | jetson | `make voice` | `[READY]` |
| 8 | jetson | `firefox --kiosk :8000/` | web hiện trên màn robot |
| 9 | web | kiosk seat một bàn | robot chạy · panel `Đang phục vụ` |
| 10 | web | bấm "nói chuyện" | jetson `[LISTENING]` |
| 11 | web | đặt món | robot về dock · panel `Đang ở dock` |

Tắt: server `make kill` · Jetson `Ctrl-C` ở T1 (tắt cả stack) rồi T2.

---

## ⑥ Gỡ rối theo triệu chứng

Chỉ liệt kê thứ **mới có từ khi ghép nav**; lỗi voice/web thuần xem
[e2e-voice-web-runbook-vi.md §6](e2e-voice-web-runbook-vi.md).

| Triệu chứng | Nguyên nhân thường gặp |
|---|---|
| Panel có pin nhưng **không có chấm minimap** | Chưa có TF `map→base_footprint`. T1 đang in `waiting for map->base_footprint` → RTAB-Map chưa relocalize: robot đứng sai chỗ (bước ②), hoặc `~/.ros/rtabmap.db` không phải map của phòng này |
| Chấm minimap chạy nhưng **nền là sàn khác** | Backend rơi về map sim — xem lại dòng `map:` ở bước ① |
| `[STARTUP] no map->base_footprint after 120s` | Như trên; bridge vẫn chạy tiếp nhưng **mọi task sẽ fail**. Tắt, đặt lại robot ở dock, bật lại |
| Robot **không nhúc nhích** khi seat bàn | Xem T1: có `task.assign` không? Không có = backend chưa gán (robot offline / pin < 20% / `robot_id` ≠ `robo-1`). Có mà không chạy = Nav2 chưa ACTIVE |
| `Nav2 goal did not succeed` rồi robot về dock | Đường bị chặn hoặc goal nằm trong costmap. Bridge cố ý **không** báo `arrived` (báo = bind mic vào ghế trống), nó đóng task và về dock |
| Robot tới nơi nhưng **đứng xéo** | `[Arrival] marker … NOT visible` hoặc `[Align] marker lost`. Mã bị che/quá xéo. `visual_align` chỉ XOAY — độ vuông góc phải nằm sẵn trong waypoint, đo lại bằng `pose_survey` |
| Robot đi được nhưng **không bao giờ lùi** | ĐÚNG thiết kế — Nav2 để `min_vel_x=0` (forward-only) |
| Task treo `Đang tới bàn N` mãi trên panel | Robot rớt giữa chừng. Watchdog 30 s sẽ requeue; xem T1 có `WS closed` không |
| `ModuleNotFoundError: websocket` | `sudo apt install python3-websocket` (system python3, vì `ros2 run` dùng nó) |
| Pin hiện sai % | Pack không phải 3S. Đo `ros2 topic echo /bat_vol` lúc đầy và lúc gần cạn, rồi `make hwbridge` thêm `-p battery_full_v:=… -p battery_empty_v:=…` |
| Hai `robot_node` tranh cổng serial | Đang chạy `robot_node` riêng — bỏ đi, `make hwstack` đã bật sẵn |
| `chromium-browser` mở là treo / `snapd.socket` không có | Chromium trên rig này là bản snap mà snapd đã chết. Dùng **`firefox --kiosk`** (bản deb, đã cài sẵn) |
| Mở `:8000/` ra **404** | Server đang ở **cách B** (chưa `make build`) → dùng URL dev `:5173` / `:5174/kiosk/` / `:5175/panel/`. Hoặc `make build` rồi **restart backend** |
| Dev server mở ra **trang trắng** ở `:5174` hay `:5175` | Thiếu đuôi `base`: phải là `:5174/kiosk/` và `:5175/panel/` |
