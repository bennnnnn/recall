/**
 * An email card saved with code in its body, as the server stores it
 * (docs/fixtures/fence_body_rewrites.json): the whole reply, through the real markdown
 * pipeline, still draws one email card. Before, a ```` fence holding ``` lines drew as prose,
 * and the draft lost its card, its edit and its Send.
 */
import { render } from "@testing-library/react-native";

import cases from "../../../../../docs/fixtures/fence_body_rewrites.json";
import { MarkdownContent } from "@/components/MarkdownContent";
import "@/lib/i18n";

jest.unmock("react-i18next");
jest.mock("@/components/LinkPreviewCard", () => {
  const { Text } = jest.requireActual("react-native") as typeof import("react-native");
  return { LinkPreviewCard: ({ url }: { url: string }) => <Text>{url}</Text> };
});

type Rewrite = { name: string; expected: string };

it.each(cases as Rewrite[])("$name: the saved reply draws one email card", async ({ expected }) => {
  const { getAllByLabelText } = await render(<MarkdownContent content={expected} />);
  expect(getAllByLabelText("Edit email")).toHaveLength(1);
});
