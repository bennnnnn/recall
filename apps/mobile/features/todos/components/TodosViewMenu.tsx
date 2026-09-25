import { useMemo } from "react";
import { useTranslation } from "react-i18next";

import { SettingsPickerSheet } from "@/components/settings/SettingsPickerSheet";
import type { TodoView } from "@/features/todos/model/todoListFilter";

const VIEWS: { id: TodoView; label: string }[] = [
  { id: "all", label: "todos.menu_all" },
  { id: "open", label: "todos.menu_open" },
  { id: "completed", label: "todos.menu_completed" },
  { id: "today", label: "todos.menu_today" },
];

export function TodosViewMenu({
  view,
  onView,
  onSelect,
  onClose,
}: {
  view: TodoView;
  onView: (view: TodoView) => void;
  onSelect: () => void;
  onClose: () => void;
}) {
  const { t } = useTranslation();
  const options = useMemo(
    () => [
      { key: "select", label: t("todos.menu_select") },
      ...VIEWS.map((item) => ({ key: item.id, label: t(item.label) })),
    ],
    [t],
  );

  return (
    <SettingsPickerSheet
      visible
      options={options}
      selectedKey={view}
      onSelect={(key) => {
        if (key === "select") onSelect();
        else onView(key as TodoView);
      }}
      onClose={onClose}
    />
  );
}
