#!/usr/bin/env bash
# Health check Jetson trước demo. Chạy sau mỗi lần boot.
R=/home/orin/AI_voice/AIWaiter; VP=$R/.venv/bin/python; ok=0; bad=0
p(){ if [ "$1" = 1 ]; then echo "  [OK]   $2"; ok=$((ok+1)); else echo "  [LỖI]  $2"; bad=$((bad+1)); fi; }

echo "── Hạ tầng ──"
[ -f /etc/ld.so.conf.d/ctranslate2.conf ] && p 1 "ld.so.conf ctranslate2" || p 0 "ld.so.conf ctranslate2 MẤT"
ldconfig -p | grep -q libctranslate2.so.4 && p 1 "loader thấy libctranslate2.so.4" || p 0 "loader KHÔNG thấy libctranslate2 → sudo ldconfig"
ldconfig -p | grep -q libcudss.so.0 && p 1 "loader thấy libcudss.so.0" || p 0 "loader KHÔNG thấy libcudss → torch sẽ chết"
[ -f /home/orin/AI_voice/ct2-runtime/lib/libctranslate2.so.4.6.0 ] && p 1 "lib ctranslate2 còn trên đĩa" || p 0 "lib ctranslate2 MẤT → build lại"
swapon --show | grep -q /swapfile && p 1 "swapfile 16G active" || p 0 "swapfile chưa mount"

echo "── Python env ──"
$VP -c "import torch;assert torch.cuda.is_available()" 2>/dev/null && p 1 "torch $($VP -c 'import torch;print(torch.__version__)' 2>/dev/null) + CUDA" || p 0 "torch/CUDA hỏng"
$VP -c "import ctranslate2;assert ctranslate2.get_cuda_device_count()>0" 2>/dev/null && p 1 "ctranslate2 $($VP -c 'import ctranslate2;print(ctranslate2.__version__)' 2>/dev/null) + CUDA" || p 0 "ctranslate2 hỏng"
$VP -c "import faster_whisper" 2>/dev/null && p 1 "faster-whisper" || p 0 "faster-whisper thiếu"
$VP -c "import pyaudio,sounddevice,soundfile,scipy,httpx,websockets,piper" 2>/dev/null && p 1 "deps voice đủ" || p 0 "thiếu deps voice"

echo "── Model cache (cần cho chạy offline) ──"
[ -d ~/.cache/huggingface/hub/models--Systran--faster-whisper-medium ] && p 1 "Whisper medium ($(du -sh ~/.cache/huggingface/hub/models--Systran--faster-whisper-medium 2>/dev/null|cut -f1))" || p 0 "Whisper CHƯA tải → cần internet"
[ -d ~/.cache/torch/hub/snakers4_silero-vad_master ] && p 1 "Silero VAD" || p 0 "Silero VAD CHƯA tải → cần GitHub"
ls $R/storage/tts/*.onnx >/dev/null 2>&1 && p 1 "Piper TTS model" || p 0 "Piper TTS CHƯA tải → cần internet"

echo "── Cấu hình demo ──"
[ -f $R/.env ] && p 1 ".env có ($(grep -c . $R/.env) dòng)" || p 0 ".env THIẾU"
arecord -l 2>/dev/null | grep -qi usb && p 1 "mic USB nhận" || p 0 "KHÔNG thấy mic USB"
# Loa: PortAudio không enumerate được card USB khi pulse đang giữ nó, nên VAD/TTS rơi về
# `default` -> pulse -> default sink/source. Tức là 2 giá trị mặc định của pulse LÀ đường
# âm thanh thật. Trỏ sai (mặc định của board là `platform-sound` = jack analog trống, và
# HDMI thì màn hình không có loa) = chạy không lỗi, log sạch, mà câm như hến.
USB_SINK=$(pactl list short sinks 2>/dev/null | grep -i usb | cut -f2 | head -1)
USB_SRC=$(pactl list short sources 2>/dev/null | grep -i "usb.*input\|alsa_input.*usb" | cut -f2 | head -1)
DEF_SINK=$(pactl info 2>/dev/null | sed -n 's/^Default Sink: //p')
DEF_SRC=$(pactl info 2>/dev/null | sed -n 's/^Default Source: //p')
[ -n "$USB_SINK" ] && [ "$DEF_SINK" = "$USB_SINK" ] \
  && p 1 "loa: default sink = USB" \
  || p 0 "default sink KHÔNG phải loa USB (đang: ${DEF_SINK:-không có}) → pactl set-default-sink \"$USB_SINK\""
[ -n "$USB_SRC" ] && [ "$DEF_SRC" = "$USB_SRC" ] \
  && p 1 "mic: default source = USB" \
  || p 0 "default source KHÔNG phải mic USB (đang: ${DEF_SRC:-không có}) → pactl set-default-source \"$USB_SRC\""
VOL=$(pactl get-sink-volume @DEFAULT_SINK@ 2>/dev/null | grep -o '[0-9]*%' | head -1)
[ -n "$VOL" ] && [ "${VOL%\%}" -gt 0 ] 2>/dev/null \
  && p 1 "âm lượng loa: $VOL" \
  || p 0 "âm lượng loa 0% hoặc không đọc được → pactl set-sink-volume @DEFAULT_SINK@ 45%"
pactl get-sink-mute @DEFAULT_SINK@ 2>/dev/null | grep -q "no" && p 1 "loa không mute" || p 0 "loa đang MUTE → pactl set-sink-mute @DEFAULT_SINK@ 0"
echo "  [info] power mode: $(cat /var/lib/nvpmodel/status 2>/dev/null) (0002=MAXN_SUPER là tốt nhất)"
echo "  [info] governor  : $(cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor)"
echo
echo "══ $ok OK, $bad LỖI ══"
[ $bad -eq 0 ] && echo "Sẵn sàng demo." || echo "Sửa các dòng [LỖI] trước khi demo."
