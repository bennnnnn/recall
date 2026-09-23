import { useTranslation } from "react-i18next";

import { StateView } from "@/components/StateView";

type Props = {
  error: boolean;
  onRetry: () => void;
  showEmpty: boolean;
};

/** Compact list state; the To-do page intentionally has no calendar wall. */
export function TodosListHeader({
  error,
  onRetry,
  showEmpty,
}: Props) {
  const { t } = useTranslation();

  if (error) {
    return (
      <StateView
        variant="error"
        title={t("common.error")}
        onRetry={onRetry}
        retryLabel={t("common.retry")}
      />
    );
  }
  if (!showEmpty) return null;
  return (
    <StateView
      variant="empty"
      icon="checkmark-circle-outline"
      title={t("todos.empty_title")}
      message={t("todos.empty_body")}
    />
  );
}
