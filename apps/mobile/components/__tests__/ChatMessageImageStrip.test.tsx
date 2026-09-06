import { render } from "@testing-library/react-native";

import { ChatMessageImageStrip } from "@/components/ChatMessageImageStrip";

jest.mock("@/components/ChatMessageImage", () => {
  const { View: MockView } = jest.requireActual("react-native");
  return {
    ChatMessageImage: ({ attachmentId }: { attachmentId?: string | null }) => (
      <MockView testID={`chat-message-image-${attachmentId ?? "local"}`} />
    ),
  };
});

const twoCars = [
  { attachmentId: "a", path: "/attachments/a/file" },
  { attachmentId: "b", path: "/attachments/b/file" },
];

describe("ChatMessageImageStrip", () => {
  it("does not render a scroller for a single image", async () => {
    const { queryByTestId, getByTestId } = await render(
      <ChatMessageImageStrip images={[{ attachmentId: "a", path: "/attachments/a/file" }]} />,
    );

    expect(queryByTestId("chat-image-strip")).toBeNull();
    expect(getByTestId("chat-message-image-a")).toBeOnTheScreen();
  });

  it("puts two or more images in a horizontal snap scroller", async () => {
    const { getByTestId } = await render(<ChatMessageImageStrip images={twoCars} />);

    const strip = getByTestId("chat-image-strip");
    expect(strip.props.horizontal).toBe(true);
    expect(strip.props.showsHorizontalScrollIndicator).toBe(false);
    expect(strip.props.snapToInterval).toBeGreaterThan(0);
    expect(getByTestId("chat-message-image-a")).toBeOnTheScreen();
    expect(getByTestId("chat-message-image-b")).toBeOnTheScreen();
  });

  it("renders nothing when there are no images", async () => {
    const { toJSON } = await render(<ChatMessageImageStrip images={[]} />);
    expect(toJSON()).toBeNull();
  });
});
