import { act, render } from "@testing-library/react-native";

import { GalleryThumbnail } from "@/components/GalleryThumbnail";
import { lightTheme as mockLightTheme } from "@/lib/theme";

jest.mock("@/contexts/AuthContext", () => ({
  useAuthToken: () => "tok",
}));
jest.mock("@/lib/attachmentUri", () => ({
  resolveAttachmentUri: ({ attachmentId }: { attachmentId: string }) =>
    `http://test.local/${attachmentId}`,
}));
jest.mock("@expo/vector-icons", () => ({
  Ionicons: "Ionicons",
}));
jest.mock("@/lib/theme", () => ({
  ...jest.requireActual("@/lib/theme"),
  useTheme: () => mockLightTheme,
}));

describe("GalleryThumbnail", () => {
  beforeEach(() => {
    jest.useFakeTimers();
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  it("resets loading when the attachment id changes", async () => {
    const { getByTestId, queryByTestId, rerender } = await render(
      <GalleryThumbnail attachmentId="a" size={40} />,
    );
    expect(getByTestId("gallery-thumb-loading")).toBeTruthy();

    await act(async () => {
      getByTestId("gallery-thumb-image").props.onLoad();
    });
    expect(queryByTestId("gallery-thumb-loading")).toBeNull();

    await act(async () => {
      rerender(<GalleryThumbnail attachmentId="b" size={40} />);
    });
    expect(getByTestId("gallery-thumb-loading")).toBeTruthy();
  });

  it("sends Bearer on /file even when downloadUrl is an absolute R2 URL", async () => {
    const { getByTestId } = await render(
      <GalleryThumbnail
        attachmentId="a"
        downloadUrl="https://r2.example/presigned"
        size={40}
      />,
    );
    expect(getByTestId("gallery-thumb-image").props.source.headers).toEqual({
      Authorization: "Bearer tok",
    });
  });

  it("keeps a loaded image after the timeout", async () => {
    const { getByTestId, queryByTestId } = await render(
      <GalleryThumbnail attachmentId="a" size={40} />,
    );
    await act(async () => {
      getByTestId("gallery-thumb-image").props.onLoad();
    });
    await act(async () => {
      jest.advanceTimersByTime(10_000);
    });
    expect(getByTestId("gallery-thumb-image")).toBeTruthy();
    expect(queryByTestId("gallery-thumb-loading")).toBeNull();
  });
});
