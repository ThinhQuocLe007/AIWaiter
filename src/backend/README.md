# Orchestrator backend (FastAPI + SQLite)

Server trung tâm điều phối — sở hữu trạng thái bàn/đơn/thanh toán và chia task cho robot
(xem `docs/SYSTEM_ARCHITECTURE.md`, mục 8–9). Đứng **độc lập**: không import `ai_waiter_core`.

## Chạy (từ repo root)

```bash
uv run uvicorn src.backend.app.main:app --reload --port 8000
```

- API docs: http://localhost:8000/docs
- Health:   http://localhost:8000/health
- Menu:     http://localhost:8000/menu

DB SQLite tạo tự động ở `storage/db/orchestrator.db` (schema 7 bảng, seed `dishes` từ
`assets/data/menu.json`).

## Cấu trúc

```
src/backend/app/
├── main.py          # FastAPI app, CORS, lifespan (init_db + seed), mount routers
├── config.py        # Settings (env prefix ORCH_): đường dẫn menu/db, CORS origins
├── db.py            # sqlite3 + schema mục 8 (tables/dishes/orders/.../payments)
├── menu.py          # load_menu() từ menu.json + seed_dishes()
└── routers/
    └── menu.py      # GET /menu
```

## Lộ trình (theo mục 11)

- [x] Bước 0 — khung FastAPI + SQLite + `GET /menu`
- [ ] Bước 1 — nối `customer_ui` loadMenu() vào `GET /menu`
- [ ] Bước 2 — `POST /orders` + confirmOrder()
- [ ] Bước 3 — WebSocket `/ws` (server đẩy lệnh chuyển màn cho UI)
- [ ] Bước 4 — payment: bill + QR + webhook
