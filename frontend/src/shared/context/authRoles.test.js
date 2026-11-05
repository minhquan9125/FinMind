import test from "node:test";
import assert from "node:assert/strict";
import { primaryRole, normalizeAuthUser } from "./authRoles.js";

test("canonical admin grant is recognized in any role position", () => {
  assert.equal(primaryRole(["RESEARCHER", "ADMINISTRATOR"]), "admin");
  assert.equal(primaryRole(["ADMINISTRATOR", "RESEARCHER"]), "admin");
  assert.equal(primaryRole(["RESEARCHER"]), "user");
  assert.equal(primaryRole(null), "user");
});

test("restored UI role derives from role list and preserves user profile", () => {
  assert.deepEqual(normalizeAuthUser({ name: "User", role: "user", roles: ["ADMINISTRATOR"] }),
    { name: "User", role: "admin", roles: ["ADMINISTRATOR"] });
  assert.equal(normalizeAuthUser({ role: "admin", roles: ["RESEARCHER"] }).role, "user");
});
