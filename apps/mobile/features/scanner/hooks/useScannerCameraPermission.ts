import { useEffect } from "react";
import { useCameraPermissions } from "expo-image-picker";

import { useOnForeground } from "@/lib/foregroundRefresh";
import { useLatestRef } from "@/lib/latestRef";

/**
 * The camera permission, read each time the scanner opens and each time the app comes back
 * while it is open. The scanner stays mounted after its first open, and the permission hook
 * reads only when it mounts: a camera allowed in the phone's Settings (the permission screen's
 * Open Settings) went unseen until the app restarted.
 */
export function useScannerCameraPermission(open: boolean) {
  const [permission, requestPermission, readPermission] = useCameraPermissions({ get: false });
  const read = useLatestRef(readPermission);
  useEffect(() => {
    if (open) void read.current();
  }, [open, read]);
  useOnForeground(() => void read.current(), open);
  return [permission, requestPermission] as const;
}
