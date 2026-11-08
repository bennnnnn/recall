import type { RefObject } from "react";
import type { HostInstance } from "react-native";
import { useTranslation } from "react-i18next";

import { TODO_VIEWS } from "@/features/todos/components/todoViews";
import type { TodoView } from "@/features/todos/model/todoListFilter";
import { Menu } from "@/ui/overlay/Menu";

/** To-do list ⋮: start selecting, or switch which to-dos the list shows. */
export function TodosViewMenu({
  visible,
  view,
  anchorRef,
  onView,
  onSelect,
  onClose,
}: {
  visible: boolean;
  view: TodoView;
  anchorRef: RefObject<HostInstance | null>;
  onView: (view: TodoView) => void;
  onSelect: () => void;
  onClose: () => void;
}) {
  const { t } = useTranslation();

  return (
    <Menu
      visible={visible}
      onClose={onClose}
      anchorRef={anchorRef}
      testID="todos-view-menu"
      items={[
        { key: "select", icon: "select", label: t("todos.menu_select"), onPress: onSelect },
        "separator",
        ...TODO_VIEWS.map((item) => ({
          key: item.id,
          label: t(item.label),
          selected: item.id === view,
          onPress: () => onView(item.id),
        })),
      ]}
    />
  );
}
