import { Alert } from "react-native";

/** In-app ask before GPS — then iOS shows the system permission sheet if needed. */
export function confirmGeoLocationAccess(
  t: (key: string) => string,
): Promise<boolean> {
  return new Promise((resolve) => {
    Alert.alert(
      t("chat.location_required_title"),
      t("chat.location_confirm_body"),
      [
        { text: t("common.cancel"), style: "cancel", onPress: () => resolve(false) },
        { text: t("chat.location_allow"), onPress: () => resolve(true) },
      ],
    );
  });
}
