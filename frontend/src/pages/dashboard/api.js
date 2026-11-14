import { emptyDashboardFixture, makeDashboardFixture } from "./mock.js";

// Chỉ dùng mock. Khi có FastAPI, thay phần thân hàm này; DashboardPage không đổi.
export async function getDashboard(fixture = "success") {
  await new Promise((resolve) => setTimeout(resolve, 350));
  if (fixture === "error") throw new Error("Không thể tải Dashboard minh họa.");
  if (fixture === "empty") return emptyDashboardFixture;
  return makeDashboardFixture();
}
