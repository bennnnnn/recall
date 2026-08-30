export const UNIT_CATEGORIES = [
  "length",
  "area",
  "volume",
  "mass",
  "temperature",
  "time",
  "speed",
  "energy",
  "pressure",
  "force",
  "angle",
] as const;

export type UnitCategory = (typeof UNIT_CATEGORIES)[number];

export type UnitDef = {
  id: string;
  symbol: string;
  name: string;
  /** Single token the model reads in `convert 5 {prompt} to {prompt}`. */
  prompt: string;
  category: UnitCategory;
  /** Multiply to reach the category SI base. Unused for temperature. */
  toSi: number;
};

function u(
  id: string,
  symbol: string,
  name: string,
  prompt: string,
  category: UnitCategory,
  toSi: number,
): UnitDef {
  return { id, symbol, name, prompt, category, toSi };
}

export const UNITS_BY_CATEGORY: Record<UnitCategory, readonly UnitDef[]> = {
  length: [
    u("mm", "mm", "Millimeter", "mm", "length", 0.001),
    u("cm", "cm", "Centimeter", "cm", "length", 0.01),
    u("m", "m", "Meter", "m", "length", 1),
    u("km", "km", "Kilometer", "km", "length", 1000),
    u("in", "in", "Inch", "in", "length", 0.0254),
    u("ft", "ft", "Foot", "ft", "length", 0.3048),
    u("yd", "yd", "Yard", "yd", "length", 0.9144),
    u("mi", "mi", "Mile", "mi", "length", 1609.344),
  ],
  area: [
    u("mm2", "mm²", "Square millimeter", "mm^2", "area", 1e-6),
    u("cm2", "cm²", "Square centimeter", "cm^2", "area", 1e-4),
    u("m2", "m²", "Square meter", "m^2", "area", 1),
    u("km2", "km²", "Square kilometer", "km^2", "area", 1e6),
    u("in2", "in²", "Square inch", "in^2", "area", 0.00064516),
    u("ft2", "ft²", "Square foot", "ft^2", "area", 0.09290304),
    u("acre", "acre", "Acre", "acres", "area", 4046.8564224),
  ],
  volume: [
    u("ml", "mL", "Milliliter", "mL", "volume", 1e-6),
    u("l", "L", "Liter", "L", "volume", 0.001),
    u("m3", "m³", "Cubic meter", "m^3", "volume", 1),
    u("tsp", "tsp", "Teaspoon", "tsp", "volume", 4.92892159375e-6),
    u("tbsp", "tbsp", "Tablespoon", "tbsp", "volume", 1.478676478125e-5),
    u("cup", "cup", "Cup", "cups", "volume", 2.365882365e-4),
    u("floz", "fl oz", "Fluid ounce", "fl-oz", "volume", 2.95735295625e-5),
    u("gal", "gal", "Gallon", "gal", "volume", 0.003785411784),
  ],
  mass: [
    u("mg", "mg", "Milligram", "mg", "mass", 1e-6),
    u("g", "g", "Gram", "g", "mass", 0.001),
    u("kg", "kg", "Kilogram", "kg", "mass", 1),
    u("oz", "oz", "Ounce", "oz", "mass", 0.028349523125),
    u("lb", "lb", "Pound", "lb", "mass", 0.45359237),
  ],
  temperature: [
    u("c", "°C", "Celsius", "celsius", "temperature", 1),
    u("f", "°F", "Fahrenheit", "fahrenheit", "temperature", 1),
    u("k", "K", "Kelvin", "kelvin", "temperature", 1),
  ],
  time: [
    u("ms", "ms", "Millisecond", "ms", "time", 0.001),
    u("s", "s", "Second", "s", "time", 1),
    u("min", "min", "Minute", "min", "time", 60),
    u("hr", "hr", "Hour", "hr", "time", 3600),
  ],
  speed: [
    u("mps", "m/s", "Meter per second", "m/s", "speed", 1),
    u("kmh", "km/h", "Kilometer per hour", "km/h", "speed", 1000 / 3600),
    u("mph", "mph", "Mile per hour", "mph", "speed", 1609.344 / 3600),
    u("fps", "ft/s", "Foot per second", "ft/s", "speed", 0.3048),
    u("knot", "kn", "Knot", "knots", "speed", 1852 / 3600),
  ],
  energy: [
    u("j", "J", "Joule", "J", "energy", 1),
    u("kj", "kJ", "Kilojoule", "kJ", "energy", 1000),
    u("cal", "cal", "Calorie", "cal", "energy", 4.184),
    u("kcal", "kcal", "Kilocalorie", "kcal", "energy", 4184),
    u("wh", "Wh", "Watt-hour", "Wh", "energy", 3600),
    u("kwh", "kWh", "Kilowatt-hour", "kWh", "energy", 3.6e6),
    u("ev", "eV", "Electronvolt", "eV", "energy", 1.602176634e-19),
    u("btu", "BTU", "British thermal unit", "BTU", "energy", 1055.05585262),
  ],
  pressure: [
    u("pa", "Pa", "Pascal", "Pa", "pressure", 1),
    u("kpa", "kPa", "Kilopascal", "kPa", "pressure", 1000),
    u("atm", "atm", "Atmosphere", "atm", "pressure", 101325),
    u("bar", "bar", "Bar", "bar", "pressure", 1e5),
    u("psi", "psi", "Pound per square inch", "psi", "pressure", 6894.757293168),
    u("mmhg", "mmHg", "Millimeter of mercury", "mmHg", "pressure", 133.322387415),
  ],
  force: [
    u("n", "N", "Newton", "N", "force", 1),
    u("kn", "kN", "Kilonewton", "kN", "force", 1000),
    u("lbf", "lbf", "Pound-force", "lbf", "force", 4.4482216152605),
  ],
  angle: [
    u("deg", "°", "Degree", "degrees", "angle", Math.PI / 180),
    u("rad", "rad", "Radian", "radians", "angle", 1),
  ],
};

const UNIT_BY_ID = new Map<string, UnitDef>(
  Object.values(UNITS_BY_CATEGORY).flat().map((unit) => [unit.id, unit]),
);

export function findUnit(id: string): UnitDef | undefined {
  return UNIT_BY_ID.get(id);
}

export function defaultUnits(category: UnitCategory): { fromId: string; toId: string } {
  if (category === "length") return { fromId: "m", toId: "cm" };
  if (category === "area") return { fromId: "m2", toId: "ft2" };
  if (category === "volume") return { fromId: "l", toId: "gal" };
  if (category === "mass") return { fromId: "kg", toId: "lb" };
  if (category === "temperature") return { fromId: "c", toId: "f" };
  if (category === "speed") return { fromId: "kmh", toId: "mph" };
  if (category === "energy") return { fromId: "j", toId: "kj" };
  if (category === "pressure") return { fromId: "atm", toId: "psi" };
  if (category === "force") return { fromId: "n", toId: "lbf" };
  if (category === "angle") return { fromId: "deg", toId: "rad" };
  return { fromId: "s", toId: "min" };
}

function toKelvin(value: number, id: string): number {
  if (id === "c") return value + 273.15;
  if (id === "f") return ((value - 32) * 5) / 9 + 273.15;
  return value;
}

function fromKelvin(kelvin: number, id: string): number {
  if (id === "c") return kelvin - 273.15;
  if (id === "f") return ((kelvin - 273.15) * 9) / 5 + 32;
  return kelvin;
}

export function convertUnit(value: number, fromId: string, toId: string): number | null {
  const from = findUnit(fromId);
  const to = findUnit(toId);
  if (!from || !to || from.category !== to.category) return null;
  if (from.category === "temperature") {
    return fromKelvin(toKelvin(value, from.id), to.id);
  }
  return (value * from.toSi) / to.toSi;
}

export function formatConvertNumber(value: number): string {
  if (!Number.isFinite(value)) return "—";
  if (value === 0) return "0";
  const abs = Math.abs(value);
  if (abs >= 1e10 || (abs < 1e-6 && abs > 0)) {
    return value.toExponential(4).replace(/(\.\d*?)0+e/, "$1e").replace(/\.e/, "e");
  }
  return String(Number(value.toPrecision(8)));
}

export const CONVERTER_DEFAULT_DIGITS = "1";

export function appendConverterDigit(
  current: string,
  key: string,
  fresh = false,
): string {
  if (key === "AC") return CONVERTER_DEFAULT_DIGITS;
  if (key === "back") {
    if (current.length <= 1 || current === "-0" || (current.startsWith("-") && current.length === 2)) {
      return CONVERTER_DEFAULT_DIGITS;
    }
    return current.slice(0, -1);
  }
  if (key === "±") {
    if (current === "0" || current === "0.") return current;
    return current.startsWith("-") ? current.slice(1) : `-${current}`;
  }
  if (fresh && /^\d$/.test(key)) return key;
  if (fresh && key === ".") return "0.";
  if (key === ".") {
    if (current.includes(".")) return current;
    return `${current}.`;
  }
  if (!/^\d$/.test(key)) return current;
  if (current === "0") return key;
  if (current === "-0") return `-${key}`;
  if (current.replace("-", "").replace(".", "").length >= 12) return current;
  return current + key;
}

/** Prompt sent when the user taps Ask on the converter pad. */
export function converterAskText(digits: string, fromPrompt: string, toPrompt: string): string {
  const left = digits.endsWith(".") ? digits.slice(0, -1) : digits;
  return `convert ${left} ${fromPrompt} to ${toPrompt}`;
}

/** LaTeX snippet for inserting a live convert result into the composer. */
export function converterInsertSnippet(value: string, symbol: string): string {
  return `${value}\\,\\text{${symbol}}`;
}
