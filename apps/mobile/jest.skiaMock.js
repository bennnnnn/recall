/**
 * Jest mock for @shopify/react-native-skia. The shipped jestSetup targets the
 * commonjs build, but our resolver loads lib/module (ESM) — so map the module
 * here instead. Canvas renders its children; paint components are null; the
 * Skia path API is a minimal chainable stub. Tests can still override with
 * jest.doMock (e.g. skiaAvailability probes).
 */
const React = require("react");
const { View } = require("react-native");

const makePath = () => ({
  moveTo: () => undefined,
  lineTo: () => undefined,
  addCircle: () => undefined,
  close: () => undefined,
});

const Canvas = ({ children, ...rest }) => React.createElement(View, rest, children);
const Group = ({ children }) => (children ?? null);
const Null = () => null;

module.exports = {
  __esModule: true,
  Canvas,
  Group,
  Path: Null,
  Circle: Null,
  RoundedRect: Null,
  DashPathEffect: Null,
  Text: Null,
  Skia: {
    Path: { Make: makePath },
    XYWHRect: (x, y, width, height) => ({ x, y, width, height }),
  },
  useFont: () => null,
};
