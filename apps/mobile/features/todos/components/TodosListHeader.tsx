import { useTranslation } from "react-i18next";

import { StateView } from "@/ui/feedback/StateView";

type Props = {
  error: boolean;
  onRetry: () => void;
  /** No to-dos at all: "No to-dos yet". */
  showEmpty: boolean;
  /** Every to-do is completed: "Nothing left to do" over the folded Completed heading, which
   * alone read as an empty page. */
  allDone?: boolean;
};

/** Compact list state; the To-do page intentionally has no calendar wall. */
export function TodosListHeader({
  error,
  onRetry,
  showEmpty,
  allDone = false,
}: Props) {
  const { t } = useTranslation();

  return (
    <>
      {error ? (
        <StateView
          variant="error"
          title={t("common.error")}
          onRetry={onRetry}
          retryLabel={t("common.retry")}
        />
      ) : showEmpty ? (
        <StateView
          variant="empty"
          icon="check-circle"
          title={t("todos.empty_title")}
        />
      ) : allDone ? (
        <StateView
          variant="empty"
          compact
          icon="check-circle"
          title={t("todos.empty_open")}
        />
      ) : null}
    </>
  );
}
