/** @type {import('jest').Config} */
module.exports = {
  testMatch: ["**/lib/__tests__/**/*.test.ts"],
  preset: "ts-jest",
  testEnvironment: "node",
  moduleNameMapper: {
    "^@/(.*)$": "<rootDir>/$1",
  },
  globals: {
    "ts-jest": {
      tsconfig: {
        types: ["jest"],
        paths: { "@/*": ["./*"] },
      },
    },
  },
};
