import { profileFixtures } from "./mock.js";

// The real profile is the signed-in account from AuthContext; fixtures remain only for ?fixture= previews.
export async function getProfile(fixture = "success", account = null) {
  await new Promise((resolve) => setTimeout(resolve, 350));
  if (fixture === "error") throw new Error(profileFixtures.error);
  if (fixture === "empty") return profileFixtures.empty;
  return account || profileFixtures.success;
}
