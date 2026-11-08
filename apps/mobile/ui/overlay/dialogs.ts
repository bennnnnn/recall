import { Alert, Linking } from "react-native";

import i18n, { t } from "i18next";

import type { DialogAction } from "./Dialog";

export type DialogRequest = {
  title: string;
  message?: string;
  actions: DialogAction[];
  /** Runs when the dialog closes without a button (scrim, Android back). */
  onDismiss: () => void;
};

type Host = (request: DialogRequest) => void;

/** Shared copy. Falls back to the key before i18n has started. */
function label(key: string): string {
  const text = i18n.isInitialized ? t(key) : "";
  return typeof text === "string" && text ? text : key;
}

let host: Host | null = null;

/** `DialogHost` registers itself here; the last mounted host wins. */
export function registerDialogHost(next: Host): () => void {
  host = next;
  return () => {
    if (host === next) host = null;
  };
}

/**
 * No host mounted (tests, code running outside the app root): the platform
 * alert shows the same choices. It is called the way the app always called
 * it — a plain notice gets only its title and message.
 */
function show(request: DialogRequest, plainNotice = false): void {
  if (host) {
    host(request);
    return;
  }
  if (plainNotice) {
    if (request.message === undefined) Alert.alert(request.title);
    else Alert.alert(request.title, request.message);
    request.onDismiss();
    return;
  }
  Alert.alert(
    request.title,
    request.message,
    request.actions.map((action) => ({
      text: action.label,
      style:
        action.style === "destructive"
          ? "destructive"
          : action.style === "cancel"
            ? "cancel"
            : "default",
      onPress: action.onPress,
    })),
  );
}

export type ConfirmOptions = {
  title: string;
  message?: string;
  /** Defaults to OK. Name the action ("Delete", "Sign out") when you can. */
  confirmLabel?: string;
  cancelLabel?: string;
  /** Red confirm button for actions that lose data. */
  destructive?: boolean;
};

/**
 * Ask before acting. Resolves true when the person confirms, false on Cancel
 * or when they dismiss the dialog.
 */
export function confirmDialog(options: ConfirmOptions): Promise<boolean> {
  return new Promise((resolve) => {
    let settled = false;
    const finish = (value: boolean) => {
      if (settled) return;
      settled = true;
      resolve(value);
    };
    show({
      title: options.title,
      message: options.message,
      actions: [
        {
          label: options.cancelLabel ?? label("common.cancel"),
          style: "cancel",
          onPress: () => finish(false),
        },
        {
          label: options.confirmLabel ?? label("common.ok"),
          style: options.destructive ? "destructive" : "primary",
          onPress: () => finish(true),
        },
      ],
      onDismiss: () => finish(false),
    });
  });
}

type AlertOptions = {
  title: string;
  message?: string;
  /** Extra buttons (e.g. Open Settings). An OK button is added when omitted. */
  actions?: DialogAction[];
};

/** Tell the person something that needs acknowledging. Resolves when closed. */
export function alertDialog(options: AlertOptions): Promise<void> {
  return new Promise((resolve) => {
    let settled = false;
    const finish = () => {
      if (settled) return;
      settled = true;
      resolve();
    };
    const custom = Boolean(options.actions && options.actions.length > 0);
    const actions: DialogAction[] = (
      custom ? (options.actions as DialogAction[]) : [{ label: label("common.ok"), style: "primary" as const }]
    ).map((action) => ({
      ...action,
      onPress: () => {
        action.onPress?.();
        finish();
      },
    }));
    show({ title: options.title, message: options.message, actions, onDismiss: finish }, !custom);
  });
}

/** A permission the OS asks for once; after a refusal only Settings can turn it back on. */
export type SettingsPermission = "camera" | "microphone" | "photos" | "location" | "notifications";

/**
 * Offer Settings for a permission that is off: a dialog that names it, with Not now and
 * Open Settings, and the app is left only on Open Settings. Each permission asks in its
 * own words, and every offer is this one dialog. Resolves true once Settings opened; when
 * it cannot open, says so.
 */
export async function offerSettings(permission: SettingsPermission): Promise<boolean> {
  const open = await confirmDialog({
    title: label(`permissions.${permission}_title`),
    message: label(`permissions.${permission}_body`),
    cancelLabel: label("common.not_now"),
    confirmLabel: label("common.open_settings"),
  });
  if (!open) return false;
  try {
    await Linking.openSettings();
    return true;
  } catch (error) {
    console.warn("[settings] could not open Settings", error instanceof Error ? error.name : typeof error);
    void alertDialog({ title: label("common.open_settings_failed") });
    return false;
  }
}
