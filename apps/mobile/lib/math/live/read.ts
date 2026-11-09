/**
 * Reads the math keyboard's draft (`$3+1\times 2$`) into a tree the live answer evaluates.
 *
 * Only a calculation made of numbers is read: digits, + − × ÷, brackets, powers, roots,
 * fractions, %, !, π, e, trig, logs, |x|, ⌊x⌋, ⌈x⌉, mod, binomials and P(n, k). Anything
 * else — a letter, `=`, `<`, `\pm`, an integral, a sum, a limit, an empty box — is not a
 * calculation, and `readCalculation` gives `null`: the composer then shows no answer and
 * Send asks the server as before.
 *
 * Precedence follows the server's reading (SymPy's, `docs/fixtures/live_answer_cases.json`
 * holds the two together): × ÷ mod and a written-together product share one level and run
 * left to right (`6÷2(1+2)` is 9), `^` binds tighter than a leading minus (`-3^2` is −9)
 * and groups to the right (`2^3^2` is 512).
 */
import { guard, refuse } from "@/lib/fence/validate";

export type LiveFunction =
  | "sin" | "cos" | "tan" | "cot" | "sec" | "csc"
  | "asin" | "acos" | "atan" | "acot" | "asec" | "acsc"
  | "sinh" | "cosh" | "tanh" | "coth" | "sech" | "csch"
  | "asinh" | "acosh" | "atanh"
  | "log" | "ln" | "exp";

export type LiveNode =
  | { kind: "number"; text: string }
  | { kind: "pi" }
  | { kind: "e" }
  | { kind: "add"; op: "+" | "-"; left: LiveNode; right: LiveNode }
  | { kind: "mul"; op: "*" | "/" | "mod"; left: LiveNode; right: LiveNode }
  | { kind: "neg"; operand: LiveNode }
  | { kind: "pow"; base: LiveNode; exponent: LiveNode }
  | { kind: "frac"; num: LiveNode; den: LiveNode }
  | { kind: "root"; index: LiveNode | null; radicand: LiveNode }
  | { kind: "factorial" | "percent" | "degrees" | "radians" | "abs" | "floor" | "ceil"; operand: LiveNode }
  | { kind: "call"; fn: LiveFunction; arg: LiveNode; base: LiveNode | null }
  | { kind: "binom" | "perm"; n: LiveNode; k: LiveNode };

const MAX_LENGTH = 400;
const MAX_DEPTH = 48;

/** `\cot^{-1}` is acot; the hyperbolic keys with no inverse here are refused. */
const INVERSE: Partial<Record<string, LiveFunction>> = {
  sin: "asin", cos: "acos", tan: "atan", cot: "acot", sec: "asec", csc: "acsc",
  sinh: "asinh", cosh: "acosh", tanh: "atanh",
};
const NAMED: Record<string, LiveFunction> = {
  sin: "sin", cos: "cos", tan: "tan", cot: "cot", sec: "sec", csc: "csc",
  sinh: "sinh", cosh: "cosh", tanh: "tanh", coth: "coth", sech: "sech", csch: "csch",
  arcsin: "asin", arccos: "acos", arctan: "atan",
  log: "log", ln: "ln", exp: "exp",
};
/** Spacing commands, and `\left` / `\right`, which only size the bracket after them. */
const SKIPPED = new Set([",", ";", ":", "!", " ", "quad", "qquad", "left", "right"]);
const TIMES = new Set(["*", "×", "·"]);
const DIVIDE = new Set(["/", "÷"]);

class Reader {
  private pos = 0;
  private depth = 0;

  constructor(private readonly src: string) {}

  read(): LiveNode {
    const node = this.expression();
    this.space();
    if (this.pos !== this.src.length) refuse();
    return node;
  }

  private fail(): never {
    return refuse();
  }

  /** The command at the cursor (`\frac` → `frac`, `\%` → `%`), without moving. */
  private command(): string | null {
    if (this.src[this.pos] !== "\\") return null;
    const word = /^[A-Za-z]+/.exec(this.src.slice(this.pos + 1));
    return word ? word[0] : (this.src[this.pos + 1] ?? null);
  }

  private take(command: string): boolean {
    if (this.command() !== command) return false;
    this.pos += command.length + 1;
    return true;
  }

  private space(): void {
    for (;;) {
      if (/\s/.test(this.src[this.pos] ?? "")) this.pos += 1;
      else if (SKIPPED.has(this.command() ?? "")) this.pos += (this.command() ?? "").length + 1;
      else return;
    }
  }

  private peek(): string {
    this.space();
    return this.src[this.pos] ?? "";
  }

  private expect(char: string): void {
    if (this.peek() !== char) this.fail();
    this.pos += 1;
  }

  private expression(): LiveNode {
    this.depth += 1;
    if (this.depth > MAX_DEPTH) this.fail();
    let left = this.term();
    for (let c = this.peek(); c === "+" || c === "-" || c === "−"; c = this.peek()) {
      this.pos += 1;
      left = { kind: "add", op: c === "+" ? "+" : "-", left, right: this.term() };
    }
    this.depth -= 1;
    return left;
  }

  private term(): LiveNode {
    let left = this.unary();
    for (;;) {
      const c = this.peek();
      const op = this.operator(c);
      if (op) {
        left = { kind: "mul", op, left, right: this.unary() };
      } else if (this.startsFactor()) {
        // Written together (`2(3+1)`, `2\pi`, `3\sqrt{2}`): a product on the same level.
        left = { kind: "mul", op: "*", left, right: this.power() };
      } else {
        return left;
      }
    }
  }

  private operator(c: string): "*" | "/" | "mod" | null {
    if (TIMES.has(c) || DIVIDE.has(c)) {
      this.pos += 1;
      return TIMES.has(c) ? "*" : "/";
    }
    if (this.take("times") || this.take("cdot")) return "*";
    if (this.take("div")) return "/";
    if (this.take("bmod")) return "mod";
    return null;
  }

  /** What may follow a factor with no sign between them. A digit may not (`2 3`). */
  private startsFactor(): boolean {
    const c = this.peek();
    if (c === "(" || c === "[" || c === "π") return true;
    if (c === "e") return !/[A-Za-z]/.test(this.src[this.pos + 1] ?? "");
    if (c === "P") return this.src[this.pos + 1] === "(";
    const command = this.command();
    if (!command) return false;
    return (
      command in NAMED ||
      ["frac", "dfrac", "tfrac", "sqrt", "pi", "lfloor", "lceil", "binom"].includes(command)
    );
  }

  private unary(): LiveNode {
    const c = this.peek();
    if (c === "-" || c === "−") {
      this.pos += 1;
      return { kind: "neg", operand: this.unary() };
    }
    if (c === "+") {
      this.pos += 1;
      return this.unary();
    }
    return this.power();
  }

  private power(): LiveNode {
    const base = this.postfix();
    if (this.peek() !== "^") return base;
    this.pos += 1;
    if (this.peek() === "{") {
      const save = this.pos;
      this.pos += 1;
      if (this.take("circ") && this.peek() === "}") {
        this.pos += 1;
        return { kind: "degrees", operand: base };
      }
      this.pos = save;
      const exponent = this.group();
      if (this.peek() === "!") this.fail(); // `2^{3}!`: (2³)! or 2^(3!)
      return { kind: "pow", base, exponent };
    }
    // A typed `2^3`: the exponent is one signed factor, grouping to the right.
    const c = this.peek();
    if (c !== "-" && c !== "−") return { kind: "pow", base, exponent: this.power() };
    this.pos += 1;
    return { kind: "pow", base, exponent: { kind: "neg", operand: this.power() } };
  }

  private postfix(): LiveNode {
    let node = this.primary();
    for (;;) {
      const c = this.peek();
      if (c === "!") {
        this.pos += 1;
        if (this.peek() === "!") this.fail(); // `3!!`: a double factorial or (3!)!
        node = { kind: "factorial", operand: node };
      } else if (c === "°") {
        this.pos += 1;
        node = { kind: "degrees", operand: node };
      } else if (this.take("%")) {
        node = { kind: "percent", operand: node };
      } else if (this.src.startsWith("\\mathrm{rad}", this.pos)) {
        this.pos += "\\mathrm{rad}".length;
        node = { kind: "radians", operand: node };
      } else {
        return node;
      }
    }
  }

  private group(): LiveNode {
    this.expect("{");
    const node = this.expression();
    this.expect("}");
    return node;
  }

  private closed(open: string, close: string): LiveNode {
    this.expect(open);
    const node = this.expression();
    this.expect(close);
    return node;
  }

  private primary(): LiveNode {
    const c = this.peek();
    const number = /^(?:\d+(?:\.\d+)?|\.\d+)/.exec(this.src.slice(this.pos));
    if (number) {
      this.pos += number[0].length;
      if (this.src[this.pos] === ".") this.fail(); // `3.` or `1.2.3`: still being typed
      return { kind: "number", text: number[0] };
    }
    if (c === "(") return this.closed("(", ")");
    if (c === "[") return this.closed("[", "]");
    if (c === "{") return this.group();
    if (c === "|") return { kind: "abs", operand: this.closed("|", "|") };
    if (c === "π" || (c === "e" && !/[A-Za-z]/.test(this.src[this.pos + 1] ?? ""))) {
      this.pos += 1;
      return { kind: c === "π" ? "pi" : "e" };
    }
    if (c === "P" && this.src[this.pos + 1] === "(") return this.perm();
    if (c === "\\") return this.commandPrimary();
    return this.fail();
  }

  private perm(): LiveNode {
    this.pos += 1;
    this.expect("(");
    const n = this.expression();
    this.expect(",");
    const k = this.expression();
    this.expect(")");
    return { kind: "perm", n, k };
  }

  private commandPrimary(): LiveNode {
    if (this.take("frac") || this.take("dfrac") || this.take("tfrac")) {
      return { kind: "frac", num: this.group(), den: this.group() };
    }
    if (this.take("sqrt")) {
      const index = this.peek() === "[" ? this.closed("[", "]") : null;
      return { kind: "root", index, radicand: this.group() };
    }
    if (this.take("pi")) return { kind: "pi" };
    if (this.take("binom")) return { kind: "binom", n: this.group(), k: this.group() };
    if (this.take("lfloor")) return this.until("floor", "rfloor");
    if (this.take("lceil")) return this.until("ceil", "rceil");
    const name = this.command();
    if (name && name in NAMED) {
      this.pos += name.length + 1;
      return this.call(name);
    }
    return this.fail();
  }

  private until(kind: "floor" | "ceil", close: string): LiveNode {
    const operand = this.expression();
    this.space();
    if (!this.take(close)) this.fail();
    return { kind, operand };
  }

  private call(name: string): LiveNode {
    let fn = NAMED[name]!;
    let base: LiveNode | null = null;
    if (fn === "log" && this.peek() === "_") {
      this.pos += 1;
      base = this.group();
    }
    if (this.peek() === "^") {
      // Only the inverse, as the keys type it (`\cot^{-1}`); `\sin^{2}` is not read.
      if (!this.src.startsWith("^{-1}", this.pos)) this.fail();
      const inverse = INVERSE[name];
      if (!inverse) this.fail();
      this.pos += "^{-1}".length;
      fn = inverse;
    }
    const c = this.peek();
    const arg = c === "(" ? this.closed("(", ")") : c === "{" ? this.group() : this.fail();
    return { kind: "call", fn, arg, base };
  }
}

/**
 * The calculation a draft holds, or `null`. A draft is one `$…$` span the keys typed (or
 * plain text with a digit, as `3+1*2` typed on the phone's own keyboard); words around
 * it make it a question for the server.
 */
export function readCalculation(draft: string): LiveNode | null {
  const text = draft.trim();
  if (!text || text.length > MAX_LENGTH) return null;
  let math = text;
  if (text.includes("$")) {
    const span = /^\$([^$]+)\$$/.exec(text);
    if (!span) return null;
    math = span[1]!;
  } else if (!/\d/.test(text)) {
    return null;
  }
  return guard(() => new Reader(math).read());
}
