#!/usr/bin/env node
/**
 * The over-the-air update gate (mobile-update.yml): an update may go out only when its
 * native fingerprint is the one the channel's newest finished build was made with, on
 * each platform the channel has a build for (one with none is skipped, with a note).
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

/**
 * The gate's verdict on each platform: `{ platform, update, build }` is this update's
 * runtime version and the channel's newest finished build there (or null). A platform
 * with no build on the channel is skipped with a note (a preview channel may have an
 * iPhone build only): no phone of it can take the update either way. A platform with a
 * build must match it, and at least one platform must have a build.
 */
function gateUpdate(channel, platforms) {
  const notes = [];
  const problems = [];
  for (const { platform, update, build } of platforms) {
    if (!build) {
      notes.push(
        `${platform}: skipped, no finished build listens on the "${channel}" channel, so no ` +
          `${platform} phone takes this update.`,
      );
      continue;
    }
    const problem = runtimeMismatch(platform, channel, update, build);
    if (problem) problems.push(problem);
    else notes.push(`${platform}: fingerprint ${update} matches the newest "${channel}" build.`);
  }
  if (platforms.every(({ build }) => !build)) {
    problems.push(
      `No finished build listens on the "${channel}" channel on any platform, so no phone ` +
        "would take this update. Ship a store build (deploy.yml) before an update.",
    );
  }
  return { notes, problems };
}

/** What is wrong with publishing `update` over `build` (both runtime versions), or null. */
function runtimeMismatch(platform, channel, update, build) {
  if (!update) return `${platform}: could not work out this update's runtime version.`;
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
  const { notes, problems } = gateUpdate(
    channel,
    PLATFORMS.map((platform) => ({
      platform,
      update: updateRuntimeVersion(platform),
      build: newestBuild(platform, channel),
    })),
  );
  for (const note of notes) console.log(note);
  for (const problem of problems) console.log(`::error title=Update gate::${problem}`);
  if (problems.length > 0) process.exit(1);
}

if (require.main === module) main();

module.exports = { gateUpdate };
