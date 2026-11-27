#!/usr/bin/env node
/**
 * The over-the-air update gate (mobile-update.yml): an update may go out only when its
 * native fingerprint is the one the channel's newest finished build was made with.
 *
 * app.json's runtimeVersion policy is "fingerprint": the runtime version is a hash of
 * everything native (packages with native code and their versions, config plugins, the
 * app config, patches). A build takes only updates with its own hash, so an update that
 * needs native code an installed build lacks never reaches that build. This gate turns
 * the quiet case, an update that would reach no build at all, into a failed publish that
 * says why: a store build (deploy.yml) has to ship first.
 *
 * Run from apps/mobile with the channel's EAS environment loaded, so app.config.ts
 * resolves as it did on the build worker:
 *   eas env:exec production 'node scripts/check-update-runtime.cjs production'
 */
const { execFileSync } = require("node:child_process");

const PLATFORMS = ["ios", "android"];

/** What is wrong with publishing `update` over `build` (both runtime versions), or null. */
function runtimeMismatch(platform, channel, update, build) {
  if (!update) return `${platform}: could not work out this update's runtime version.`;
  if (!build) {
    return (
      `${platform}: no finished build listens on the "${channel}" channel yet. ` +
      "Ship a store build (deploy.yml) before an update."
    );
  }
  if (build.runtimeVersion !== update) {
    return (
      `${platform}: this update's native fingerprint is ${update}, but the newest ` +
      `"${channel}" build (${build.id}) has ${build.runtimeVersion}. Native code, a config ` +
      "plugin, the app config or a native package's version changed since that build, so " +
      "no installed phone would take this update. Ship a store build (deploy.yml) first. " +
      `\`eas fingerprint:compare --build-id ${build.id}\` shows what changed.`
    );
  }
  return null;
}

/** This checkout's runtime version for `platform`, as `eas update` works it out. */
function updateRuntimeVersion(platform) {
  const out = execFileSync(
    "node",
    [require.resolve("expo-updates/bin/cli.js"), "runtimeversion:resolve", "--platform", platform],
    { encoding: "utf8", stdio: ["ignore", "pipe", "inherit"] },
  );
  return JSON.parse(out).runtimeVersion ?? null;
}

/** The newest finished build on `channel` for `platform`, or null. */
function newestBuild(platform, channel) {
  const out = execFileSync(
    "eas",
    [
      "build:list",
      "--platform", platform,
      "--channel", channel,
      "--status", "finished",
      "--limit", "1",
      "--json",
      "--non-interactive",
    ],
    { encoding: "utf8", stdio: ["ignore", "pipe", "inherit"] },
  );
  // The build as EAS's API has it: its runtime version is `runtime.version`.
  const [build] = JSON.parse(out);
  return build ? { id: build.id, runtimeVersion: build.runtime?.version ?? null } : null;
}

function main() {
  const channel = process.argv[2];
  if (!channel) {
    console.error("Usage: node scripts/check-update-runtime.cjs <channel>");
    process.exit(2);
  }
  const problems = [];
  for (const platform of PLATFORMS) {
    const update = updateRuntimeVersion(platform);
    const problem = runtimeMismatch(platform, channel, update, newestBuild(platform, channel));
    if (problem) problems.push(problem);
    else console.log(`${platform}: fingerprint ${update} matches the newest "${channel}" build.`);
  }
  for (const problem of problems) console.log(`::error title=Native code changed::${problem}`);
  if (problems.length > 0) process.exit(1);
}

if (require.main === module) main();

module.exports = { runtimeMismatch };
