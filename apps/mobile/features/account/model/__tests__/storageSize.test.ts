import en from "@/lib/i18n/en.json";
import fr from "@/lib/i18n/fr.json";
import { storageUsedOfTotal } from "@/features/account/model/storageSize";

function translator(bundle: Record<string, string>) {
  return (key: string, options?: Record<string, unknown>) =>
    (bundle[key] ?? key).replace(/\{\{(\w+)\}\}/g, (_, name: string) => String(options?.[name]));
}

const MB = 1024 ** 2;
const GB = 1024 ** 3;
const t = translator(en);

it.each([
  [0, "0 MB"],
  [300, "1 KB"],
  [512 * 1024, "512 KB"],
  [1.5 * MB, "1.5 MB"],
  [123.4 * MB, "123 MB"],
  [400 * MB, "400 MB"],
  [1023.6 * 1024, "1 MB"],
  [999.4 * MB, "999 MB"],
  [1020 * MB, "1 GB"],
  [1023.6 * MB, "1 GB"],
  [1.25 * GB, "1.3 GB"],
  [4 * GB, "4 GB"],
])("%d bytes read as %s", (bytes, shown) => {
  expect(storageUsedOfTotal(bytes, 4 * GB, "en", t)).toBe(`${shown} of 4 GB`);
});

it("says what is kept of the plan's total", () => {
  expect(storageUsedOfTotal(123 * MB, 400 * MB, "en", t)).toBe("123 MB of 400 MB");
  expect(storageUsedOfTotal(1.2 * GB, 4 * GB, "en", t)).toBe("1.2 GB of 4 GB");
});

it("writes the number and the unit in the app's language", () => {
  expect(storageUsedOfTotal(1.2 * GB, 4 * GB, "fr", translator(fr))).toBe("1,2 Go sur 4 Go");
});
