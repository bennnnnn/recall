// https://docs.expo.dev/guides/using-eslint/
const { defineConfig } = require('eslint/config');
const expoConfig = require("eslint-config-expo/flat");

/**
 * Imports the UI kit replaces. Screens use the kit's component instead, so a
 * feature cannot quietly bring back its own version.
 */
const REPLACED_BY_UI_KIT = [
  {
    name: "@expo/vector-icons",
    message: "Use Icon from @/ui/icons/Icon (Lucide line icons), or BrandMark for logos.",
  },
  {
    name: "@react-native-community/datetimepicker",
    message: "Use TimePickerDialog / DatePickerDialog from @/ui/pickers.",
  },
];

/** Popups live in ui/overlay; everything else asks it for one. Tests may still spy on Alert. */
const POPUPS_OWNED_BY_UI_KIT = [
  {
    name: "react-native",
    importNames: ["Alert"],
    message: "Use confirmDialog / alertDialog from @/ui/overlay/dialogs, or a toast for a passing error.",
  },
  {
    name: "react-native",
    importNames: ["Modal"],
    message: "Use Sheet, Overlay or FullScreenModal from @/ui/overlay.",
  },
];

/** Controls the kit draws itself. ui/ may use them to build its rows. */
const CONTROLS_OWNED_BY_UI_KIT = [
  {
    name: "react-native",
    importNames: ["Switch"],
    message: "Use ListRow with switchValue from @/ui/list/ListRow; the whole row toggles.",
  },
];

const TEST_FILES = ["**/__tests__/**", "**/*.test.ts", "**/*.test.tsx"];

const UI_LEAF = {
  group: ["@/features/*", "@/components/*", "@/contexts/*", "@/hooks/*", "@/app/*"],
  message: "ui/ never imports product code. Pass data and callbacks in as props.",
};

/**
 * lib/math, lib/physics and lib/chemistry are the phone's domain and
 * render-model code: plain data in, plain data out, testable in Node. Screens
 * draw what they return; device adapters live beside their callers.
 */
const DOMAIN_LIB_NO_REACT_NATIVE = [
  {
    name: "react-native",
    message: "Domain libraries stay free of React Native. Put the UI or device part beside its caller.",
  },
];

const DOMAIN_LIB_LEAF = [
  {
    group: ["@/features/*", "@/components/*", "@/app/*", "@/hooks/*", "@/contexts/*"],
    message: "Domain libraries never import product code. Return data; the caller renders it.",
  },
  {
    group: ["expo-*"],
    message: "Domain libraries hold no device code. Put the Expo adapter beside its caller (like lib/clipboard.ts).",
  },
];

module.exports = defineConfig([
  expoConfig,
  {
    ignores: ["dist/*", "vendor/**", ".expo/**"],
  },
  {
    files: ["**/*.{ts,tsx}"],
    ignores: TEST_FILES,
    rules: {
      "no-restricted-imports": [
        "error",
        { paths: [...REPLACED_BY_UI_KIT, ...POPUPS_OWNED_BY_UI_KIT, ...CONTROLS_OWNED_BY_UI_KIT] },
      ],
      // Import cycles are caught by lib/__tests__/importCycles.test.ts, which,
      // unlike import/no-cycle, also sees type-only imports.
      "@typescript-eslint/no-explicit-any": "error",
    },
  },
  {
    files: ["lib/{math,physics,chemistry}/**/*.{ts,tsx}"],
    ignores: TEST_FILES,
    rules: {
      "no-restricted-imports": [
        "error",
        {
          paths: [...REPLACED_BY_UI_KIT, ...DOMAIN_LIB_NO_REACT_NATIVE],
          patterns: DOMAIN_LIB_LEAF,
        },
      ],
    },
  },
  {
    files: TEST_FILES,
    rules: {
      "no-restricted-imports": ["error", { paths: REPLACED_BY_UI_KIT }],
    },
  },
  {
    // The UI kit is a dependency leaf: tokens and helpers from lib/ only.
    files: ["ui/**/*.{ts,tsx}"],
    ignores: TEST_FILES,
    rules: {
      "no-restricted-imports": [
        "error",
        { paths: [...REPLACED_BY_UI_KIT, ...POPUPS_OWNED_BY_UI_KIT], patterns: [UI_LEAF] },
      ],
    },
  },
  {
    // The one place that may open a native Modal or Alert.
    files: ["ui/overlay/**/*.{ts,tsx}"],
    ignores: TEST_FILES,
    rules: {
      "no-restricted-imports": ["error", { paths: REPLACED_BY_UI_KIT, patterns: [UI_LEAF] }],
    },
  },
  {
    rules: {
      // Expo SDK 56 enables React Compiler hook rules that flag common RN patterns.
      "react-hooks/refs": "off",
      "react-hooks/set-state-in-effect": "off",
      "react-hooks/preserve-manual-memoization": "off",
      "react/no-unescaped-entities": "off",
    },
  },
  {
    // The chat turn is a reducer held outside render (code-health audit CLAR-04): chat
    // code reads refs in callbacks and effects only, never while rendering.
    files: ["features/chat/**/*.{ts,tsx}"],
    ignores: TEST_FILES,
    rules: {
      "react-hooks/refs": "error",
    },
  },
  {
    files: ["**/*.{ts,tsx}"],
    // Domain graphics (math layout, diagrams, plots) and the type scale itself
    // keep raw numbers. Everything else uses lib/type, lib/space, lib/radius and
    // the theme.
    ignores: [
      "**/__tests__/**",
      "**/*.test.ts",
      "**/*.test.tsx",
      "lib/vendor/**",
      "lib/math/**",
      "components/rich/geometry/**",
      "components/rich/FunctionGraphBlock.tsx",
      "components/rich/InteractiveFunctionPlot.tsx",
      "features/chat/components/MathDraftPreview.tsx",
      "lib/graphic.ts",
      // Vega specs for the chart WebView: a pie slice's label is Vega text, not React Native.
      "lib/chartPresentation.ts",
      "lib/type.ts",
    ],
    rules: {
      "no-restricted-syntax": [
        "error",
        {
          selector: "Property[key.name='fontSize'][value.raw=/^\\d/]",
          message:
            "Use a Type role from lib/type.ts. Raw font sizes belong in that file, or in domain graphics.",
        },
        {
          selector: "Property[key.name='fontWeight']",
          message:
            "Use Weight from lib/type.ts (`...Weight.bold`). It switches to the matching Source Sans file; a bare fontWeight draws fake bold on Android.",
        },
        {
          selector:
            "Property[key.name=/^(padding|margin|gap|paddingHorizontal|paddingVertical|marginHorizontal|marginVertical|paddingTop|paddingBottom|paddingLeft|paddingRight|marginTop|marginBottom|marginLeft|marginRight|rowGap|columnGap)$/][value.raw=/^(?!0$|1$|2$)\\d*\\.?\\d+$/]",
          message: "Use a Space token from lib/space.ts. 0, 1, and 2 may stay raw.",
        },
        {
          selector:
            "Property[key.name=/^(borderRadius|borderTopLeftRadius|borderTopRightRadius|borderBottomLeftRadius|borderBottomRightRadius|borderTopStartRadius|borderTopEndRadius|borderBottomStartRadius|borderBottomEndRadius)$/][value.raw=/^(?!0$|1$|2$)\\d*\\.?\\d+$/]",
          message: "Use a Radius token from lib/radius.ts. 0, 1, and 2 may stay raw.",
        },
        {
          selector:
            "Property[key.name=/^(color|backgroundColor|borderColor|shadowColor|tintColor)$/][value.raw=/^['\"]#/]",
          message: "Use a theme color. Neutral shadow ink is SHADOW_COLOR in lib/shadow.ts.",
        },
      ],
    },
  },
]);
