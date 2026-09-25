import { useTranslation } from "react-i18next";

import { StateView } from "@/ui/feedback/StateView";
import {
  CalendarNudgeCard,
  type CalendarNudge,
} from "@/features/todos/components/CalendarNudgeCard";

type Props = {
  error: boolean;
  onRetry: () => void;
  showEmpty: boolean;
  calendarNudge?: CalendarNudge | null;
};

/** Compact list state; the To-do page intentionally has no calendar wall. */
export function TodosListHeader({
  error,
  onRetry,
  showEmpty,
  calendarNudge,
}: Props) {
  const { t } = useTranslation();

  return (
    <>
      {calendarNudge ? <CalendarNudgeCard event={calendarNudge} /> : null}
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
          icon="checkmark-circle-outline"
          title={t("todos.empty_title")}
        />
      ) : null}
    </>
  );
}
