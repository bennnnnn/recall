import { useTranslation } from "react-i18next";

import { todoViewCopy } from "@/features/todos/components/todoViews";
import type { TodoView } from "@/features/todos/model/todoListFilter";
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
 * A view with nothing in it while other to-dos exist. It read "Nothing in this view" with no
 * icon, and the view was named only inside the ⋯ menu; its title now names the view.
 */
export function TodosViewEmpty({ view }: { view: TodoView }) {
  const { t } = useTranslation();
  const { emptyIcon, emptyTitle } = todoViewCopy(view);
  return <StateView variant="empty" icon={emptyIcon} title={t(emptyTitle)} />;
}
