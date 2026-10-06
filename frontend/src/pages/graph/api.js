import { emptyGraphFixture, graphFixture } from "./mock.js";

// Thay phần thân bằng FastAPI khi backend có endpoint đọc graph giới hạn hai hop.
// Backend vẫn phải tự kiểm giới hạn; không tin tham số từ frontend.
export async function getGraph(fixture = "success") {
  await new Promise((resolve) => setTimeout(resolve, 350));
  if (fixture === "error") throw new Error("Không thể tải đồ thị minh họa.");
  return fixture === "empty" ? emptyGraphFixture : graphFixture;
}
