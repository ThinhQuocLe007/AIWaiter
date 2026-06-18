# Kế hoạch tách Brain / Body (AI Waiter)

> Tài liệu này mô tả việc tách **"Não" (AI/LLM/RAG, Python thuần)** ra khỏi **"Thân"
> (ROS 2 điều khiển robot)** và cho chúng nói chuyện qua **WebSocket/JSON**.
> Dùng để theo dõi tiến độ và lên ý tưởng các bước tiếp theo.

---

## 1. Vì sao tách

`ai_waiter_core` trước đây nằm trong `robot_ws/src/common/` (giả dạng ROS package) nhưng phải
`COLCON_IGNORE` để colcon đừng build — dấu hiệu nó đặt sai chỗ:

- Là **logic AI thuần Python** (LangGraph agent, RAG, STT/TTS), **không** import `rclpy`.
- Cần `torch`, `whisper`, `langchain`, `faiss`… → chạy bằng **uv** (Python 3.10), không qua colcon.

→ Tách thành 2 tiến trình độc lập, nối nhau qua một "hợp đồng" message rõ ràng.

### Phân vai 6 nhiệm vụ hệ thống

| Nhiệm vụ | Thuộc | Ở đâu |
|---|---|---|
| Nhận khách, trò chuyện | Não | `ai_waiter_core` |
| Order món | Não | `ai_waiter_core` (agent + RAG) |
| Thanh toán | Não | `ai_waiter_core` (payment_worker) |
| Di chuyển | Thân | `turtlebot4_navigation` (Nav2) |
| Giao món | Thân | `turtlebot4_python_tutorials/food_delivery` |

Não ra quyết định *"giao món bàn 3"* → gửi command → Thân thực thi điều hướng → báo ack về Não.

---

## 2. Kiến trúc đích

```
AI_Waiter/                         (uv env, Python 3.10 — NÃO)
├── ai_waiter_core/                ← đã chuyển ra đây
│   ├── ai_waiter_core/            (agent, services, perception, output, schemas, config, utils)
│   │   └── interfaces/ws_server.py   ← Phase 4: WebSocket server (Não)
│   ├── main.py                    (vòng STT → agent → TTS)
│   └── setup.py
├── pyproject.toml                 (uv; sẽ khai báo ai_waiter_core ở Phase 2)
└── robot_ws/                      (colcon, Python 3.10 — THÂN)
    └── src/sim/ai_waiter_ros/
        └── ai_waiter_ros/nodes/ai_brain_bridge.py   ← Phase 5: rclpy + WS client
```

Giao tiếp: **WebSocket/JSON** qua `localhost` (chọn vì 2 env tách biệt, không share import,
Não không cần dính `rclpy`).

---

## 3. Đã hoàn thành ✅

- **Phase 0** — Dọn dẹp: xóa package rỗng `ai_waiter_nav`; cập nhật `robot_ws/README.md`.
- **Phase 1** — Di chuyển Não ra khỏi `robot_ws`:
  - `git mv robot_ws/src/common/ai_waiter_core → ./ai_waiter_core` (giữ git history).
  - Xóa artifact ROS: `package.xml`, `COLCON_IGNORE`, `resource/`.
  - `setup.py` viết lại gọn (`find_packages()`, bỏ ament `data_files`, bỏ entry point hỏng).
  - Đã verify: `find_project_root()` vẫn bám `.git` ở gốc repo → đường dẫn `storage/assets/inputs`
    không đổi; `ai_waiter_core` không import `rclpy`.
- **Lock Python 3.10** (khớp ROS 2 Humble, tránh lệch version):
  - `.python-version` → `3.10`; `pyproject.toml` → `requires-python = ">=3.10,<3.11"`.
  - Nới pin chặn 3.10: `numpy>=2.0,<2.3`, `scikit-learn>=1.3,<1.9`.
  - `uv sync` chạy sạch trên CPython 3.10.12 → **clone về `uv sync` là được**.

> Yêu cầu máy clone: có `python3.10` (ROS Humble đã kèm sẵn) → `uv sync` tự tạo `.venv` 3.10.

---

## 4. Việc tiếp theo (chưa làm)

### Phase 2 — Cắm Não vào env uv
- [ ] Khai báo `ai_waiter_core` là package trong `pyproject.toml` (build-system + packages) để
      `uv sync` cài luôn → `import ai_waiter_core` chạy được trong env uv.
- [ ] Gộp dep còn thiếu của Não vào `pyproject.toml`: `torch`, `torchaudio`, `faster-whisper`,
      `edge-tts`, `sounddevice`, `soundfile`, `pyaudio`, `websockets`.
      (Hiện một số đã được kéo gián tiếp qua `sentence-transformers`; cần khai báo trực tiếp.)
- [ ] Thêm console script: `uv run ai-waiter-brain` → `ai_waiter_core.main:main`.
      ⚠️ Lưu ý: `main.py` đang ở **ngoài** package (`ai_waiter_core/main.py`) — cần chuyển vào
      trong package hoặc trỏ module cho đúng.

### Phase 3 — Định nghĩa "hợp đồng" WebSocket (xem mục 5)
- [ ] Viết schema pydantic 2 chiều + tài liệu `docs/brain_robot_protocol.md`.

### Phase 4 — Phía Não: `ws_server.py` (hiện đang RỖNG)
- [ ] Server WebSocket async (`websockets`): nhận/đẩy command + chờ ack.
- [ ] Móc vào `main.py`: khi agent quyết định hành động vật lý → gửi command xuống Thân.

### Phase 5 — Phía Thân: ROS bridge (hiện chỉ là prototype cũ)
- [ ] Viết node `ai_brain_bridge.py` (rclpy + WS client): nhận command → gọi
      `TurtleBot4Navigator` / `food_delivery`, bắn ack/trạng thái về Não.
- [ ] Đăng ký entry point trong `ai_waiter_ros/setup.py` (hiện `console_scripts` rỗng).
- [ ] **Bỏ `<depend>ai_waiter_msgs</depend>`** trong `ai_waiter_ros/package.xml` (package này
      không tồn tại; dùng WebSocket nên không cần custom ROS msg).

### Phase 6 — Dọn & tài liệu
- [ ] Cập nhật `robot_ws/README.md` (Não không còn trong `src/`).
- [ ] Hướng dẫn chạy 2 phần: `uv run ai-waiter-brain` + `ros2 run ai_waiter_ros ai_brain_bridge`.

---

## 5. Bản nháp protocol WebSocket (Phase 3)

JSON qua `localhost`. Gợi ý message:

**Não → Thân (lệnh):**
```jsonc
{ "type": "navigate",    "table_id": 3 }   // tới bàn 3
{ "type": "return_dock" }                  // về bếp/dock
{ "type": "deliver" }                      // báo đã tới, thực hiện giao
```

**Thân → Não (sự kiện/ack):**
```jsonc
{ "type": "arrived",          "table_id": 3 }
{ "type": "nav_failed",       "reason": "..." }
{ "type": "customer_detected" }
{ "type": "status", "state": "moving|idle|delivering" }
```

---

## 6. ⚠️ Rủi ro lớn nhất — KHÔNG chỉ là "nối dây"

**Agent hiện chỉ trả về *text*** (`agent.chat()` → `response`). **Chưa có chỗ nào sinh lệnh điều
khiển robot** (đi bàn nào, giao món). Các worker order/payment đã có, nhưng thiếu hẳn "action
output". → Phase 4–5 phải **thêm logic để agent phát lệnh hành động**, đây là phần việc thật sự.

**Quyết định cần chốt trước khi code tiếp:**
1. **Não chạy vật lý ở đâu?** Cùng Jetson với ROS (nói chuyện qua `localhost`)? Hay máy/tablet
   riêng (cần đổi host/port, mở firewall)? — Vì Não cần mic/loa.
2. **Ai là server, ai là client?** (Gợi ý: Não = server, bridge ROS = client.)
3. Cơ chế khi mất kết nối / nav thất bại (retry, timeout, robot tự về dock?).
</content>
