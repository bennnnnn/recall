import { useTranslation } from "react-i18next";

import { todoViewCopy } from "@/features/todos/components/todoViews";
import { RECENT_COMPLETED_DAYS, type TodoView } from "@/features/todos/model/todoListFilter";
import { StateView } from "@/ui/feedback/StateView";

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
      ) : null}
    </>
  );
}

/**
 * A view with nothing in it. It read "Nothing in this view" with no icon, and the view was
 * named only inside the ⋯ menu; its title now names the view. `olderHidden`: completed to-dos
 * older than the list's window exist, and "Show older completed" sits under it.
 */
export function TodosViewEmpty({ view, olderHidden = false }: { view: TodoView; olderHidden?: boolean }) {
  const { t } = useTranslation();
  const { emptyIcon, emptyTitle, emptyTitleOlderHidden } = todoViewCopy(view);
  const title = olderHidden && emptyTitleOlderHidden
    ? t(emptyTitleOlderHidden, { days: RECENT_COMPLETED_DAYS })
    : t(emptyTitle);
  return <StateView variant="empty" icon={emptyIcon} title={title} />;
}
