import { useLayoutEffect, type ReactElement, type RefObject } from "react";
import { Pressable, Text, type HostInstance } from "react-native";
import { useNavigation } from "expo-router";
import { useTranslation } from "react-i18next";

import { TodosHeaderTitle } from "@/features/todos/components/TodosHeaderTitle";
import type { TodoView } from "@/features/todos/model/todoListFilter";
import { useLatestRef } from "@/lib/latestRef";
import { useTheme } from "@/lib/theme";
import { Type } from "@/lib/type";
import { HeaderButton } from "@/ui/controls/HeaderButton";
import { plainHeaderItems, StackBackButton } from "@/ui/controls/StackBackButton";
import { SheetCover } from "@/ui/overlay/Sheet";

type Params = {
  /** The list's view, named under the title; none on a to-do's own page. */
  view: TodoView;
  /** A to-do's own page is open (`editingId` once its to-do is known). */
  detailOpen: boolean;
  editingId: string | null;
  selecting: boolean;
  /** The new to-do sheet is up: a screen reader skips the header under it, as it skips the list. */
  covered: boolean;
  /** The ⋯ button, which the list's and the to-do's menus drop from. */
  menuAnchorRef: RefObject<HostInstance | null>;
  /** Back from a to-do's page to the list. */
  onLeaveDetail: () => void;
  /** ⋯, or Done while selecting. */
  onMenu: () => void;
};

/**
 * The To-do header: back (to the list, on a to-do's page), the title with the list's view
 * under it, and ⋯ (Done while selecting). The native header keeps the first button it
 * mounted, so a press goes through the latest handlers.
 */
export function useTodosHeader({
  view,
  detailOpen,
  editingId,
  selecting,
  covered,
  menuAnchorRef,
  onLeaveDetail,
  onMenu,
}: Params) {
  const navigation = useNavigation();
  const { t } = useTranslation();
  const C = useTheme();
  const handlers = useLatestRef({ onLeaveDetail, onMenu });

  useLayoutEffect(() => {
    const cover = (element: ReactElement) => <SheetCover covered={covered}>{element}</SheetCover>;
    const headerLeftElement = cover(
      detailOpen ? (
        <HeaderButton
          icon="arrow-left"
          variant="plain"
          accessibilityLabel={t("common.back")}
          onPress={() => handlers.current.onLeaveDetail()}
        />
      ) : (
        <StackBackButton />
      ),
    );
    let headerRightElement: ReactElement | null = null;
    if (!(detailOpen && !editingId)) {
      headerRightElement = cover(
        !detailOpen && selecting ? (
          <Pressable
            onPress={() => handlers.current.onMenu()}
            accessibilityRole="button"
            accessibilityLabel={t("todos.selection_done")}
            hitSlop={12}
          >
            <Text style={[Type.body, { color: C.primary }]}>{t("todos.selection_done")}</Text>
          </Pressable>
        ) : (
          <HeaderButton
            ref={menuAnchorRef}
            icon="more-horizontal"
            variant="plain"
            accessibilityLabel={detailOpen ? t("todos.detail_menu") : t("todos.menu")}
            onPress={() => handlers.current.onMenu()}
          />
        ),
      );
    }
    navigation.setOptions({
      headerTitle: () => cover(<TodosHeaderTitle view={detailOpen ? null : view} />),
      headerStyle: { backgroundColor: detailOpen ? C.surface : C.bg },
      headerShadowVisible: false,
      headerLeft: () => headerLeftElement,
      unstable_headerLeftItems: () => plainHeaderItems(headerLeftElement),
      headerRight: () => headerRightElement,
      unstable_headerRightItems: () => plainHeaderItems(headerRightElement),
    });
  }, [navigation, t, selecting, detailOpen, editingId, view, covered, menuAnchorRef, handlers, C.primary, C.surface, C.bg]);
}
