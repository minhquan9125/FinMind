import { catalogFixtures } from "./mock.js";

// Sau này chỉ thay phần thân hàm này bằng fetch tới FastAPI; UI giữ nguyên.
export async function getCompanies(fixture = "success") {
  await new Promise((resolve) => setTimeout(resolve, 350));
  if (fixture === "error") throw new Error(catalogFixtures.error);
  return catalogFixtures[fixture] ?? catalogFixtures.success;
}
