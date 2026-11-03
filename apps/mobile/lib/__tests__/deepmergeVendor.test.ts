/**
 * vendor/deepmerge is 4.3.1 with GHSA-gcqx-w48m-w2h4 fixed (upstream has no patched release):
 * a source key `__proto__` must stay a plain key, never the merged object's prototype, and its
 * two callers (@expo/config, jest-config; the package.json override hands them this copy) must
 * merge as they did before.
 */

type Deepmerge = ((target: object, source: object, options?: object) => Record<string, unknown>) & {
  all: (objects: object[]) => Record<string, unknown>;
};

const deepmerge = jest.requireActual<Deepmerge>("../../vendor/deepmerge");

it("keeps a source's __proto__ key a plain key, off the merged object's prototype", () => {
  const source = JSON.parse('{"__proto__": {"polluted": true}, "a": {"b": 1}}');
  const merged = deepmerge(Object.create(null), source);
  expect(merged.polluted).toBeUndefined();
  expect(Object.getPrototypeOf(merged)).toBe(Object.prototype);
  expect(Object.prototype.hasOwnProperty.call(merged, "__proto__")).toBe(true);
  expect(merged.a).toEqual({ b: 1 });
});

it("merges objects, arrays and lists as 4.3.1 did", () => {
  expect(deepmerge({ a: { x: 1 }, list: [1] }, { a: { y: 2 }, list: [2] })).toEqual({
    a: { x: 1, y: 2 },
    list: [1, 2],
  });
  expect(deepmerge.all([{ a: 1 }, { b: 2 }, { a: 3 }])).toEqual({ a: 3, b: 2 });
});
