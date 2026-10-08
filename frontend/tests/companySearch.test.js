import test from "node:test";
import assert from "node:assert/strict";
import { companyPlaceholder, searchCompanies } from "../src/pages/companies/companySearch.js";

test("new symbol is searchable without inventing financials", () => {
  const result = searchCompanies([], " ctr ");
  assert.equal(result[0].id, "CTR");
  assert.deepEqual(result[0].financials, []);
  assert.deepEqual(result[0].reports, []);
});
test("known metadata wins and unsafe symbols are rejected", () => {
  const fpt = { id: "FPT", name: "Công nghệ FPT", sector: "Công nghệ" };
  assert.deepEqual(searchCompanies([fpt], "fpt"), [fpt]);
  assert.deepEqual(searchCompanies([fpt], "cong nghe"), [fpt]);
  for (const value of ["../CTR", "AB", "ABCD", "<X>"]) assert.equal(companyPlaceholder(value), null);
});
