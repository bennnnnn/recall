import type { RefObject } from "react";
import type { HostInstance } from "react-native";
import { useTranslation } from "react-i18next";

import { Menu } from "@/ui/overlay/Menu";

/**
 * To-do list ⋮: start selecting. The list is one list of sections; the views it held
 * (All, Not completed, Completed, Today) hid to-dos, and Today opened on "Nothing due today"
 * while undated ones existed.
 */
export function TodosListMenu({
  visible,
  anchorRef,
  onSelect,
  onClose,
}: {
  visible: boolean;
  anchorRef: RefObject<HostInstance | null>;
  onSelect: () => void;
  onClose: () => void;
}) {
  const { t } = useTranslation();

  return (
    <Menu
      visible={visible}
      onClose={onClose}
      anchorRef={anchorRef}
      testID="todos-list-menu"
      items={[
        { key: "select", icon: "select", label: t("todos.menu_select"), onPress: onSelect },
      ]}
    />
  );
}
