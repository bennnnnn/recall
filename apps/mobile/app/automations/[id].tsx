import { Redirect } from "expo-router";

/**
 * Older builds and push payloads may still deep-link to an automation id.
 * My Job now has one dedicated search dashboard, so collapse those links into
 * the purpose-built feed instead of showing the retired generic task editor.
 */
export default function LegacyAutomationDetailRedirect() {
  return <Redirect href="/automations" />;
}
