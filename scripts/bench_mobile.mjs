#!/usr/bin/env node
// Fail a pull request that makes a phone screen clearly slower to render than main's.
//
//   node scripts/bench_mobile.mjs apps/mobile/.reassure   # exit 1 on a regression
//
// Reassure (`pnpm perf` in apps/mobile) renders each benchmark ten times on main's tree at
// the merge base, ten on the pull request's, on the same runner, and compares them in
// .reassure/output.json: each side's mean render time (React's Profiler, ms) and
// `isDurationDiffSignificant`, true when the pull request's mean lies outside main's spread
// (p < 0.02) and differs by at least 5%. Significance alone fails too easily: each side's ten
// renders spread only 1-8%, so a machine busier during one side's run reads as "significant".
// Measured locally, the same tree timed twice stayed within ±2% and 0.6 ms; in a later run
// with a deliberate slowdown of the markdown renderer, the drawer, which it does not touch,
// still came out 20-26% (1.4-1.9 ms) slower. So a regression here is significant, more than
// 25% slower and at least 8 ms more: that slowdown failed all four reply benchmarks (+11 to
// +42 ms) and the drifting drawer passed. The job is advisory (not a required check) until
// its noise on GitHub's runners is measured. The table, then Reassure's report, go to stdout.

import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";

const MOST_RATIO = 0.25;
const LEAST_MS = 8;

const dir = process.argv[2];
if (!dir) {
  console.log("usage: node scripts/bench_mobile.mjs <apps/mobile/.reassure>");
  process.exit(2);
}

// A tree with no benchmarks (main before they existed) writes no baseline: nothing to compare.
if (!existsSync(join(dir, "baseline.perf"))) {
  console.log("Main has no render benchmarks at the merge base yet: nothing to compare.");
  process.exit(0);
}
if (!existsSync(join(dir, "output.json"))) {
  console.log("Reassure wrote no comparison (output.json): see the run's log.");
  process.exit(1);
}

const report = JSON.parse(readFileSync(join(dir, "output.json"), "utf8"));
const ms = (value) => `${value.toFixed(1)} ms`;
const percent = new Intl.NumberFormat("en", {
  style: "percent",
  signDisplay: "exceptZero",
  maximumFractionDigits: 0,
});

function regressed(entry) {
  return (
    entry.isDurationDiffSignificant &&
    entry.relativeDurationDiff > MOST_RATIO &&
    entry.durationDiff >= LEAST_MS
  );
}

function renders(entry) {
  const before = entry.baseline.meanCount;
  const after = entry.current.meanCount;
  return before === after ? "" : `, renders ${before} → ${after}`;
}

const lines = ["| Benchmark | main | this PR | change |", "|---|---|---|---|"];
const compared = [...report.significant, ...report.meaningless].sort((a, b) =>
  a.name.localeCompare(b.name),
);
let slower = false;
for (const entry of compared) {
  const bad = regressed(entry);
  slower ||= bad;
  const change = percent.format(entry.relativeDurationDiff);
  const mark = bad ? " ⚠️ slower" : entry.isDurationDiffSignificant ? " (significant)" : "";
  lines.push(
    `| ${entry.name} | ${ms(entry.baseline.meanDuration)} | ${ms(entry.current.meanDuration)} | ${change}${renders(entry)}${mark} |`,
  );
}
for (const entry of report.added) {
  lines.push(`| ${entry.name} | – | ${ms(entry.current.meanDuration)} | new |`);
}
for (const entry of report.removed) {
  lines.push(`| ${entry.name} | ${ms(entry.baseline.meanDuration)} | – | removed |`);
}

console.log(lines.join("\n"));
if (slower) {
  console.log(
    `\nA render benchmark took over ${MOST_RATIO * 100}% longer than main and at least ` +
      `${LEAST_MS} ms more: profile it before merging.`,
  );
}
const markdown = join(dir, "output.md");
if (existsSync(markdown)) console.log(`\n${readFileSync(markdown, "utf8")}`);
process.exit(slower ? 1 : 0);
