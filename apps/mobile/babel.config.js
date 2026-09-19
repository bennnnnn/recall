module.exports = function (api) {
  // Re-evaluate when NODE_ENV flips so the test env gets its extra plugin.
  api.cache.using(() => process.env.NODE_ENV);
  const plugins = ['react-native-reanimated/plugin'];
  if (process.env.NODE_ENV === 'test') {
    // Jest (CJS) cannot execute native import(); Metro handles it in app
    // builds, so only lower it away for tests.
    plugins.push('@babel/plugin-transform-dynamic-import');
  }
  return {
    presets: ['babel-preset-expo'],
    plugins,
  };
};
