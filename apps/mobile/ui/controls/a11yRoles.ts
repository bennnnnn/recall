import { Platform, type AccessibilityRole } from "react-native";

/**
 * Roles VoiceOver has no word for. React Native gives iOS no trait and no value for `menuitem`
 * or `tab`, so a menu row or a tab was read as bare text, with nothing to say it acts. iOS's own
 * menus and tab bars read as buttons, "Selected" on the current one (pass
 * `accessibilityState.selected`); TalkBack has the real roles and says "menu item" and "tab".
 * `radio` needs nothing here: React Native reads it out on iOS ("radio button, checked").
 */
export function menuItemRole(): AccessibilityRole {
  return Platform.OS === "ios" ? "button" : "menuitem";
}

/** One tab in a row of tabs (`tablist`); give it `accessibilityState.selected`. */
export function tabRole(): AccessibilityRole {
  return Platform.OS === "ios" ? "button" : "tab";
}
