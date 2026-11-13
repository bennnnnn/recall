/**
 * Render benchmarks (`pnpm perf`, Reassure): the components project's setup and
 * mocks, run on `*.perf-test.tsx` files only. The normal suite (jest.config.js)
 * never matches them; a benchmark renders each screen eleven times and its
 * timings mean nothing outside Reassure's own Node flags.
 */
const { projects } = require("./jest.config");

const components = projects.find((project) => project.displayName === "components");

/** @type {import('jest').Config} */
module.exports = {
  ...components,
  displayName: "perf",
  testMatch: ["**/__tests__/**/*.perf-test.tsx"],
};
