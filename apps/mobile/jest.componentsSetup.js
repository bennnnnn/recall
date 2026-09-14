const { jest: jestGlobals } = require("@jest/globals");

/**
 * AppSheet (and other chrome) import RNGH + Reanimated. The RN jest env has
 * neither native module, so mock them before any component test file loads.
 */
jestGlobals.mock("react-native-reanimated", () => {
  const React = require("react");
  const { View: RNView } = require("react-native");
  const id = (value) => value;
  /**
   * Spread `animatedProps` onto the wrapped component instead of dropping it.
   * Paired with the synchronous `useAnimatedProps` below, the worklet's derived
   * values arrive as ordinary props, so a test can assert an animated SVG
   * element's geometry the same way it asserts a static one.
   */
  const createAnimatedComponent = (Component) => {
    const Animated = ({ animatedProps, ...rest }) =>
      React.createElement(Component, { ...rest, ...(animatedProps ?? {}) });
    Animated.displayName = `Animated(${Component.displayName ?? Component.name ?? "Component"})`;
    return Animated;
  };
  const layoutAnim = () => {
    const api = {};
    api.duration = () => api;
    api.easing = () => api;
    api.delay = () => api;
    api.springify = () => api;
    api.damping = () => api;
    api.stiffness = () => api;
    return api;
  };
  return {
    __esModule: true,
    default: { View: RNView, createAnimatedComponent },
    createAnimatedComponent,
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
    runOnUI: (fn) => (...args) => fn(...args),
    useAnimatedStyle: (factory) => (typeof factory === "function" ? factory() : {}),
    useAnimatedProps: (factory) => (typeof factory === "function" ? factory() : {}),
    useAnimatedReaction: () => undefined,
    useSharedValue: (value) => ({ value }),
    withSpring: id,
    withTiming: id,
    withRepeat: id,
    withSequence: id,
    withDelay: id,
    cancelAnimation: jestGlobals.fn(),
    SlideInRight: layoutAnim(),
    SlideOutLeft: layoutAnim(),
    SlideOutDown: layoutAnim(),
  };
});

jestGlobals.mock("react-native-gesture-handler", () => {
  const { View: RNView, Pressable: RNPressable } = require("react-native");
  const chain = () => {
    const api = new Proxy(
      {},
      {
        get: (_target, prop) => {
          if (prop === "then") return undefined;
          return () => api;
        },
      },
    );
    return api;
  };
  return {
    Gesture: {
      Pan: () => chain(),
      Pinch: () => chain(),
      Tap: () => chain(),
      Simultaneous: () => chain(),
      Exclusive: () => chain(),
    },
    GestureDetector: ({ children }) => children,
    GestureHandlerRootView: RNView,
    Pressable: RNPressable,
    ScrollView: require("react-native").ScrollView,
    Swipeable: RNView,
  };
});

jestGlobals.mock("@expo/vector-icons", () => ({
  Ionicons: "Ionicons",
}));
