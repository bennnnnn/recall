import { StyleSheet } from "react-native";
import { fireEvent, render } from "@testing-library/react-native";

import { DrawerHeader } from "@/features/chat/drawer/DrawerHeader";
import { makeConversationListStyles } from "@/features/chat/drawer/conversationListStyles";
import am from "@/lib/i18n/am.json";
import de from "@/lib/i18n/de.json";
import en from "@/lib/i18n/en.json";
import es from "@/lib/i18n/es.json";
import fr from "@/lib/i18n/fr.json";
import itLocale from "@/lib/i18n/it.json";
import pt from "@/lib/i18n/pt.json";
import ru from "@/lib/i18n/ru.json";
import tr from "@/lib/i18n/tr.json";
import { lightTheme } from "@/lib/theme";

jest.mock("@/lib/haptics", () => ({ tap: jest.fn() }));

const props = {
  styles: makeConversationListStyles(lightTheme),
  theme: lightTheme,
  paddingTop: 0,
  searchQuery: "",
  searchInputRef: { current: null },
  onSearchChange: jest.fn(),
  onOpenSearch: jest.fn(),
  onCloseSearch: jest.fn(),
};

// The owner's layout (2026-11-11): Recall's mark at the top left, search at the top right.
it("shows Recall's mark at the left and opens search from the right", async () => {
  const onOpenSearch = jest.fn();
  const view = await render(<DrawerHeader {...props} searchOpen={false} onOpenSearch={onOpenSearch} />);

  expect(view.getByLabelText("app.name")).toBeTruthy();
  expect(view.queryByPlaceholderText("search.placeholder")).toBeNull();
  await fireEvent.press(view.getByRole("search", { name: "search.open_accessibility" }));
  expect(onOpenSearch).toHaveBeenCalledTimes(1);
});

it("becomes the search field across the bar, with Cancel", async () => {
  const onCloseSearch = jest.fn();
  const view = await render(<DrawerHeader {...props} searchOpen onCloseSearch={onCloseSearch} />);

  expect(view.getByPlaceholderText("search.placeholder")).toBeTruthy();
  expect(view.queryByLabelText("app.name")).toBeNull();
  await fireEvent.press(view.getByRole("button", { name: "common.cancel" }));
  expect(onCloseSearch).toHaveBeenCalledTimes(1);
});

// The owner (2026-11-11): titles scrolling up show through the top, dimmed by its fade.
it("lets the titles show through, under the fade", async () => {
  const view = await render(<DrawerHeader {...props} searchOpen={false} />);
  const root = view.toJSON() as unknown as { props: { style: Parameters<typeof StyleSheet.flatten>[0] } };
  expect(StyleSheet.flatten(root.props.style)).toMatchObject({ backgroundColor: "transparent" });
});

// The bar showed "Search messages..." and VoiceOver said "Search conversations".
it.each(Object.entries({ en, am, de, es, fr, it: itLocale, pt, ru, tr }))(
  "is labelled with the words it shows in %s",
  (_code, bundle) => {
    expect(bundle["search.placeholder"]).toBe(`${bundle["search.open_accessibility"]}…`);
  },
);
