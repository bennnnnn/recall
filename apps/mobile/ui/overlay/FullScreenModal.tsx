import { Modal, type ModalProps } from "react-native";

/**
 * A page that replaces the screen: image / PDF / text viewers, the HTML
 * preview, the math scanner, the full-screen graph. Popups are `Menu`,
 * `Dialog` and `Sheet` instead.
 *
 * Keep it mounted and drive `visible` from state. Returning null above an
 * open iOS modal skips RN's dismiss path and can leave the presenter stuck
 * (see the math-scanner lesson in .cursor/rules/lessons.mdc).
 */
export function FullScreenModal({ animationType = "slide", ...props }: ModalProps) {
  return <Modal animationType={animationType} {...props} />;
}
