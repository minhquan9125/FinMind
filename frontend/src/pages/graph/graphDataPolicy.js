// Confirmed legacy Alpha/Beta seed graphs returned by the shared backend.
// Keep them out of the user workspace without deleting the team's DB records.
const seedVersions = new Set(["wbs08-smoke-20261030", "wbs08-smoke-20261030b"]);

export const isSeedGraphVersion = version => seedVersions.has(version);
