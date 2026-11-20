import { profileFixtures } from "./mock.js";

// Khi có backend tài khoản, chỉ thay hàm này bằng API thật.
export async function getProfile(fixture = "success") {
  await new Promise((resolve) => setTimeout(resolve, 350));
  if (fixture === "error") throw new Error(profileFixtures.error);
  return fixture === "empty" ? profileFixtures.empty : profileFixtures.success;
}
