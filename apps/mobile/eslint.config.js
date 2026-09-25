// https://docs.expo.dev/guides/using-eslint/
const { defineConfig } = require('eslint/config');
const expoConfig = require("eslint-config-expo/flat");

module.exports = defineConfig([
  expoConfig,
  {
    ignores: ["dist/*", "vendor/**", ".expo/**"],
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
    files: ["**/*.{ts,tsx}"],
    ignores: [
      "**/__tests__/**",
      "**/*.test.ts",
      "**/*.test.tsx",
      "lib/type.ts",
      "lib/vendor/**",
      "lib/math/**",
      "components/CodeBlock.tsx",
      "components/rich/MathText.tsx",
      "components/rich/AnswerBlock.tsx",
      "components/rich/CircularClockBlock.tsx",
      "components/rich/InteractiveFunctionPlot.tsx",
      "components/rich/InequalityGraphChart.tsx",
      "components/rich/FunctionGraphBlock.tsx",
      "components/rich/GeometryBlock.tsx",
      "components/rich/geometry/**",
      "components/rich/NumberLineChart.tsx",
      "components/rich/CartesianAxes.tsx",
      "components/rich/SimulationBlock.tsx",
      "components/rich/Molecule3DBlock.tsx",
      "components/rich/MoleculeCard.tsx",
      "components/rich/ChemistryBlock.tsx",
      "components/rich/ChartBlock.tsx",
      "components/rich/MermaidBlock.tsx",
      "components/chat/MathKeyboardBar.tsx",
      "components/chat/MathConverterUnitSheet.tsx",
      "components/chat/MathConverterPad.tsx",
      "components/chat/MathDraftPreview.tsx",
      "features/learning/screens/LessonPlayScreen.tsx",
    ],
    rules: {
      "no-restricted-syntax": [
        "error",
        {
          selector: "Property[key.name='fontSize'][value.raw=/^\\d/]",
          message:
            "Use a Type role from lib/type.ts. Raw font sizes belong in that file, or in domain graphics.",
        },
      ],
    },
  },
]);
