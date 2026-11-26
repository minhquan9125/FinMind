// Dữ liệu mock cho linh vật. Khi có backend thì chỉ cần thay hàm askMascot().
import { describeMarket, describeTime } from "./timeTalk";

export const MASCOT_TIPS = [
  "Xin chào! Mình là Fin 🤖 — trợ lý nhỏ của FinMind!",
  "Thử gõ một mã cổ phiếu ở trang Tìm kiếm xem nào 🔍",
  "Thêm mã vào Watchlist, mình sẽ để mắt giúp bạn 👀",
  "Đồ thị tri thức có nhiều mối liên hệ thú vị lắm đó 🕸️",
  "Bấm vào mình thử xem, mình biết nhảy đấy! 🕺",
  "Cuộn chậm thôi, mình chóng mặt quá 😵‍💫",
  "Có câu hỏi gì cứ bấm “Hỏi mình nhé” bên dưới!",
];

// Câu thoại theo tình huống (chọc, ngủ, bị nhấc lên...)
export const MASCOT_LINES = {
  wake: ["Ơ! Mình đâu có ngủ đâu 😳", "Á! Giật cả mình 🙀", "Hả? Có ai gọi mình hả? 🥱", "5 phút nữa thôi mà... 😴"],
  wakeSelf: ["Ngủ ngon ghê 😌 Tiếp tục khám phá nào!", "Sạc pin xong rồi ⚡"],
  dizzy: ["Đừng chọc nữa mà 😵‍💫", "Chóng mặt quá... mình chạy đây! 🏃", "Hứ, giận rồi đó 😤"],
  drag: ["Á á, thả mình xuống! 😱", "Wiii~ bay nè 🚀", "Cao quá đi mất 🫣"],
  drop: ["Hú hồn 😮‍💨", "Tiếp đất an toàn ✨", "Lần sau nhẹ tay thôi nha 🥺"],
  startled: ["Á! Giật cả mình 😠", "Đang ngủ mà chọc gì chứ! 😤", "Hứ! Mình đi chỗ khác ngủ 💢"],
  chase: ["Tới liền, tới liền! 🏃", "Đợi mình với~ 💨", "Bé tới đây! 🐾"],
  arrive: ["Bé đây nè! 🥰", "Gọi mình có việc gì thế? ✨", "Tới rồi nè 👋"],
};

export const MASCOT_GREETING =
  "Chào bạn! Mình có thể chỉ đường quanh FinMind. Bạn muốn tìm gì nào?";

const RULES = [
  // Câu hỏi về thời gian / giờ giao dịch (trả lời theo giờ thực)
  { match: /mấy giờ|giờ rồi|bây giờ là|thời gian/i, reply: describeTime },
  { match: /mở cửa|đóng cửa|giờ giao dịch|phiên|thị trường/i, reply: describeMarket },
  { match: /(xin )?chào|hello|\bhi\b/i, reply: "Chào bạn nha 👋 Hôm nay bạn muốn xem mã nào?" },
  { match: /cổ phiếu|mã|giá|chứng khoán/i, reply: "Bạn vào trang Tìm kiếm, gõ mã (VD: FPT, VNM) để xem tin tức và phân tích nhé 📈" },
  { match: /watchlist|theo dõi|yêu thích/i, reply: "Ở trang Watchlist, bấm ⭐ để lưu mã. Mình sẽ gom tin mới nhất cho bạn!" },
  { match: /tin|news|tức/i, reply: "Tin tức được cập nhật liên tục và gắn với từng mã cổ phiếu, xem ở Dashboard nhé 📰" },
  { match: /đồ thị|graph|quan hệ/i, reply: "Trang Đồ thị cho thấy công ty, ngành và sự kiện liên kết với nhau thế nào 🕸️" },
  { match: /tải|upload|tài liệu|pdf/i, reply: "Bạn có thể tải tài liệu lên ở trang Upload, hệ thống sẽ tự trích xuất nội dung 📄" },
  { match: /cảm ơn|thanks|thank/i, reply: "Không có gì đâu! Cần gì cứ gọi mình nha 💚" },
];

const FALLBACK =
  "Câu này hơi khó với mình 😅 (đang là bản demo). Bạn thử hỏi về cổ phiếu, watchlist hoặc tin tức nhé!";

/** Giả lập gọi API: trả về câu trả lời sau 500–900ms. */
export function askMascot(question) {
  const rule = RULES.find((r) => r.match.test(question));
  const delay = 500 + Math.random() * 400;
  const answer = () => {
    if (!rule) return FALLBACK;
    return typeof rule.reply === "function" ? rule.reply() : rule.reply;
  };
  return new Promise((resolve) => setTimeout(() => resolve(answer()), delay));
}
