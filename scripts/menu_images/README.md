# Menu image pipeline

Tái tạo ảnh món ăn trong `src/frontends/customer_ui/public/dishes/` từ ảnh trang menu gốc
(`assets/data/menu_images/`), không tẩy nền phá chi tiết (nồi/đĩa trắng giữ nguyên).

```bash
python recrop.py    # dò vị trí crop trên trang gốc (masked NCC), cắt lại -> work/recropped
python cleanup.py   # dọn chữ/giá/gạch/khối cam của layout menu -> work/final
cp work/final/*.jpg ../../src/frontends/customer_ui/public/dishes/
```

Cần: numpy, scipy, Pillow (có sẵn trong .venv). `recrop.py` dùng chính ảnh dishes hiện tại
làm template (mask bỏ vùng trắng), nên chạy được cả khi ảnh đích đã qua xử lý.
