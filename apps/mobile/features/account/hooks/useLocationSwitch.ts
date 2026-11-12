import { useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { useAuth } from "@/contexts/AuthContext";
import { useSettingSave } from "@/features/account/components/settingsUi";
import { getDeviceLocationLabel } from "@/lib/deviceLocation";
import { canUseDeviceLocation } from "@/lib/expoRuntime";
import { alertDialog } from "@/ui/overlay/dialogs";

/**
 * Data controls' Location switch. Off saves at once. On reads the phone first (its
 * permission sheet, then a fix): the switch shows on while it does, saves the place when
 * the phone gives one, and goes back with a word when it says no. No spinner in its place.
 */
export function useLocationSwitch(): { on: boolean; toggle: (enabled: boolean) => void } {
  const { user } = useAuth();
  const { t } = useTranslation();
  const save = useSettingSave();
  const [shown, setShown] = useState<boolean | null>(null);
  const reading = useRef(false);

  const toggle = (enabled: boolean) => {
    if (reading.current) return;
    if (!enabled) {
      save({ location_enabled: false, location: null });
      return;
    }
    if (!canUseDeviceLocation()) {
      void alertDialog({ title: t("common.error"), message: t("settings.location_expo_go") });
      return;
    }
    reading.current = true;
    setShown(true);
    void getDeviceLocationLabel()
      .then((label) => {
        if (label) save({ location_enabled: true, location: label });
        else void alertDialog({ title: t("settings.location_denied") });
      })
      .finally(() => {
        reading.current = false;
        setShown(null);
      });
  };

  return { on: shown ?? user?.location_enabled === true, toggle };
}
