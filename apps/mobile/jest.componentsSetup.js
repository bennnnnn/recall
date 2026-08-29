/**
 * AppSheet (and other chrome) import RNGH + Reanimated. The RN jest env has
 * neither native module, so mock them before any component test file loads.
 */
jest.mock("react-native-reanimated", () => {
  const { View: RNView } = require("react-native");
  const id = (value) => value;
  return {
    __esModule: true,
    default: { View: RNView },
    Easing: {
      linear: id,
      ease: id,
      sin: id,
      cubic: id,
      inOut: () => id,
      out: () => id,
      in: () => id,
    },
    runOnJS: (fn) => fn,
    useAnimatedStyle: (factory) => (typeof factory === "function" ? factory() : {}),
    useSharedValue: (value) => ({ value }),
    withSpring: id,
    withTiming: id,
    withRepeat: id,
    cancelAnimation: jest.fn(),
  };
});

jest.mock("react-native-gesture-handler", () => {
  const { View: RNView } = require("react-native");
  const chain = () => {
    const api = {};
    api.enabled = () => api;
    api.activeOffsetY = () => api;
    api.failOffsetX = () => api;
    api.onUpdate = () => api;
    api.onEnd = () => api;
    return api;
  };
  return {
    Gesture: { Pan: () => chain() },
    GestureDetector: ({ children }) => children,
    GestureHandlerRootView: RNView,
    ScrollView: require("react-native").ScrollView,
    Swipeable: RNView,
  };
});
