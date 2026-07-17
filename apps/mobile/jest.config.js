// Package-name prefixes that ship untranspiled source and must be run through
// Babel instead of being treated as pre-built node_modules content. Used to
// build transformIgnorePatterns for both possible on-disk layouts below.
const RN_TRANSFORM_ALLOWLIST =
  "(?:(?:jest-)?react-native|@react-native(?:-community)?|@react-native-google-signin|" +
  "@react-native-masked-view|expo(?:nent)?|@expo(?:nent)?|@expo-google-fonts|" +
  "react-navigation|@react-navigation|@sentry|native-base|react-native-svg|" +
  "@gorhom)";

/** @type {import('jest').Config} */
module.exports = {
  projects: [
    {
      displayName: "lib",
      // Pure-function unit tests on lib/ modules — no rendering, no RN runtime.
      // Covers lib/__tests__ AND nested ones like lib/vendor/__tests__ (the
      // vendored-asset integrity checks live there; without the second pattern
      // they were silently never discovered/run).
      testMatch: [
        "**/lib/__tests__/**/*.test.ts",
        "**/lib/**/__tests__/**/*.test.ts",
      ],
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
      //
      // pnpm's default (non-hoisted) store nests every package under
      // node_modules/.pnpm/<encoded-name>@<version>/node_modules/<real-path>,
      // so a single "node_modules/(?!ALLOWLIST)" pattern never reaches the
      // real package name — it matches (and wrongly ignores) right after the
      // *first* node_modules/, since ".pnpm/..." itself doesn't start with
      // an allow-listed name. A second pattern anchored on the literal
      // ".pnpm/" segment checks the allowlist against pnpm's encoded folder
      // name directly (scoped packages keep their "@scope" prefix verbatim,
      // e.g. "@react-native+jest-preset@...", just with "+" instead of "/").
      transformIgnorePatterns: [
        // Hoisted-style layout — excludes .pnpm/ so it defers to the pattern
        // below for that segment instead of wrongly matching "ignore" at the
        // first node_modules/ (.pnpm never itself starts with an allowed name).
        `node_modules/(?!\\.pnpm)(?!${RN_TRANSFORM_ALLOWLIST})`,
        `node_modules/\\.pnpm/(?!${RN_TRANSFORM_ALLOWLIST})`,
      ],
    },
  ],
};
