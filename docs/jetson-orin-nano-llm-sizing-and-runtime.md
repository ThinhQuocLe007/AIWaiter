# 0007 — Chọn LLM local & runtime để deploy trên Jetson Orin Nano 8GB

> Quyết định kỹ thuật: cỡ LLM và runtime inference để deploy toàn bộ AI_Waiter (Brain + Body)
> xuống một con Jetson Orin Nano 8GB. Cập nhật: 2026-06-23.

## Context (vì sao làm việc này)

Cần deploy **toàn bộ** AI_Waiter (Brain = LLM + RAG + STT/TTS, và Body = ROS2/Nav2) xuống **1 con Jetson Orin Nano 8GB unified RAM**, chạy **time-multiplex** (đang Nav2 thì tắt LLM, đang hội thoại thì robot đứng yên nên Nav2 nhàn). Câu hỏi cốt lõi: **LLM local cỡ nào để hệ chạy được với "sai số ít nhất"** mà vẫn vừa RAM + đủ nhanh cho giọng nói (ưu tiên *cân bằng*).

Hai phát hiện quan trọng định hình quyết định:
1. **Ràng buộc thật không chỉ là cỡ model mà là runtime.** Ollama trên Jetson không tận dụng iGPU tốt. Đã thử ONNX→TensorRT `.engine` nhưng chỉ build nổi Qwen3 0.6B (quá bé, **mất tool-calling** + context bé) → TensorRT-LLM **không khả thi** cho model cần tool-calling trên Orin Nano. Đường đi thực tế: **llama.cpp build CUDA (GGUF Q4)**.
2. **Hệ đã được thiết kế chịu lỗi cho model nhỏ:** router chạy **semantic centroid trước** (~50-70% intent không gọi LLM), workers có **validator deterministic + retry 3 lần**, resolve tên món bằng Python. Nghĩa là **không cần model lớn** — chỗ model nhỏ dễ gãy nhất là **tool-calling + structured output (JSON)**, nên tiêu chí chọn model phải xoay quanh độ tin cậy tool-calling, không phải "thông minh" chung chung.

Yêu cầu của LLM (xác minh trong code):
- **Tool-calling**: `order_worker`/`search_worker`/`payment_worker` `.bind_tools(...)` (sync_cart, confirm_order, search, request_payment, verify_payment).
- **Structured output (JSON Pydantic)**: `slm_router_node` (`IntentPrediction`), `critic_node` (`CriticVerdict`).
- **Sinh tiếng Việt tự nhiên**: `response_node`.
- Hiện dùng chung 1 model cho cả 3 vai (`gemma4:e2b-it-qat` = Gemma 3n E2B ~2B hiệu dụng), `LLM_NUM_CTX=8192`.

## Khuyến nghị cỡ model (kết luận)

**Sweet spot = model instruct ~3B–4B, lượng tử 4-bit (Q4_K_M), chạy GGUF trên llama.cpp-CUDA.** Đây là cỡ lớn nhất chạy *thoải mái* trên Orin Nano 8GB ở pha hội thoại mà vẫn ~10-20 tok/s, đồng thời đủ tin cậy tool-calling/JSON để giảm sai số rõ rệt so với 2B. Đi lên 7-8B thì hoặc vỡ RAM hoặc prefill prompt ~3.5k token quá chậm cho voice → không nên.

Thứ tự ứng viên benchmark (đều có tool-calling + tiếng Việt, đều có GGUF):

| Hạng | Model (GGUF Q4_K_M) | ~RAM weights | Ghi chú |
|---|---|---|---|
| **Top khuyến nghị** | `Qwen2.5-3B-Instruct` | ~2.0 GB | tool-calling/JSON tốt nhất ở cỡ nhỏ, VN khá |
| Thay thế (VN mượt hơn) | `Gemma-3-4B-it` (QAT q4) | ~2.6 GB | tiếng Việt response mượt, tool-calling ổn |
| Baseline hiện tại | Gemma 3n E2B (đang dùng) | ~2-3 GB | giữ làm mốc so sánh |
| Sàn (nếu cần nhẹ/nhanh) | `Qwen2.5-1.5B-Instruct` | ~1.0 GB | còn tool-calling, nhanh, sai số cao hơn |
| **Loại** | Qwen3 0.6B | — | **mất tool-calling** → không dùng |
| **Loại** | 7-8B Q4 | ~4.5-5 GB | vỡ budget / prefill quá chậm cho voice |

> "Sai số ít nhất *trong giới hạn phần cứng*" = model lớn nhất còn vừa & đủ nhanh. Trên Orin Nano 8GB đó là **lớp 3-4B Q4**. Quyết định cuối chọn bằng **số đo eval**, không chọn cảm tính (xem mục Verify).

## Ngân sách RAM ở pha hội thoại (Nav2 idle)
- OS + JetPack + ROS idle: ~2.0-2.5 GB
- STT faster-whisper `small` (int8 CPU): ~0.5 GB  ·  VAD Silero (CPU): ~0.1 GB
- Embedding (CPU, model nhẹ): ~0.5 GB
- → **còn ~4-4.5 GB cho LLM** (weights Q4 ~2-3 GB + KV cache 8192 ctx ~0.5-1 GB) → lớp 3-4B vừa.

## Các thay đổi cần làm

### 1. Runtime: chuyển Ollama → llama.cpp-CUDA (đòn bẩy lớn nhất về tốc độ)
- Build/lấy `llama.cpp` có CUDA cho Jetson (qua `jetson-containers` hoặc build `-DGGML_CUDA=on`), chạy `llama-server` (OpenAI-compatible) với `--n-gpu-layers -1`.
- **Code thay đổi tối thiểu**: các node dùng `langchain_ollama.ChatOllama`. Hai lựa chọn:
  - (a) Giữ Ollama nhưng dùng bản build CUDA (jetson-containers `ollama`) — ít sửa code nhất, chỉ cần model GGUF; **làm trước để đo**.
  - (b) Đổi sang `llama-server` + `langchain_openai.ChatOpenAI(base_url=...)` hoặc `ChatOllama` trỏ tới endpoint — nhiều quyền kiểm soát hơn (n-gpu-layers, KV quant).
- Bọc một factory `make_chat_llm(role)` để mọi node lấy client từ một chỗ (hiện mỗi node tự `ChatOllama(...)`), dễ A/B runtime/model.

### 2. Đổi model qua `.env` (không sửa code logic)
- Model đọc từ env: `ROUTER_MODEL`/`WORKER_MODEL`/`RESPONSE_MODEL` trong `.env` (xác minh tại `ai_waiter_core/config/agent_config.py:7-9`). Đổi 3 dòng này để A/B từng ứng viên.
- Giữ thống nhất 1 model cho cả 3 vai (để runtime chỉ giữ 1 model resident — lý do đã chốt ở các phân tích deploy Jetson trước).

### 3. Levers giải phóng RAM (đã có sẵn trong code)
- `.env`: `EMBEDDING_DEVICE=cpu` để đẩy embedding khỏi iGPU (`hardware_config.py:9-11` đã hỗ trợ; fp16↔fp32 tự chọn theo device tại `embeddings.py:95`).
- Đổi embedding nhẹ để test: `EMBEDDING_MODEL=bkai-foundation-models/vietnamese-bi-encoder` (~0.5GB) rồi rebuild index: `python scripts/setup.py --embeddings-only`. (Danh sách ứng viên đã liệt kê trong `.env.template`.)
- KV cache: cân nhắc hạ `LLM_NUM_CTX` 8192→6144 nếu cần thêm RAM (order worker cần ~3.5k token prompt → **không** hạ dưới ~5k).
- STT: nếu cần thêm RAM/tốc độ, thử whisper `base`/`tiny` (sửa `perception/stt_phowhisper.py:23`) — nhưng cân nhắc giảm độ chính xác tiếng Việt; giữ `small` int8 là mặc định an toàn.

### 4. (Sau, không chặn) TTS offline
- Hiện `output/tts_engine.py` dùng **edge-tts (cloud)** → vi phạm "local-first" khi mất internet. Hiện *ưu tiên offline nhưng chưa bắt buộc*. TODO: thay bằng TTS local (vd Piper voice VI) khi cần offline thật — tốn thêm ~0.1-0.3GB.

## Verify (cách chọn model "sai số ít nhất" bằng số đo)

Dùng **bộ eval có sẵn** (đọc model từ `.env`, không cần sửa) để lập ma trận so sánh. Với mỗi ứng viên: `ollama pull`/load GGUF → set 3 biến model trong `.env` → chạy:

```bash
# Router accuracy + độ trễ (semantic vs SLM)
python evals/scripts/eval_router.py
# End-to-end: tool gọi đúng không, item confirm đúng không, response chứa từ khoá kỳ vọng
python evals/scripts/eval_e2e.py
# Chặn món ngoài menu
python evals/scripts/eval_out_of_menu.py
# (RAG, chạy 1 lần khi đổi embedding)
python evals/scripts/eval_retrieval.py
```

Đọc kết quả ở `evals/results/*.json` (router: `accuracy`, `overall_avg_latency_s`; e2e: `pass_rate`). **Tiêu chí chọn**: pass-rate cao nhất với độ trễ/turn chấp nhận được cho voice (mục tiêu gợi ý: e2e first-token + decode đủ để robot đáp trong ~2-4s/lượt). Lập bảng: `{model, e2e_pass_rate, router_acc, avg_latency, RAM resident}` → chọn điểm cân bằng (kỳ vọng: Qwen2.5-3B hoặc Gemma-3-4B).

Đo trực tiếp trên Jetson (không chỉ máy dev) vì tok/s và RAM khác hẳn. Kiểm RAM khi chạy: `tegrastats` / `jtop`.

## File/đường dẫn chính
- `ai_waiter_core/config/agent_config.py` — `*_MODEL`, `LLM_NUM_CTX`
- `ai_waiter_core/config/hardware_config.py` + `.env` — `DEVICE`, `EMBEDDING_DEVICE`, `EMBEDDING_MODEL`
- `ai_waiter_core/agent/nodes/{slm_router_node,order_worker_node,search_worker_node,payment_worker_node,response_node,critic_node}.py` — nơi khởi tạo `ChatOllama` (gom về 1 factory nếu đổi runtime)
- `ai_waiter_core/perception/stt_phowhisper.py` — cỡ model STT
- `ai_waiter_core/output/tts_engine.py` — TTS (edge-tts, item offline sau)
- `ai_waiter_core/services/retriever/indices/embeddings.py` — `EMBEDDING_PROFILES`, fp16/fp32
- `evals/scripts/*.py` — đo sai số
- `scripts/setup.py --embeddings-only` — rebuild index khi đổi embedding
