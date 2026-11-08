/**
 * "Open with Recall" for PDFs: what the phone must be told before it offers Recall for a PDF
 * (iOS: Open in, and the share sheet's app row; Android: Open with, and Share), and where the
 * file then arrives (features/attachments/model/openedDocumentRoute.ts, modules/opened-document).
 * Each of these is native: a change needs a new build.
 */
import type { ExpoConfig } from "expo/config";
import { AndroidConfig } from "expo/config-plugins";

import appConfig from "../../app.config";
import appJson from "../../app.json";
import { readSource, ROOT } from "@/lib/__tests__/support/sourceFiles";

type DocumentType = {
  CFBundleTypeName?: string;
  CFBundleTypeRole?: string;
  LSHandlerRank?: string;
  LSItemContentTypes?: string[];
};

// eslint-disable-next-line @typescript-eslint/no-require-imports -- a config plugin is CommonJS, as Expo loads it
const { addOpenedDocumentHook } = require("../../plugins/withOpenedDocumentIntent.js") as {
  addOpenedDocumentHook: (source: string) => string;
};

/** Expo 58's MainActivity.kt (node_modules/expo/template.tgz), its comments and back-button override left out. */
const TEMPLATE_MAIN_ACTIVITY = `package com.recall.app

import android.os.Build
import android.os.Bundle

import com.facebook.react.ReactActivity
import com.facebook.react.ReactActivityDelegate
import com.facebook.react.defaults.DefaultNewArchitectureEntryPoint.fabricEnabled
import com.facebook.react.defaults.DefaultReactActivityDelegate

import expo.modules.ReactActivityDelegateWrapper

class MainActivity : ReactActivity() {
  override fun onCreate(savedInstanceState: Bundle?) {
    setTheme(R.style.AppTheme);
    super.onCreate(null)
  }

  override fun getMainComponentName(): String = "main"

  override fun createReactActivityDelegate(): ReactActivityDelegate {
    return ReactActivityDelegateWrapper(
          this,
          BuildConfig.IS_NEW_ARCHITECTURE_ENABLED,
          object : DefaultReactActivityDelegate(this, mainComponentName, fabricEnabled){})
  }
}
`;

function resolvedConfig(): ExpoConfig {
  return appConfig({ projectRoot: "", staticConfigPath: null, packageJsonPath: null, config: {} });
}

describe("iOS", () => {
  const infoPlist = resolvedConfig().ios?.infoPlist ?? {};

  it("declares Recall a viewer of PDFs, never their default app", () => {
    expect(infoPlist.CFBundleDocumentTypes).toEqual([
      {
        CFBundleTypeName: "PDF document",
        CFBundleTypeRole: "Viewer",
        LSHandlerRank: "Alternate",
        LSItemContentTypes: ["com.adobe.pdf"],
      } satisfies DocumentType,
    ]);
  });

  it("takes a copy into its Inbox rather than opening the other app's file in place", () => {
    // In place, the URL would point into another app's storage, readable only while it lets it be.
    expect(infoPlist.LSSupportsOpeningDocumentsInPlace).toBe(false);
    expect(infoPlist.UISupportsDocumentBrowser).toBeUndefined();
  });

  it("keeps them through app.config.ts, which rebuilds ios.infoPlist", () => {
    expect(infoPlist.CFBundleDocumentTypes).toEqual(appJson.expo.ios.infoPlist.CFBundleDocumentTypes);
    expect(infoPlist.LSApplicationQueriesSchemes).toEqual(appJson.expo.ios.infoPlist.LSApplicationQueriesSchemes);
  });
});

describe("Android", () => {
  /** MainActivity's intent filters as `expo prebuild` writes them into AndroidManifest.xml. */
  function renderedFilters() {
    // The template's MainActivity, with its launcher filter: prebuild adds the app's beside it.
    const launcher = {
      action: [{ $: { "android:name": "android.intent.action.MAIN" } }],
      category: [{ $: { "android:name": "android.intent.category.LAUNCHER" } }],
    };
    const mainActivity = { $: { "android:name": ".MainActivity" }, "intent-filter": [launcher] };
    const manifest = {
      manifest: {
        $: { "xmlns:android": "http://schemas.android.com/apk/res/android" },
        application: [{ $: { "android:name": ".MainApplication" }, activity: [mainActivity] }],
      },
    } as unknown as AndroidConfig.Manifest.AndroidManifest;
    const written = AndroidConfig.IntentFilters.setAndroidIntentFilters(resolvedConfig(), manifest);
    const activity = AndroidConfig.Manifest.getMainActivityOrThrow(written);
    return (activity["intent-filter"] ?? []).map((filter) => ({
      action: filter.action?.map((entry) => entry.$["android:name"]),
      category: filter.category?.map((entry) => entry.$["android:name"]),
      data: filter.data?.map((entry) => entry.$),
    }));
  }

  it("offers Recall in Open with for a PDF another app serves", () => {
    expect(renderedFilters()).toContainEqual({
      action: ["android.intent.action.VIEW"],
      category: ["android.intent.category.DEFAULT"],
      // content: only. A file: path would let another app have Recall read its own files.
      data: [{ "android:scheme": "content", "android:mimeType": "application/pdf" }],
    });
  });

  it("offers Recall in the share sheet for a PDF", () => {
    expect(renderedFilters()).toContainEqual({
      action: ["android.intent.action.SEND"],
      category: ["android.intent.category.DEFAULT"],
      data: [{ "android:mimeType": "application/pdf" }],
    });
  });

  it("is not a browser target: a web page cannot hand Recall a PDF intent", () => {
    for (const filter of renderedFilters()) {
      expect(filter.category ?? []).not.toContain("android.intent.category.BROWSABLE");
    }
  });

  it("reads every new intent in MainActivity, before Expo's wrapper can drop it while the app loads", () => {
    expect(appJson.expo.plugins).toContain("./plugins/withOpenedDocumentIntent.js");
    const patched = addOpenedDocumentHook(TEMPLATE_MAIN_ACTIVITY);
    expect(patched).toMatch(/^import android\.content\.Intent$/m);
    expect(patched).toMatch(
      /override fun onNewIntent\(intent: Intent\) \{\n\s+expo\.modules\.recallopeneddocument\.OpenedDocumentIntents\.onNewIntent\(this, intent\)\n\s+super\.onNewIntent\(intent\)\n/,
    );
    // A prebuild over an existing android/ applies it again: nothing changes.
    expect(addOpenedDocumentHook(patched)).toBe(patched);
  });

  it("joins an onNewIntent MainActivity already has", () => {
    const own = TEMPLATE_MAIN_ACTIVITY.replace(
      "class MainActivity : ReactActivity() {\n",
      "class MainActivity : ReactActivity() {\n  override fun onNewIntent(next: Intent) {\n    super.onNewIntent(next)\n  }\n",
    );
    const patched = addOpenedDocumentHook(own);
    expect(patched.match(/override fun onNewIntent/g)).toHaveLength(1);
    expect(patched).toContain(
      "override fun onNewIntent(next: Intent) {\n    expo.modules.recallopeneddocument.OpenedDocumentIntents.onNewIntent(this, next)\n",
    );
  });

  it.each([
    ["a qualified Intent", "override fun onNewIntent(intent: android.content.Intent) {\n"],
    ["a comment after the brace", "override fun onNewIntent(intent: Intent) { // deep links\n"],
    ["a declared return type", "override fun onNewIntent(intent: Intent): Unit {\n"],
  ])("joins an existing onNewIntent with %s", (_case, opening) => {
    const own = TEMPLATE_MAIN_ACTIVITY.replace(
      "class MainActivity : ReactActivity() {\n",
      `class MainActivity : ReactActivity() {\n  ${opening}    super.onNewIntent(intent)\n  }\n`,
    );
    const patched = addOpenedDocumentHook(own);
    expect(patched.match(/fun onNewIntent/g)).toHaveLength(1);
    expect(patched).toContain(
      `${opening}    expo.modules.recallopeneddocument.OpenedDocumentIntents.onNewIntent(this, intent)\n`,
    );
  });

  it("fails the prebuild on an onNewIntent it cannot join, rather than adding a second", () => {
    const own = TEMPLATE_MAIN_ACTIVITY.replace(
      "class MainActivity : ReactActivity() {\n",
      "class MainActivity : ReactActivity() {\n  override fun onNewIntent(intent: Intent) = super.onNewIntent(intent)\n",
    );
    expect(() => addOpenedDocumentHook(own)).toThrow(/cannot join/);
  });

  it("imports Intent in a MainActivity with no package line", () => {
    const patched = addOpenedDocumentHook(TEMPLATE_MAIN_ACTIVITY.replace("package com.recall.app\n\n", ""));
    expect(patched.startsWith("import android.content.Intent\n")).toBe(true);
  });

  it("autolinks the Android module that reads Share's EXTRA_STREAM and the file's name", () => {
    expect(JSON.parse(readSource(`${ROOT}/modules/opened-document/expo-module.config.json`))).toEqual({
      platforms: ["android"],
      android: { modules: ["expo.modules.recallopeneddocument.OpenedDocumentModule"] },
    });
  });
});
