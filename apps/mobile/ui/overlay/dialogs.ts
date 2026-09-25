import { Alert } from "react-native";

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

/** Shared button copy. Falls back to the key before i18n has started. */
function label(key: "common.ok" | "common.cancel"): string {
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

function show(request: DialogRequest): void {
  if (host) {
    host(request);
    return;
  }
  // No host mounted (tests, code running outside the app root): the platform
  // alert keeps the same choices so callers behave the same either way.
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
    { cancelable: true, onDismiss: request.onDismiss },
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
export function confirm(options: ConfirmOptions): Promise<boolean> {
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

export type AlertOptions = {
  title: string;
  message?: string;
  /** Extra buttons (e.g. Open Settings). An OK button is added when omitted. */
  actions?: DialogAction[];
};

/** Tell the person something that needs acknowledging. Resolves when closed. */
export function alert(options: AlertOptions): Promise<void> {
  return new Promise((resolve) => {
    let settled = false;
    const finish = () => {
      if (settled) return;
      settled = true;
      resolve();
    };
    const actions: DialogAction[] = (
      options.actions && options.actions.length > 0
        ? options.actions
        : [{ label: label("common.ok"), style: "primary" as const }]
    ).map((action) => ({
      ...action,
      onPress: () => {
        action.onPress?.();
        finish();
      },
    }));
    show({ title: options.title, message: options.message, actions, onDismiss: finish });
  });
}
