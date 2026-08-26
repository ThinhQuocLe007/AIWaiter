# Demo kho AGV bằng giọng nói — hướng dẫn từ máy trắng

Ba máy, mỗi máy một việc. Đọc đúng mục của máy đang ngồi, làm từ trên xuống.

```
JETSON (Ubuntu 22)                PC SERVER (ở nhà, VPN)          LAPTOP (Ubuntu 24)
mic → VAD → Whisper → TTS  ──VPN──►  agent LLM :8100              Gazebo + Nav2 + V-JEPA
       │                             backend web :8000            cầu UDP nghe :45455
       │                                    └──► màn hình monitor
       └────── UDP, LAN tại chỗ demo ──────────────────────────►  AGV chạy
```

Vì sao chia vậy: Jetson chạy ROS 2 Humble, laptop chạy Jazzy — DDS hai bản không nói chuyện được
nên chặng robot đi UDP thuần. Chặng LLM đi HTTP vì mất một lượt hội thoại là mất câu trả lời, còn
lệnh dừng thì không được phép nằm chờ TCP gửi lại.

## IP cố định của buổi demo

| Máy | IP | Mạng overlay |
|---|---|---|
| PC server (agent + web) | `172.25.223.218` | ZeroTier |
| Jetson (giọng nói) | `172.25.171.115` | ZeroTier |
| Jetson — cùng máy đó | `100.66.136.17` | Netbird |
| Laptop (Gazebo) | `100.66.149.248` | Netbird |

**Jetson nằm trên cả hai mạng, mỗi chặng đi một mạng khác nhau:**

```
Jetson ──ZeroTier── PC server 172.25.223.218      LLM + web
Jetson ──Netbird─── laptop    100.66.149.248      lệnh robot
```

PC chỉ có mặt trên ZeroTier, laptop chỉ có mặt trên Netbird, và Netbird **không** định tuyến sang
ZeroTier (`netbird status` báo `Networks: -`). Jetson bắc được cả hai nên chuỗi chạy thông.

Không phải khai IP của chính Jetson ở đâu cả — kernel tự chọn đường theo IP đích. Chỉ cần đặt
đúng **IP đích** trong `.env`.

> Kiểm 5 giây, chạy trên máy nào cũng được:
>
> ```bash
> make netcheck
> ```
>
> Nó in luôn interface mà kernel chọn để đi (`qua zt… (ZeroTier)` / `qua wt0 (Netbird)`), nên gõ
> nhầm IP của mạng kia là thấy ngay. Và nó phân biệt "không tới được máy đó" (lỗi mạng) với "tới
> được nhưng dịch vụ chưa bật" (chỉ cần `make backend`). Chạy nó **trước** khi nghi ngờ mic, LLM
> hay robot.

| | Cần cài | Không cần |
|---|---|---|
| PC server | uv, Node 22, Ollama, model 14b | ROS, Gazebo |
| Jetson | uv, mic/loa, Whisper+Piper | Node, Ollama, ROS |
| Laptop | Docker + Gazebo + ROS Jazzy | uv, venv, Node, Ollama |

Laptop **không cần venv**: cầu UDP chỉ dùng thư viện chuẩn của Python cộng `rclpy` có sẵn của ROS.

---

# A. PC SERVER — agent + web

## A1. Cài từ máy trắng

```bash
git clone https://github.com/ThinhQuocLe007/AIWaiter.git
cd AIWaiter
git checkout ai_warehouse

make setup      # nvm + Node 22 + uv + npm deps  (chỉ chạy lần đầu)
```

Python cho vai trò server. **Chọn đúng một extra CUDA**, không được cả hai:

```bash
make install UV_EXTRAS="--extra server --extra cu12"    # GPU đời cũ, driver CUDA 12
# hoặc
make install UV_EXTRAS="--extra server --extra cu13"    # GPU đời mới, driver CUDA 13
```

Không chắc dùng cái nào thì xem `nvidia-smi` góc trên bên phải: `CUDA Version: 12.x` → cu12,
`13.x` → cu13.

## A2. Ollama

```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama pull qwen2.5:14b-instruct-q6_K
```

Tên model phải **khớp đúng** `LLM_MODEL` trong `.env`, sai một chữ là agent nhận 404 từ Ollama.

## A3. File .env

```bash
cp .env.template .env
```

Trên PC **không cần sửa gì thêm** — template đã đặt sẵn 14b, embedding CPU, và trỏ về
`127.0.0.1`. Mở ra xem cho biết ba nhóm biến:

```ini
LLM_MODEL=qwen2.5:14b-instruct-q6_K      # brain kho gọi con này
EMBED_MODEL=dangvantuan/vietnamese-embedding
EMBED_DEVICE=cpu                          # để dành VRAM cho con 14b
ORCHESTRATOR_URL=http://127.0.0.1:8000
AGENT_URL=http://127.0.0.1:8100
```

> **Đừng đặt `ROUTER_MODEL` / `WORKER_MODEL` / `RESPONSE_MODEL` / `EMBEDDING_MODEL`.** Đó là biến
> của bản nhà hàng cũ, **không dòng nào của brain kho đọc tới**. Đặt vào đó không có tác dụng gì.
> Biến sống là `LLM_MODEL`.

## A4. Train bộ phân loại ý định

```bash
make train-router
```

Nó nhúng 212 câu mẫu trong `src/agent_brain/warehouse/router/intents.json`, fit một MLP nhỏ, lưu
ra `storage/router/mlp_router.joblib`. Chạy chừng 1–2 phút (lần đầu phải tải model embedding).

Cuối sẽ in bảng đánh giá, đại khái:

```
=== Router training evaluation ===
              precision    recall  f1-score   support
      answer       0.93      1.00      0.96        15
        chat       1.00      0.75      0.86         4
     control       1.00      1.00      1.00         5
    navigate       1.00      0.88      0.93         8
Saved router -> .../storage/router/mlp_router.joblib
```

**Bắt buộc, và phải chạy trên chính PC này**, vì `make agent` nạp file đó lúc khởi động. File
không nằm trong git (là kết quả train, không phải mã nguồn). Quên chạy thì `make agent` sẽ **từ
chối khởi động** và in ra đúng lệnh cần chạy — không để bạn phát hiện giữa buổi demo.

Sửa `intents.json` lúc nào thì train lại lúc đó. Và `EMBED_MODEL` lúc train phải giống lúc chạy:
trọng số là một MLP trên không gian vector của đúng model đó, đổi model sau khi train thì router
vẫn chạy nhưng đoán bậy và **không báo lỗi gì cả**.

## A5. Build web

```bash
make build
```

Build cả 4 trang (customer_ui, kiosk, panel, **monitor**) ra `dist/`. Sau đó `make backend` tự
phục vụ luôn, **không cần chạy npm lúc demo**:

```
http://172.25.223.218:8000/monitor     ← màn hình demo
http://172.25.223.218:8000/panel
http://172.25.223.218:8000/kiosk
http://172.25.223.218:8000/
```

Chạy lại `make build` sau mỗi lần `git pull` có đụng `src/frontends/`.

## A6. Chạy — 2 cửa sổ

```bash
make backend     # cửa sổ 1 — :8000, web + hub WebSocket
make agent       # cửa sổ 2 — :8100, brain LLM
```

## A7. Kiểm tra ngay trên PC (chưa cần máy khác)

```bash
make checkmap                                    # data kho có khớp sa bàn Gazebo không
make caps                                        # in bảng: câu nói nào ra lệnh gì
make say TEXT="dẫn tôi đi lấy thùng bia" DRY=1   # câu này sẽ thành lệnh robot nào
```

`checkmap` so từng ô A01–C03 giữa `data/inventory.csv` và `semantic_tasks.yaml` của sa bàn, **kể
cả màu hộp**. Sai một ô là robot tới đúng kệ mà gắp sai hộp trước mặt khách.

---

# B. JETSON — giọng nói

## B1. Cài

```bash
git clone https://github.com/ThinhQuocLe007/AIWaiter.git
cd AIWaiter && git checkout ai_warehouse

make setup
make install UV_EXTRAS="--extra voice"
```

Jetson **không cần** `--extra server`, không cần Node, không cần Ollama. Nó chỉ nghe, nhận dạng,
đọc thành tiếng, và bắn lệnh đi.

> Nếu Jetson đã có `ctranslate2`/`faster-whisper` build tay thì **đừng chạy `uv sync` trơn** —
> nó sẽ gỡ mất bản build tay đó. `make install UV_EXTRAS="--extra voice"` dùng `--inexact` nên an
> toàn. Target `make voice` cũng gọi thẳng `.venv/bin/python`, không qua `uv run`, vì lý do này.

## B2. File .env

```bash
cp .env.template .env
```

Trên Jetson **phải sửa 3 dòng** — chú ý đây là **hai địa chỉ khác nhau**, đừng lẫn:

```ini
# LLM + web: qua VPN, tới PC ở nhà
ORCHESTRATOR_URL=http://172.25.223.218:8000
AGENT_URL=http://172.25.223.218:8100

# Robot: qua LAN tại chỗ demo, tới LAPTOP chạy Gazebo
ROBOT_UDP_HOST=100.66.149.248      # laptop Gazebo, qua Netbird
```

Để trống `ROBOT_UDP_HOST` thì Jetson chỉ nghe và trả lời, không điều khiển robot — đúng cho lúc
test mic hoặc demo web mà chưa mở sa bàn.

## B3. Thử micro trước (không cần server)

```bash
make probe        # nói vào mic, in ra text
```

Chạy cái này sau mỗi lần reboot hoặc đổi cổng USB. Nó tách bạch lỗi âm thanh khỏi lỗi mạng —
đừng đi tiếp khi nó chưa in ra đúng câu bạn nói.

## B4. Chạy

```bash
make jetson SERVER_HOST=172.25.223.218:8000 ID=robo-1 VOICE=1 WEB=1 STACK=0
```

Một lệnh cho cả buổi: bật voice + mở trình duyệt kiosk vào `/monitor` trên PC.
`STACK=0` vì robot thật đứng yên — xe chạy là xe trong Gazebo.

> **Dùng dạng đầy đủ này, đừng gõ `make jetson` trơn.** Nếu Makefile trên Jetson là bản cũ thiếu
> hai dòng target-specific thì make sẽ lấy mặc định toàn cục `SERVER_HOST=127.0.0.1:8000` — trên
> Jetson `127.0.0.1` là **chính nó**, không phải PC. Kiểm nhanh: `make -n jetson | head -1`.

Chỉ muốn voice, không mở trình duyệt: `make voice`.

---

# C. LAPTOP — Gazebo + V-JEPA

Sa bàn và V-JEPA cài như cũ, **không đổi gì**. Phần thêm vào là cầu UDP.

## C1. Chạy sa bàn (đúng lệnh Anh Khôi đưa)

```bash
cd ~/workshop/warehouse_agv_demo
./run_demo.sh
```

Khởi động Gazebo + Nav2 + V-JEPA + 5 công nhân đi lại. **Chạy cái này trước tiên**, đợi Gazebo và
RViz hiện đủ rồi mới làm bước sau.

Lệnh lấy hàng thủ công, để đối chiếu khi cầu UDP có vấn đề:

```bash
./pick_box.sh --storage A --color blue --deliver
```

## C2. Chạy cầu UDP

Cầu phải chạy **cùng chỗ với ROS**. Chạy Gazebo trong Docker thì cầu cũng phải ở **trong
container** — nó cần `rclpy` để giữ bánh xe, và cần gọi được `pick_box.sh`.

Nó không cần cài gì thêm: chỉ dùng thư viện chuẩn của Python.

**Nếu Gazebo chạy thẳng trên máy:**

```bash
git clone https://github.com/ThinhQuocLe007/AIWaiter.git ~/AIWaiter
cd ~/AIWaiter && git checkout ai_warehouse
source /opt/ros/jazzy/setup.bash
python3 -m src.robot_link.bridge --demo-dir ~/workshop/warehouse_agv_demo --bind 0.0.0.0:45455
```

**Nếu Gazebo chạy trong Docker** — mount thêm AIWaiter, và dùng `--network host` (ROS/Gazebo vốn
đã cần, kèm theo cổng UDP mở thẳng trên IP LAN của laptop):

```bash
docker run -it --rm --network host \
  -v ~/workshop/warehouse_agv_demo:/warehouse_agv_demo \
  -v ~/workshop/vjepa_visual_localization:/vjepa_visual_localization \
  -v ~/AIWaiter:/AIWaiter \
  <image-gazebo-của-bạn>
```

Trong container:

```bash
source /opt/ros/jazzy/setup.bash && cd /AIWaiter
python3 -m src.robot_link.bridge --demo-dir /warehouse_agv_demo --bind 0.0.0.0:45455
```

Ảnh ROS gọn thường không cài `make` — nên gọi thẳng module như trên, đừng `make robotlink`.

Không dùng được `--network host` thì thêm `-p 45455:45455/udp`, và `ROBOT_UDP_HOST` trên Jetson
phải là IP của **host laptop**, không phải IP trong container.

## C3. Mở cổng

```bash
sudo ufw allow 45455/udp        # chỉ khi có bật tường lửa
```

Lúc khởi động, cầu phải in ra dòng này — không thấy là lệnh dừng sẽ **không hoạt động**:

```
Giữ tốc độ: publisher /cmd_vel_keyboard + /cmd_vel sẵn sàng
Nghe lệnh giọng nói trên udp://0.0.0.0:45455
```

---

# D. Kiểm tra tăng dần

Mỗi bậc kiểm **một** chặng. Bậc nào hỏng thì sửa xong mới đi tiếp — bật hết rồi đoán là cách tốn
thời gian nhất.

| Bậc | Ở đâu | Làm gì | Đúng thì thấy |
|---|---|---|---|
| 1 | PC | `make checkmap` | `KẾT QUẢ: TẤT CẢ KHỚP` |
| 2 | PC / Jetson | `make say TEXT="dẫn tôi đi lấy thùng bia" DRY=1` | `pick_box.sh --storage B --deliver --color blue` |
| 3 | Laptop + Jetson | cầu chạy với `--dry-run`, Jetson gõ `make say TEXT="dẫn tôi đi lấy thùng bia"` | Jetson: `✓ Robot đã nhận` · Laptop: `CHẠY pick_box.sh …` |
| 4 | Laptop | `./run_demo.sh` + cầu (bỏ `--dry-run`), rồi `python3 -m src.robot_link.say "dẫn tôi đi lấy thùng bia" --host 127.0.0.1` | xe chạy thật |
| 5 | Laptop | `… say "dừng lại" --host 127.0.0.1` rồi `"đi tiếp"` | xe đứng rồi chạy lại |
| 6 | cả ba | bấm **Bắt đầu ra lệnh** trên monitor, nói "kệ nào thiếu đồ" | robot trả lời, **không** chạy đi đâu |

**Bậc 5 là bậc quan trọng nhất** và là phần chưa từng chạy thật lần nào — làm trước ngày demo,
đừng để tới hôm đó.

30 giây trước khi khách vào, trên Jetson:

```bash
make say TEXT="dừng lại"        # phải thấy ✓, laptop phải log DỪNG
```

---

# E. Kịch bản demo

Bấm **Bắt đầu ra lệnh** trên màn monitor trước mỗi câu.

| # | Nói | Robot làm gì |
|---|---|---|
| 1 | "Xin chào" | chào lại — cho thấy nó phân biệt được trò chuyện với lệnh |
| 2 | "Kệ nào thiếu đồ?" | *"Khu A thiếu Gạo (còn 45 kg, tối thiểu 100). Khu C thiếu Muối…"* — **không** chạy đi đâu |
| 3 | "Khu B có gì?" | liệt kê 3 ô kèm màu hộp |
| 4 | "Dẫn tôi đi lấy thùng bia" | **lệnh chính** — chạy tới khu B, gắp hộp xanh dương, mang về đóng gói. Trên đường gặp công nhân băng qua |
| 5 | *đang chạy:* "Dừng lại!" | đứng ngay, ~1,2 giây vì không qua LLM. **Nhấn mạnh chỗ này** |
| 6 | "Đi tiếp" | chạy tiếp đúng đích cũ, không tính lại đường |
| 7 | *đang chạy:* "Thôi qua khu C lấy hộp màu xanh dương" | hủy chuyến cũ, quay sang khu C |
| 8 | "Qua khu A thôi, đừng lấy gì" | chạy trọn tuyến không gắp — đây là bài **né người** WAIT/PASS/REPLAN |

Câu 4 và câu 8 đáng tiền nhất: một cái cho thấy hiểu ngôn ngữ + gắp đúng hộp, một cái cho thấy dự
đoán quỹ đạo người.

## Hai chỗ phải nói cho đúng

**Lệnh dừng lúc đang gắp hàng.** Xe chạy hành lang thì "dừng lại" chặn sạch qua bộ mux ưu tiên.
Nhưng ở đoạn camera dẫn gắp cuối cùng, `vqa_mission.py` publish thẳng vào `/cmd_vel`, bỏ qua mux —
cầu chỉ **áp đảo được** chứ không tắt hẳn nó, nên xe có thể nhích nhẹ thay vì đứng chết. Muốn dừng
hẳn ở đoạn đó thì nói **"hủy chuyến"**. Hô "dừng lại" lúc xe đang chạy hành lang, đừng hô lúc nó
đang thò càng vào kệ.

**V-JEPA không phải VQA.** Nó làm *định vị bằng camera* và *dự đoán latent z(t+1..3)* — cả hai đều
thật, có biểu đồ L1/cosine. Phần mang tên "VQA" trong sa bàn là `warehouse_agv_demo/scripts/vqa_oracle.py`, một hàm
khớp từ khóa 76 dòng, docstring tự ghi là bản thay tạm chờ model trên Orin. Đừng giới thiệu nó là
"robot nhìn và hiểu".

---

# F. Trục trặc

| Hiện tượng | Nguyên nhân hay gặp | Xử lý |
|---|---|---|
| `make agent` không chịu khởi động, đòi train router | chưa chạy `make train-router` | chạy nó, trên chính PC này |
| Agent trả lời được vài câu rồi 500 | router train từ bộ nhãn cũ | `make train-router` lại |
| Ollama trả 404 | `LLM_MODEL` không khớp tên đã pull | `ollama list` rồi sửa `.env` cho khớp |
| `make build` chết ở monitor | thiếu node_modules | `make install` (đã sửa để cài cả monitor) |
| Nói xong robot không nhúc nhích, Jetson báo `Robot KHÔNG phản hồi` | cầu chưa chạy, hoặc Jetson không cùng mạng với laptop | `make netcheck` trên Jetson |
| Jetson gọi agent không được | ZeroTier trên Jetson rớt (PC chỉ có ở mạng đó) | `make netcheck` — dòng PC phải ghi `qua zt… (ZeroTier)`; `sudo zerotier-cli listnetworks` |
| Laptop log `KHÔNG CÓ LỜI GIẢI TỪ BRAIN — tự đọc` | VPN/PC không tới được | robot vẫn chạy bằng nhánh dự phòng; kiểm `AGENT_URL` trên Jetson |
| Laptop log `KHÔNG LÀM ĐƯỢC: sa bàn không có khu 'D'` | data lệch sa bàn | `make checkmap` trên PC |
| Nói "dừng lại" mà xe vẫn chạy | cầu chạy ở terminal chưa `source` ROS, hoặc chạy trên host thay vì trong container | lúc khởi động phải in `Giữ tốc độ: publisher … sẵn sàng` |
| Xe nhích nhẹ khi hô dừng | đang ở đoạn camera gắp hàng | nói "hủy chuyến" — xem mục E |
| Lượt thứ hai không thấy công nhân băng qua | có ai gọi thẳng `run_storage_pick.sh` | cầu luôn gọi `pick_box.sh`, chỉ nó mới reset công nhân |
| Container báo `make: command not found` | ảnh ROS gọn không có make | gọi thẳng `python3 -m src.robot_link.bridge …` |
| Robot đọc to một câu quảng cáo YouTube | Whisper bịa trên tiếng động ngắn | đã có bộ lọc; kiểm `grep -q "def _is_hallucination" src/edge_voice/perception/stt_phowhisper.py && echo CÓ` |
| Web monitor đứng ở "Sẵn sàng" suốt lượt | backend không nhận được lượt nói | kiểm `make agent` còn sống và `ORCHESTRATOR_URL` trên Jetson |

---

# G. Tắt

Ctrl-C từng cửa sổ. Trên laptop tắt **cầu UDP trước**, `run_demo.sh` sau — để nó kịp hủy đích Nav2
đang chạy. Trên PC, `make kill` dọn hết :8000 và :8100.

---

# H. Tra cứu nhanh

| Lệnh | Máy | Làm gì |
|---|---|---|
| `make setup` | PC, Jetson | nvm + Node 22 + uv (lần đầu) |
| `make install UV_EXTRAS="--extra server --extra cu12"` | PC | Python + npm cả 4 web |
| `make install UV_EXTRAS="--extra voice"` | Jetson | Python cho STT/TTS |
| `make train-router` | PC | train bộ phân loại ý định |
| `make build` | PC | build 4 web ra dist/ |
| `make backend` / `make agent` | PC | chạy :8000 / :8100 |
| `make voice` / `make jetson` | Jetson | chỉ voice / voice + màn rời |
| `make probe` | Jetson | thử mic, in text ra màn hình |
| `./run_demo.sh` | Laptop | Gazebo + Nav2 + V-JEPA |
| `python3 -m src.robot_link.bridge --demo-dir … --bind 0.0.0.0:45455` | Laptop | cầu UDP |
| `make netcheck` | bất kỳ | ba máy có thông nhau không |
| `make checkmap` | bất kỳ | data có khớp sa bàn không |
| `make caps` | bất kỳ | bảng câu nói → lệnh robot |
| `make say TEXT="…" [DRY=1]` | Jetson, PC | gõ câu bắn thẳng sang robot |
| `make kill` | PC | tắt hết dev server |
