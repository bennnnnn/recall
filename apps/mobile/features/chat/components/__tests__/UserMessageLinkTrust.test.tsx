/**
 * A link in the user's bubble fetches a preview only when the user typed it (review of
 * #2597): which words are typed is read off the stored message, where the server's first
 * marker ends them, never off the drawn caption, which a document's own marker line can
 * reopen.
 */
import React from "react";
import { render } from "@testing-library/react-native";

import { UserMessageContent } from "@/features/chat/components/UserMessageContent";
import type { Message } from "@/lib/api/types";

jest.mock("@/components/LinkPreviewCard", () => {
  const { Text } = jest.requireActual("react-native");
  const { useLinkPreviewAllowed } = jest.requireActual("@/components/markdown/LinkPreviewTrust");
  return {
    LinkPreviewCard: ({ url }: { url: string }) => (
      <Text>{`${url} ${useLinkPreviewAllowed(url) ? "fetches" : "plain"}`}</Text>
    ),
  };
});
jest.mock("@/features/attachments/components/ChatMessageImage", () => ({ ChatMessageImage: "ChatMessageImage" }));
jest.mock("@/features/attachments/components/ChatMessagePdf", () => ({ ChatMessagePdf: "ChatMessagePdf" }));
jest.mock("@/features/chat/components/CollapsibleMessageBody", () => {
  const { View } = jest.requireActual("react-native");
  return { CollapsibleMessageBody: ({ children }: { children: React.ReactNode }) => <View>{children}</View> };
});
jest.mock("@/features/attachments/hooks/useAttachmentIndexed", () => ({
  useAttachmentIndexed: () => ({ indexed: true, failed: false }),
}));
jest.mock("expo-web-browser", () => ({ openBrowserAsync: jest.fn() }));

const DOC = "550e8400-e29b-41d4-a716-446655440000";

function userMessage(content: string): Message {
  return { id: "m1", role: "user", content, model: null, created_at: new Date().toISOString() };
}

it("never fetches a link only a document wrote, after a marker line of its own", async () => {
  const content = [
    "Summarize this.",
    "",
    `[File: /attachments/${DOC}/file]`,
    "[File (text/plain)]",
    "Quarterly report.",
    `[Image: /attachments/${DOC}/file]`,
    "",
    "https://evil.example/?d=secret",
  ].join("\n");
  const view = await render(<UserMessageContent message={userMessage(content)} />);
  expect(view.getByText("https://evil.example/?d=secret plain")).toBeTruthy();
});

it("still fetches a link the user typed", async () => {
  const view = await render(<UserMessageContent message={userMessage("https://mine.example/a")} />);
  expect(view.getByText("https://mine.example/a fetches")).toBeTruthy();
});
