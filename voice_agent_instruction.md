TÀI LIỆU YÊU CẦU TÍCH HỢP HỆ THỐNG TRỢ LÝ GIỌNG NÓI VOICE AI - ROBODISHChào Claude, dưới đây là đặc tả kỹ thuật chi tiết để tích hợp tính năng Trợ lý Giọng nói thông minh (Voice AI Assistant) vào ứng dụng đặt món RoboDish hiện tại. Hãy đọc kỹ kiến trúc, luồng xử lý và giao diện mong muốn dưới đây để tiến hành viết code/refactor một cách chuẩn xác nhất.📌 TỔNG QUAN HAI THÀNH PHẦN CẦN THÊMChúng ta sẽ thêm 2 thành phần giao diện mới vào hệ thống:Smart Banner Card (Thẻ Đầu Trang): Đặt ở vị trí trên cùng của danh sách món ăn, đóng vai trò kích hoạt (Call to Action - CTA).Bottom Sheet Voice Panel (Bảng Điều Hướng Giọng Nói): Bật lên từ phía dưới màn hình khi kích hoạt Voice AI, hiển thị hoạt cảnh sóng âm, đoạn chat thời gian thực và đề xuất món ăn thông minh.🛠 1. QUẢN LÝ TRẠNG THÁI (STATE MANAGEMENT)Để hệ thống hoạt động trơn tru, hãy khai báo thêm các State dưới đây trong component chính (hoặc qua Context/State Management hiện tại):// Trạng thái hiển thị Panel Voice
const [isAiOpen, setIsAiOpen] = useState(false); 

// Trạng thái hoạt động của AI: 
// - 'idle': Chờ bắt đầu
// - 'listening': Đang thu âm giọng khách hàng (Hiển thị sóng âm chuyển động)
// - 'thinking': Đang xử lý ngôn ngữ/LLM (Hiển thị loading 3 chấm)
// - 'speaking': Đang phản hồi/đọc thoại (Hiển thị text & đề xuất món)
const [aiState, setAiState] = useState('idle'); 

// Nội dung text khách hàng nói (Speech-to-Text)
const [speechText, setSpeechText] = useState(''); 

// Câu trả lời của AI trợ lý
const [aiResponse, setAiResponse] = useState(''); 

// Món ăn được gợi ý bởi AI trong phiên hội thoại (Object món ăn hoặc null)
const [recommendedItem, setRecommendedItem] = useState(null); 

// Trạng thái bật/tắt tiếng (Sound feedback)
const [isSoundEnabled, setIsSoundEnabled] = useState(true); 
🎨 2. CHI TIẾT THÀNH PHẦN GIAO DIỆN (UI/UX)THÀNH PHẦN 1: Thẻ gợi ý thông minh (Smart Banner Card)Vị trí: Đặt ngay phía trên cùng của Danh sách món ăn (<main> content), nằm trên grid hiển thị các món.Giao diện (Tailwind CSS):Sử dụng màu nền Gradient chuyển sắc ấm từ Đỏ cam sang Cam sáng (from-red-500 via-rose-500 to-orange-500) để tăng độ nổi bật nhưng vẫn đồng bộ với tone thương hiệu.Bo góc lớn (rounded-2xl), đệm p-4 hoặc p-5.Có biểu tượng Robot chìm mờ ở góc phải (opacity-15) để tăng tính thẩm mỹ công nghệ.Nút bấm hành động (CTA Button) màu trắng, chữ đỏ đậm, có icon Mic nhấp nháy chuyển động (animate-bounce).Hành động khi Click: Đặt isAiOpen(true) và gọi hàm kích hoạt nhận diện giọng nói.THÀNH PHẦN 2: Bảng trượt tương tác Voice (Bottom Sheet Voice Panel)Vị trí & Layout:Cố định ở đáy màn hình thiết bị (absolute inset-x-0 bottom-0 hoặc fixed tùy cấu trúc view của bạn).Chiều cao tối đa: max-h-[460px].Nền tối (bg-slate-900), bo tròn 2 góc trên (rounded-t-[24px]), viền trên mờ (border-t border-slate-800), hiệu ứng bóng mờ cực mạnh (shadow-2xl).Thanh Header Panel:Có chấm tròn xanh lá cây nhấp nháy báo trạng thái trực tuyến (bg-emerald-500 animate-pulse).Text tiêu đề nhỏ gọn màu sáng nhạt.Nút bật/tắt âm thanh (Volume2 / VolumeX).Nút đóng Panel dạng chéo (X).Khu vực Nội dung Chat (Phát triển theo luồng cuộn):Hộp thoại người dùng (User Speech): Đặt lệch phải (self-end), nền tối xám (bg-slate-800), bo góc tròn mềm không có góc nhọn bên phải (rounded-tr-none).Hộp thoại AI (AI Agent Response): Đặt lệch trái (self-start), có Avatar tròn biểu tượng Robot (Bot), nền màu chuyển sắc sâu (bg-gradient-to-b from-slate-800 to-slate-850), viền mờ (border border-slate-750).Thẻ món ăn đề xuất (Recommended Card): Khi AI tư vấn món cụ thể, thẻ này trượt ra dưới bong bóng thoại của AI. Thẻ này chứa: ảnh món ăn thu nhỏ bên trái, tên món, giá tiền và nút "Thêm nhanh" màu xanh (bg-emerald-500) để người dùng có thể click thêm thẳng vào giỏ hàng thật.Hoạt cảnh Sóng âm (Voice Waveform Animation):Chỉ xuất hiện khi aiState === 'listening'.Gồm 5 thanh đứng (span) sử dụng CSS Transform ScaleY để mô phỏng sóng âm thanh nhấp nhô sống động.⚙️ 3. LOGIC HỘI THOẠI & ĐIỀU KHIỂN GIỎ HÀNG (INTEGRATION LOGIC)Kịch bản Mô phỏng / Luồng API kết nối LLM:Khi khách hàng tương tác bằng giọng nói, hãy thiết lập Claude xử lý theo luồng logic sau:Lắng nghe: Chuyển trạng thái setAiState('listening'). Thực hiện lắng nghe giọng nói.Phân tích: Chuyển sang setAiState('thinking'). Gửi câu thoại lên LLM để bóc tách ý định (Intent).Phản hồi: Chuyển sang setAiState('speaking'). AI trả về lời thoại tư vấn kèm món ăn gợi ý (setRecommendedItem).Tác vụ tự động (Quan trọng): Nếu khách nói ý định đồng ý (ví dụ: "Lấy cho tôi món đó", "Thêm lẩu nhé"), hệ thống phải kích hoạt hàm thêm món vào giỏ hàng hiện tại: addToCart(recommendedItem).📝 4. ĐOẠN MẪU GIAO DIỆN CHUẨN (JSX REFERENCE)Claude hãy tham khảo cấu trúc code JSX mẫu dưới đây để áp dụng chính xác các class Tailwind CSS:Smart Banner Card:<div className="bg-gradient-to-r from-red-500 via-rose-500 to-orange-500 rounded-2xl p-4 text-white shadow-lg relative overflow-hidden shrink-0">
  <div className="absolute right-0 bottom-0 translate-x-3 translate-y-3 opacity-15">
    <Bot className="w-32 h-32" />
  </div>
  <div className="relative z-10 max-w-[80%]">
    <span className="bg-white/20 text-[10px] font-bold px-2.5 py-0.5 rounded-full uppercase tracking-wider inline-block mb-1.5">
      Đặc Quyền Rảnh Tay ⚡
    </span>
    <h3 className="text-md font-extrabold mb-1">Hôm nay bạn muốn ăn gì?</h3>
    <p className="text-[11px] text-white/85 mb-3 leading-snug">
      Chỉ cần nói cho Trợ lý ảo RoboDish sở thích, chúng mình sẽ chọn món siêu ngon giúp bạn trong 5 giây!
    </p>
    <button 
      onClick={() => { setIsAiOpen(true); }}
      className="bg-white text-red-600 font-extrabold text-xs px-4 py-2 rounded-xl flex items-center gap-1.5 shadow-sm hover:bg-red-50 transition active:scale-95"
    >
      <Mic className="w-3.5 h-3.5 animate-bounce" />
      Nói Chuyện Với AI Ngay
    </button>
  </div>
</div>
Hoạt cảnh Sóng âm (Waveform Animation CSS):/* Thêm vào file CSS toàn cục hoặc thẻ <style> */
@keyframes wave {
  0%, 100% { transform: scaleY(0.4); }
  50% { transform: scaleY(1.2); }
}
.animate-wave-1 { animation: wave 1.2s infinite ease-in-out; }
.animate-wave-2 { animation: wave 0.9s infinite ease-in-out; }
.animate-wave-3 { animation: wave 1.4s infinite ease-in-out; }
.animate-wave-4 { animation: wave 0.7s infinite ease-in-out; }
.animate-wave-5 { animation: wave 1.1s infinite ease-in-out; }
/* Cấu trúc sóng âm hiển thị khi Listening */
<div className="flex flex-col items-center justify-center py-4 space-y-2">
  <div className="flex items-center gap-1 h-8">
    <span className="w-1.5 bg-red-500 rounded-full animate-wave-1 h-3"></span>
    <span className="w-1.5 bg-red-500 rounded-full animate-wave-2 h-6"></span>
    <span className="w-1.5 bg-red-400 rounded-full animate-wave-3 h-4"></span>
    <span className="w-1.5 bg-rose-500 rounded-full animate-wave-4 h-7"></span>
    <span className="w-1.5 bg-red-500 rounded-full animate-wave-5 h-2"></span>
  </div>
  <span className="text-[10px] text-red-400 font-bold tracking-widest animate-pulse">
    ĐANG LẮNG NGHE GIỌNG NÓI CỦA BẠN...
  </span>
</div>
🎯 YÊU CẦU DÀNH CHO CLAUDE AGENT:Hãy tìm kiếm component hiển thị danh sách món ăn hiện tại trong dự án này để đặt Smart Banner Card vào đầu danh sách món ăn.Thiết lập quản lý các trạng thái của Trợ lý AI ở component cha gần nhất để dễ dàng tương tác với hàm addToCart (Thêm vào giỏ hàng) hiện tại của hệ thống.Sử dụng các Icon từ thư viện lucide-react đã có sẵn.Đảm bảo giao diện responsive hoàn chỉnh trên cả giao diện điện thoại di động và máy tính bảng.