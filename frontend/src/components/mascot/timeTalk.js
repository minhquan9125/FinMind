// Greetings and reminders use the actual device clock.
export const finNow = () => new Date();

const pick = (list) => list[Math.floor(Math.random() * list.length)];
const minutesOf = (d) => d.getHours() * 60 + d.getMinutes();
const isWeekday = (d) => d.getDay() >= 1 && d.getDay() <= 5;
export const hhmm = (d = finNow()) =>
  `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;

/* ---------------- buổi trong ngày ---------------- */

export function getPeriod(d = finNow()) {
  const h = d.getHours();
  if (h >= 5 && h < 10) return "morning";
  if (h >= 10 && h < 13) return "noon";
  if (h >= 13 && h < 18) return "afternoon";
  if (h >= 18 && h < 22) return "evening";
  return "night";
}

export const isNight = (d = finNow()) => getPeriod(d) === "night";

const GREETINGS = {
  morning: ["Chào buổi sáng! ☀️ Mình là Fin, cùng xem thị trường hôm nay nhé!", "Sáng rồi nè ☀️ Fin chào bạn một ngày đầu tư suôn sẻ!"],
  noon: ["Chào buổi trưa! 🍱 Mình là Fin đây!", "Trưa rồi nè 🌞 Fin chào bạn!"],
  afternoon: ["Chào buổi chiều! 🌤️ Fin sẵn sàng giúp bạn nè!", "Chiều rồi, cố lên nào! 💪 Mình là Fin!"],
  evening: ["Chào buổi tối! 🌙 Mình là Fin, tối nay nghiên cứu gì đây?", "Tối rồi nè 🌙 Fin chào bạn!"],
  night: ["Khuya rồi mà vẫn chăm chỉ ghê 🦉 Mình là Fin!", "Ơ, giờ này còn thức hả? 🌙 Fin chào cú đêm!"],
};

const PERIOD_TIPS = {
  morning: ["Uống cà phê chưa? ☕ Rồi mình cùng xem tin sáng nay nhé", "Buổi sáng là lúc đọc tin tức đầu ngày đó 📰"],
  noon: ["Trưa rồi, nhớ ăn cơm đúng giờ nha 🍚", "Ăn trưa xong làm ly trà cho tỉnh táo nè 🍵"],
  afternoon: ["Buồn ngủ chiều hả? Đứng dậy đi lại chút nha 🚶", "Chiều nay xem thử báo cáo tài chính một doanh nghiệp nhé 📑"],
  evening: ["Tối rồi, đọc báo cáo thường niên thư giãn chút không? 📖", "Buổi tối thích hợp để tổng kết danh mục đó 🗂️"],
  night: ["Khuya rồi đó, đi ngủ sớm mai còn xem bảng điện nha 😴", "Mình buồn ngủ quá... bạn chưa mỏi mắt hả? 🥱", "Thức khuya hại sức khoẻ lắm đó 🌙"],
};

const PERIOD_COMMENT = {
  morning: "— buổi sáng năng lượng nè ☀️",
  noon: "— trưa rồi, nhớ ăn cơm nha 🍱",
  afternoon: "— buổi chiều rồi đó 🌤️",
  evening: "— tối rồi 🌙",
  night: "— khuya lắm rồi đó, đi ngủ sớm nha 😴",
};

/* ---------------- giờ giao dịch HOSE ---------------- */

export function getMarketStatus(d = finNow()) {
  if (!isWeekday(d)) return { key: "weekend", label: "cuối tuần, thị trường nghỉ" };
  const m = minutesOf(d);
  if (m < 9 * 60) return { key: "pre", label: "chưa tới giờ mở cửa (9:00)" };
  if (m < 9 * 60 + 15) return { key: "ato", label: "đang phiên ATO" };
  if (m < 11 * 60 + 30) return { key: "open", label: "đang giao dịch phiên sáng" };
  if (m < 13 * 60) return { key: "lunch", label: "đang nghỉ trưa, 13:00 mở lại" };
  if (m < 14 * 60 + 30) return { key: "open", label: "đang giao dịch phiên chiều" };
  if (m < 14 * 60 + 45) return { key: "atc", label: "đang phiên ATC" };
  return { key: "closed", label: "đã đóng cửa" };
}

const MARKET_TIPS = {
  weekend: ["Cuối tuần thị trường nghỉ, tranh thủ nghiên cứu doanh nghiệp nhé 🏖️"],
  pre: ["Sắp tới giờ mở cửa rồi, xem tin trước phiên nhé 🔔"],
  ato: ["Đang phiên ATO, giá mở cửa sắp có rồi 🔔"],
  open: ["Thị trường đang giao dịch đó 📈 Xem nhanh VN-Index nhé!", "Bảng điện đang nhảy số kìa 📊"],
  lunch: ["Thị trường nghỉ trưa rồi, bạn đi ăn trưa chưa? 🍜"],
  atc: ["15 phút ATC cuối phiên, hồi hộp ghê ⏳"],
  closed: ["Phiên hôm nay đã đóng cửa, xem tổng kết cuối ngày nhé 📊"],
};

/* ---------------- API cho widget ---------------- */

export const getGreeting = () => pick(GREETINGS[getPeriod()]);

/** Một câu gợi ý hợp với giờ hiện tại (buổi trong ngày hoặc tình trạng thị trường). */
export function getTimelyTip() {
  const d = finNow();
  const pool = [...PERIOD_TIPS[getPeriod(d)]];
  const market = getMarketStatus(d).key;
  if (market !== "closed" || getPeriod(d) === "afternoon") pool.push(...MARKET_TIPS[market]);
  return pick(pool);
}

export const describeTime = () => `Bây giờ là ${hhmm()} ${PERIOD_COMMENT[getPeriod()]}`;
export const describeMarket = () => `Thị trường ${getMarketStatus().label} 📈 (giờ HOSE, chưa tính ngày lễ)`;

// Nhắc đúng giờ (cửa sổ 3 phút, mỗi ngày nhắc 1 lần)
const REMINDERS = [
  { id: "pre-open", at: "08:55", weekdayOnly: true, text: "5 phút nữa thị trường mở cửa! 🔔" },
  { id: "ato", at: "09:00", weekdayOnly: true, text: "Phiên ATO bắt đầu rồi! 🔔" },
  { id: "lunch-break", at: "11:30", weekdayOnly: true, text: "Thị trường nghỉ trưa tới 13h rồi, đi ăn thôi 🍱" },
  { id: "noon", at: "12:00", text: "12 giờ trưa rồi, ăn cơm thôi! 🍚" },
  { id: "afternoon", at: "13:00", weekdayOnly: true, text: "Phiên chiều bắt đầu rồi nè 📈" },
  { id: "atc", at: "14:30", weekdayOnly: true, text: "Vào phiên ATC rồi, 15 phút cuối nhé ⏳" },
  { id: "close", at: "14:45", weekdayOnly: true, text: "Hết giờ khớp lệnh rồi! Xem tổng kết phiên nhé 📊" },
  { id: "22h", at: "22:00", text: "10 giờ tối rồi, khuya rồi đó! Nghỉ sớm mai còn xem bảng điện nha 🌙" },
  { id: "23h", at: "23:00", text: "11 giờ khuya rồi... đi ngủ đi mà 😴" },
  { id: "midnight", at: "00:00", text: "Nửa đêm rồi đó! Cú đêm chính hiệu 🦉" },
];

// Nhắc theo thời gian ngồi trên trang
const SESSION_REMINDERS = [
  { id: "eyes", afterMin: 20, text: "Bạn ngồi 20 phút rồi, nhìn ra xa một chút cho đỡ mỏi mắt nhé 👀" },
  { id: "water", afterMin: 45, text: "Uống miếng nước đi nè 💧" },
  { id: "stretch", afterMin: 90, text: "Hơn tiếng rưỡi rồi đó, đứng dậy vươn vai chút nha 🙆" },
];

/** Trả về câu nhắc đến hạn (và đánh dấu đã nhắc), không có thì null. */
export function dueReminder(fired, sessionStartMs) {
  const d = finNow();
  const m = minutesOf(d);
  const day = d.toDateString();

  for (const r of REMINDERS) {
    if (r.weekdayOnly && !isWeekday(d)) continue;
    const [h, mm] = r.at.split(":").map(Number);
    const at = h * 60 + mm;
    const key = `${day}|${r.id}`;
    if (m >= at && m < at + 3 && !fired.has(key)) {
      fired.add(key);
      return r.text;
    }
  }

  const elapsedMin = (Date.now() - sessionStartMs) / 60000;
  for (const r of SESSION_REMINDERS) {
    if (elapsedMin >= r.afterMin && !fired.has(r.id)) {
      fired.add(r.id);
      return r.text;
    }
  }
  return null;
}
