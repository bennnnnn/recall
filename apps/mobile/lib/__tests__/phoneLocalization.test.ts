import { productionFiles } from "./support/ratchet";
import { readSource } from "./support/sourceFiles";

type Loaded = {
  deviceLanguage: () => string;
  readPhoneClock: () => { weekStart?: number; hourCycle: string };
  onPhoneClockChange: (listener: () => void) => () => void;
};

/** Fresh copies of both readers on a phone whose native module is `native`. */
function loadOn(native: object | null): Loaded {
  let loaded: Loaded | undefined;
  jest.isolateModules(() => {
    jest.doMock("expo-modules-core", () => ({ requireOptionalNativeModule: () => native }));
    /* eslint-disable @typescript-eslint/no-require-imports -- fresh copies per phone */
    const { deviceLanguage } = require("@/lib/i18n/deviceLanguage") as typeof import("@/lib/i18n/deviceLanguage");
    const clock = require("@/lib/datetime/phoneClock") as typeof import("@/lib/datetime/phoneClock");
    /* eslint-enable @typescript-eslint/no-require-imports */
    // The loader is lazy: load it here, while the mock is this phone's. Both readers share it.
    deviceLanguage();
    loaded = { deviceLanguage, readPhoneClock: clock.readPhoneClock, onPhoneClockChange: clock.onPhoneClockChange };
  });
  jest.dontMock("expo-modules-core");
  if (!loaded) throw new Error("not loaded");
  return loaded;
}

afterEach(() => jest.restoreAllMocks());

it("reads expo-localization's native module in one file", () => {
  // The phone's languages and its clock once had a loader each, failing differently.
  const readers = productionFiles().filter((file) => readSource(file).includes('"ExpoLocalization"'));
  expect(readers.map((file) => file.replace(/^.*\/apps\/mobile\//, ""))).toEqual(["lib/phoneLocalization.ts"]);
});

it("gives both readers the module", () => {
  const remove = jest.fn();
  const phone = loadOn({
    getLocales: () => [{ languageCode: "fr", languageTag: "fr-FR" }],
    getCalendars: () => [{ firstWeekday: 2, uses24hourClock: true }],
    addListener: () => ({ remove }),
  });
  expect(phone.deviceLanguage()).toBe("fr");
  expect(phone.readPhoneClock()).toMatchObject({ weekStart: 1, hourCycle: "h23" });
  phone.onPhoneClockChange(() => {})();
  expect(remove).toHaveBeenCalledTimes(1);
});

it("falls back the same way for both when a read fails, and says so once", () => {
  const warn = jest.spyOn(console, "warn").mockImplementation(() => {});
  const broken = () => {
    throw new Error("native read failed");
  };
  const phone = loadOn({ getLocales: broken, getCalendars: broken, addListener: broken });
  expect(phone.deviceLanguage()).toBe("en");
  expect(phone.readPhoneClock().weekStart).toBeUndefined();
  expect(() => phone.onPhoneClockChange(() => {})()).not.toThrow();
  expect(warn).toHaveBeenCalledTimes(1);
});

it("reads nothing, quietly, on a build without the module", () => {
  const warn = jest.spyOn(console, "warn").mockImplementation(() => {});
  const phone = loadOn(null);
  expect(phone.deviceLanguage()).toBe("en");
  expect(phone.readPhoneClock().weekStart).toBeUndefined();
  expect(warn).not.toHaveBeenCalled();
});
