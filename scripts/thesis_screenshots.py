"""Chụp ảnh màn hình 3 web UI cho luận văn (§4.8 Web Interfaces).

Chạy TRÊN MÁY CÓ TRÌNH DUYỆT, sau khi `make build` và `make backend` đã chạy:

    make build                                  # dist/ mới nhất cho cả 3 app
    make backend                                # phục vụ cả 3 app trên :8000
    uv run python scripts/mock_robot.py --id robo-1   # (tuỳ chọn) robot ảo cho minimap
    uv run python scripts/thesis_screenshots.py --seed

Script tự dựng một "ca phục vụ" giả (3 bàn có khách, đơn ở cả 3 cột bếp, một lượt
hội thoại giọng nói) rồi lái Chromium/Brave qua CDP để chụp từng màn hình vào
docs/thesis/images/ui/.

Bỏ --seed nếu muốn chụp đúng trạng thái hệ thống đang chạy (không đụng vào DB).
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

try:
    import websockets
except ImportError:  # pragma: no cover - dependency check
    sys.exit("Thiếu `websockets`. Chạy: uv sync --extra server")

REPO = Path(__file__).resolve().parent.parent
DEFAULT_OUT = REPO / "docs" / "thesis" / "images" / "ui"

BROWSERS = [
    "brave-browser",
    "chromium",
    "chromium-browser",
    "google-chrome",
    "google-chrome-stable",
]

# ---------------------------------------------------------------------------
# REST helpers
# ---------------------------------------------------------------------------


def api(base: str, path: str, payload=None, method: str | None = None):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        base + path,
        data=data,
        method=method or ("POST" if data is not None else "GET"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=10) as r:
        body = r.read().decode()
    return json.loads(body) if body else None


def seed(base: str) -> None:
    """Dựng một ca phục vụ đủ đông để mọi vùng của panel có dữ liệu."""
    menu = api(base, "/menu")
    by_name = {d["name"]: d for d in menu}

    def item(name, qty, note=None):
        d = by_name[name]
        out = {"name": d["name"], "qty": qty, "price": float(d["price"])}
        if note:
            out["note"] = note
        return out

    api(base, "/admin/reset", {})
    for table_id, party in ((1, 4), (3, 2), (5, 3)):
        api(base, "/seatings", {"table_id": table_id, "party_size": party})

    o1 = api(base, "/orders", {"table_id": 1, "items": [
        item("Ốc Hương Xốt Trứng Muối", 2),
        item("Tôm Thẻ Xốt Bơ Cay", 1, "ít cay"),
        item("Bánh Mì Bơ Tỏi", 2),
    ]})
    api(base, "/orders", {"table_id": 3, "items": [
        item("Ốc Hương Xốt Me", 1),
        item("Mực Cháy Tỏi", 1),
    ]})
    o5 = api(base, "/orders", {"table_id": 5, "items": [
        item("Sò Điệp Nướng Phô Mai", 2),
        item("Sò Điệp Nướng Mỡ Hành", 3),
        item("Trà Tắc", 3),
    ]})
    # Một đơn ở mỗi cột: Chờ bếp (bàn 3), Đang làm (bàn 1), Xong (bàn 5).
    api(base, f"/orders/{o1['id']}", {"status": "DANG_LAM"}, method="PATCH")
    api(base, f"/orders/{o5['id']}", {"status": "XONG"}, method="PATCH")
    print("seed: 3 bàn có khách, 3 đơn ở 3 cột bếp")


def push_voice_turn(base: str, table_id: int) -> None:
    """Đẩy một lượt hội thoại xuống tablet để chụp voice mirror + giỏ hàng."""
    api(base, "/voice/event", {
        "type": "voice.heard",
        "table_id": table_id,
        "text": "Cho mình hai phần ốc hương xốt trứng muối với một phần mực cháy tỏi nhé",
    })
    api(base, "/voice/event", {
        "type": "voice.reply",
        "table_id": table_id,
        "text": "Dạ, em đã thêm 2 phần Ốc Hương Xốt Trứng Muối và 1 phần Mực Cháy Tỏi vào giỏ. "
                "Anh chị dùng thêm món gì nữa không ạ?",
        "stage": "ordering",
        "cart_touched": True,
        "cart": [
            {"name": "Ốc Hương Xốt Trứng Muối", "quantity": 2},
            {"name": "Mực Cháy Tỏi", "quantity": 1},
        ],
    })


# ---------------------------------------------------------------------------
# CDP driver
# ---------------------------------------------------------------------------


class Browser:
    """Chromium/Brave headless điều khiển qua DevTools Protocol."""

    def __init__(self, binary: str, port: int = 9444, scale: int = 2):
        self.binary = binary
        self.port = port
        self.scale = scale
        self.profile = tempfile.mkdtemp(prefix="thesis-shots-")
        self.proc: subprocess.Popen | None = None
        self.ws = None
        self._id = 0

    async def start(self) -> None:
        self.proc = subprocess.Popen(
            [
                self.binary,
                "--headless=new",
                "--no-sandbox",
                "--disable-gpu",
                "--hide-scrollbars",
                "--disable-dev-shm-usage",
                f"--remote-debugging-port={self.port}",
                f"--user-data-dir={self.profile}",
                "about:blank",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        target = None
        for _ in range(60):
            try:
                with urllib.request.urlopen(
                    f"http://127.0.0.1:{self.port}/json/list", timeout=2
                ) as r:
                    pages = [t for t in json.loads(r.read()) if t["type"] == "page"]
                if pages:
                    target = pages[0]["webSocketDebuggerUrl"]
                    break
            except Exception:
                pass
            await asyncio.sleep(0.5)
        if not target:
            raise RuntimeError(f"{self.binary}: DevTools không lên ở cổng {self.port}")
        self.ws = await websockets.connect(target, max_size=200 * 1024 * 1024)
        await self.send("Page.enable")
        await self.send("Runtime.enable")

    async def send(self, method: str, params: dict | None = None, timeout: float = 30):
        self._id += 1
        mid = self._id
        await self.ws.send(json.dumps({"id": mid, "method": method, "params": params or {}}))
        while True:
            msg = json.loads(await asyncio.wait_for(self.ws.recv(), timeout=timeout))
            if msg.get("id") == mid:
                if "error" in msg:
                    raise RuntimeError(f"{method}: {msg['error']}")
                return msg.get("result", {})

    async def viewport(self, width: int, height: int) -> None:
        await self.send("Emulation.setDeviceMetricsOverride", {
            "width": width,
            "height": height,
            "deviceScaleFactor": self.scale,
            "mobile": False,
        })

    async def goto(self, url: str, wait: float = 4.0) -> None:
        await self.send("Page.navigate", {"url": url})
        await asyncio.sleep(wait)

    async def js(self, expression: str, wait: float = 0.0):
        res = await self.send("Runtime.evaluate", {
            "expression": expression,
            "awaitPromise": True,
            "returnByValue": True,
        })
        if wait:
            await asyncio.sleep(wait)
        return res.get("result", {}).get("value")

    async def click(self, selector: str, wait: float = 1.0) -> bool:
        ok = await self.js(
            f"(() => {{ const el = document.querySelector({selector!r});"
            f" if (!el) return false; el.click(); return true; }})()"
        )
        if wait:
            await asyncio.sleep(wait)
        return bool(ok)

    async def shot(self, path: Path) -> None:
        res = await self.send("Page.captureScreenshot", {"format": "png"})
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(base64.b64decode(res["data"]))
        print(f"  ✓ {path.relative_to(REPO) if path.is_relative_to(REPO) else path}")

    async def close(self) -> None:
        try:
            if self.ws:
                await self.ws.close()
        finally:
            if self.proc:
                self.proc.terminate()
            shutil.rmtree(self.profile, ignore_errors=True)


# ---------------------------------------------------------------------------
# Capture plan
# ---------------------------------------------------------------------------

TABLET = (1024, 600)   # màn hình cảm ứng trên robot (stage cố định của customer_ui)
KIOSK = (1280, 900)    # tablet đứng ở cổng
PANEL = (1600, 1000)   # màn hình nhân viên


async def capture(base: str, out: Path, binary: str) -> None:
    b = Browser(binary)
    await b.start()
    try:
        # --- 4.8.3 Management panel -------------------------------------
        print("panel…")
        await b.viewport(*PANEL)
        await b.goto(f"{base}/panel/", wait=6)
        await b.shot(out / "panel-overview.png")

        # --- 4.8.2 Kiosk ------------------------------------------------
        print("kiosk…")
        await b.viewport(*KIOSK)
        await b.goto(f"{base}/kiosk/", wait=5)
        await b.shot(out / "kiosk-grid.png")
        if await b.click(".table-card.free", wait=1.2):
            await b.shot(out / "kiosk-seating.png")
        else:
            print("  ! không thấy bàn trống nào để mở bước chọn số khách")

        # --- 4.8.1 Ordering screen --------------------------------------
        print("ordering screen…")
        await b.viewport(*TABLET)
        # Bàn 2 đang trống -> màn hình chào.
        await b.goto(f"{base}/", wait=2)
        await b.js("localStorage.setItem('robodish.tableId','2')")
        await b.goto(f"{base}/#/", wait=4)
        await b.js("location.reload()", wait=4)
        await b.shot(out / "ordering-welcome.png")

        # Bàn 1 đang ăn -> menu, hội thoại giọng nói, thanh toán.
        await b.js("localStorage.setItem('robodish.tableId','1')")
        await b.goto(f"{base}/#/menu", wait=2)
        await b.js("location.reload()", wait=5)
        await b.shot(out / "ordering-menu.png")

        push_voice_turn(base, 1)
        await asyncio.sleep(2.5)
        await b.shot(out / "ordering-voice.png")

        await b.js("location.hash = '#/payment'", wait=4)
        await b.shot(out / "ordering-payment.png")
    finally:
        await b.close()


def find_browser(explicit: str | None) -> str:
    if explicit:
        return explicit
    for name in BROWSERS:
        path = shutil.which(name)
        if path:
            return path
    sys.exit("Không tìm thấy Chromium/Chrome/Brave. Dùng --browser /đường/dẫn.")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--base", default="http://127.0.0.1:8000", help="gốc của backend")
    ap.add_argument("--out", default=str(DEFAULT_OUT), help="thư mục ảnh")
    ap.add_argument("--browser", default=None, help="đường dẫn Chromium/Brave")
    ap.add_argument("--seed", action="store_true", help="dựng dữ liệu demo (RESET hệ thống)")
    args = ap.parse_args()

    base = args.base.rstrip("/")
    try:
        api(base, "/health")
    except (urllib.error.URLError, OSError) as e:
        sys.exit(f"Backend không phản hồi ở {base} ({e}). Chạy `make backend` trước.")

    if args.seed:
        seed(base)

    asyncio.run(capture(base, Path(args.out), find_browser(args.browser)))
    print("Xong. Ảnh nằm trong", args.out)


if __name__ == "__main__":
    main()
