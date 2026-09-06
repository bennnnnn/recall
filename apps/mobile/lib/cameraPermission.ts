/** Permission shape shared by expo-camera and expo-image-picker. */
export type CameraPermissionSnapshot = {
  granted: boolean;
  canAskAgain?: boolean;
};

/** OS will not show the permission sheet again — only Settings can re-enable. */
export function cameraPermissionNeedsSettings(
  permission: CameraPermissionSnapshot | null | undefined,
): boolean {
  return Boolean(permission && !permission.granted && permission.canAskAgain === false);
}
