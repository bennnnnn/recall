import { StyleSheet } from "react-native";

import { CHROME_FADE_EXTRA } from "@/lib/chromeFade";
import {
  COMPOSER_CONTROL_SIZE,
  COMPOSER_INPUT_LINE_HEIGHT,
  COMPOSER_INPUT_MAX_HEIGHT,
  COMPOSER_INPUT_MIN_HEIGHT,
} from "@/lib/chat/composerLogic";
import { Radius } from "@/lib/radius";
import { Space } from "@/lib/space";
import { Theme } from "@/lib/theme";
import { Type, Weight } from "@/lib/type";

export const MATH_KEYBOARD_CHIP_HEIGHT = 44;

export function makeChatComposerStyles(theme: Theme) {
  return StyleSheet.create({
    composerBlock: {
      position: "absolute",
      left: 0,
      right: 0,
      zIndex: 110,
      overflow: "visible",
      backgroundColor: "transparent",
      paddingHorizontal: Space.md,
      paddingTop: Space.xxs,
    },
    scrollFade: {
      position: "absolute",
      left: -Space.md,
      right: -Space.md,
      top: -CHROME_FADE_EXTRA,
      height: CHROME_FADE_EXTRA,
      zIndex: 2,
    },
    composerDocked: {
      overflow: "visible",
      backgroundColor: "transparent",
      paddingHorizontal: Space.md,
      paddingTop: Space.xxs,
    },
    composerBlockExpanded: {
      zIndex: 200,
      backgroundColor: theme.bg,
    },
    expandedFill: { flex: 1, minHeight: 0 },
    bottomFade: {
      position: "absolute",
      left: -Space.md,
      right: -Space.md,
      zIndex: 0,
    },
    composerAnchor: { position: "relative", overflow: "visible", zIndex: 1 },
    composer: { paddingVertical: 6, overflow: "visible" },
    inputStack: { position: "relative", overflow: "visible" },
    liveTalkRow: {
      flexDirection: "row",
      alignItems: "flex-end",
      gap: Space.xs,
    },
    inputWrap: {
      // Attachments and the input row live inside the same rounded card.
      backgroundColor: theme.control,
      borderRadius: Radius.sheet,
      paddingHorizontal: Space.md,
      paddingTop: Space.xxs,
      paddingBottom: Space.xxs,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: theme.composerBorder,
    },
    inputWrapFlex: { flex: 1, minWidth: 0 },
    inputWrapExpanded: { flex: 1, minHeight: 0 },
    sendStatus: {
      marginTop: Space.xxs,
      marginLeft: 40,
      ...Type.meta,
      color: theme.textSecondary,
    },
    inputRowMain: { flexDirection: "row", alignItems: "flex-end", gap: Space.xs },
    inputRowMainSingleLine: { alignItems: "center" },
    inputRowMainExpanded: { flex: 1, minHeight: 0 },
    inputField: {
      flex: 1,
      justifyContent: "flex-end",
      minHeight: COMPOSER_INPUT_MIN_HEIGHT,
      position: "relative",
    },
    inputFieldExpanded: { justifyContent: "flex-start", minHeight: 0, paddingBottom: 0 },
    expandControlRow: {
      minHeight: Space.minTouch,
      flexDirection: "row",
      justifyContent: "flex-end",
      alignItems: "center",
    },
    expandControl: {
      width: Space.minTouch,
      height: Space.minTouch,
      borderRadius: Space.minTouch / 2,
      alignItems: "center",
      justifyContent: "center",
    },
    emptyCaret: {
      position: "absolute",
      left: 0,
      top: 2,
      bottom: 2,
      justifyContent: "center",
      zIndex: 2,
    },
    attachBtn: {
      width: COMPOSER_CONTROL_SIZE,
      height: COMPOSER_CONTROL_SIZE,
      borderRadius: COMPOSER_CONTROL_SIZE / 2,
      // Keep the + as quiet chrome inside the shared composer surface.
      borderWidth: 0,
      borderColor: "transparent",
      backgroundColor: "transparent",
      alignItems: "center",
      justifyContent: "center",
      marginBottom: 0,
    },
    controlDisabled: { opacity: 0.55 },
    chip: {
      position: "absolute",
      left: 0,
      top: -(MATH_KEYBOARD_CHIP_HEIGHT + Space.xxs),
      zIndex: 1,
      minWidth: Space.minTouch,
      minHeight: Space.minTouch,
      height: Space.minTouch,
      paddingHorizontal: 10,
      borderRadius: Radius.xl,
      alignItems: "center",
      justifyContent: "center",
      backgroundColor: "transparent",
    },
    chipPressed: { opacity: 0.55 },
    input: {
      flex: 1,
      ...Type.body,
      color: theme.text,
      // Fixed line box. A padded field makes iOS draw the caret a line too high.
      lineHeight: COMPOSER_INPUT_LINE_HEIGHT,
      maxHeight: COMPOSER_INPUT_MAX_HEIGHT,
      paddingVertical: 0,
      minHeight: COMPOSER_INPUT_LINE_HEIGHT,
    },
    inputExpanded: {
      height: undefined,
      maxHeight: undefined,
      minHeight: 0,
      textAlignVertical: "top",
    },
    inputParked: {
      position: "absolute",
      width: 1,
      height: 1,
      opacity: 0,
      overflow: "hidden",
      flex: 0,
    },
    sendBtn: {
      width: COMPOSER_CONTROL_SIZE,
      height: COMPOSER_CONTROL_SIZE,
      borderRadius: Radius.full,
      backgroundColor: theme.primary,
      alignItems: "center",
      justifyContent: "center",
    },
    sendBtnSlot: {
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "flex-end",
      gap: Space.xxs,
      minHeight: COMPOSER_CONTROL_SIZE,
    },
    sendBtnDisabled: { backgroundColor: theme.border },
    scanHint: {
      flexDirection: "row",
      alignItems: "center",
      gap: Space.xs,
      marginBottom: 6,
      paddingHorizontal: 10,
      paddingVertical: Space.xs,
      borderRadius: Radius.sm,
      backgroundColor: theme.primaryLight,
    },
    scanHintText: { flex: 1, ...Type.compact, color: theme.text },
    scanHintCta: { ...Type.compact, ...Weight.bold, color: theme.primary },
  });
}
