/**
 * The platform's own face: "System" is SF Pro on iOS and Roboto on Android. The OS
 * draws every weight and the italics from its own files, tuned for each size, so
 * nothing is loaded and `fontWeight` / `fontStyle` are real, never faux.
 */
export const UI_FONT_FAMILY = "System";

/** One line of the UI face at its natural height, in em (SF Pro 1.19, Roboto 1.17), rounded up. */
export const UI_LINE_EM = 1.2;

