/** @type {import('jest').Config} */
module.exports = {
  projects: [
    {
      displayName: "lib",
      // Pure-function unit tests on lib/ modules — no rendering, no RN runtime.
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
    },
    {
      displayName: "components",
      // Component/hook rendering tests. Kept out of the "lib" project above
      // because they need the React Native jest preset (native module +
      // Babel/JSX transform) instead of ts-jest's plain Node environment.
      // Convention: colocate under a top-level `__tests__/` folder per
      // directory (e.g. components/__tests__/, hooks/__tests__/), mirroring
      // how lib/__tests__ already centralizes lib's tests, and use the
      // `.test.tsx` extension so these never collide with the "lib"
      // project's `.test.ts` matcher above.
      testMatch: ["**/__tests__/**/*.test.tsx"],
      preset: "@react-native/jest-preset",
      moduleFileExtensions: ["ts", "tsx", "js", "jsx", "json"],
      moduleNameMapper: {
        "^@/(.*)$": "<rootDir>/$1",
      },
      // react-native's own preset only allow-lists react-native packages for
      // transform; Expo packages (expo, @expo/*, expo-*) ship untranspiled
      // source too, so they need to be added or Jest's default
      // transformIgnorePatterns will skip them and fail on import.
      transformIgnorePatterns: [
        "node_modules/(?!((jest-)?react-native|@react-native(-community)?)|expo(nent)?|@expo(nent)?/.*|@expo-google-fonts/.*|react-navigation|@react-navigation/.*|@sentry/react-native|native-base|react-native-svg)",
      ],
    },
  ],
};
