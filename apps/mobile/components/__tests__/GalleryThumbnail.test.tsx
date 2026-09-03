import { act, fireEvent, render } from "@testing-library/react-native";

import { GalleryThumbnail, LOAD_TIMEOUT_MS } from "@/components/GalleryThumbnail";
import { attachmentRecordExists } from "@/lib/api";
import { lightTheme as mockLightTheme } from "@/lib/theme";

jest.mock("@/contexts/AuthContext", () => ({
  useAuthToken: () => "tok",
}));
jest.mock("@/lib/attachmentUri", () => ({
  resolveAttachmentUri: ({ attachmentId }: { attachmentId: string }) =>
    `http://test.local/${attachmentId}`,
}));
jest.mock("@/lib/api", () => ({
  attachmentRecordExists: jest.fn(async () => true),
}));
jest.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (key: string) => key }),
}));
jest.mock("@expo/vector-icons", () => ({
  Ionicons: "Ionicons",
}));
jest.mock("@/lib/theme", () => ({
  ...jest.requireActual("@/lib/theme"),
  useTheme: () => mockLightTheme,
}));

const mockExists = attachmentRecordExists as jest.MockedFunction<
  typeof attachmentRecordExists
>;

describe("GalleryThumbnail", () => {
  beforeEach(() => {
    jest.useFakeTimers();
    mockExists.mockReset();
    mockExists.mockResolvedValue(true);
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

  it("keeps the row and shows Retry after a load timeout", async () => {
    const onMissing = jest.fn();
    const { getByTestId, queryByTestId } = await render(
      <GalleryThumbnail attachmentId="slow" size={40} onMissing={onMissing} />,
    );
    await act(async () => {
      jest.advanceTimersByTime(LOAD_TIMEOUT_MS);
    });
    expect(onMissing).not.toHaveBeenCalled();
    expect(mockExists).not.toHaveBeenCalled();
    expect(queryByTestId("gallery-thumb-image")).toBeNull();
    expect(getByTestId("media-load-retry")).toBeTruthy();
  });

  it("keeps the row and shows Retry on error when the record still exists", async () => {
    const onMissing = jest.fn();
    const { getByTestId, queryByTestId } = await render(
      <GalleryThumbnail attachmentId="flaky" size={40} onMissing={onMissing} />,
    );
    await act(async () => {
      getByTestId("gallery-thumb-image").props.onError();
    });
    expect(onMissing).not.toHaveBeenCalled();
    expect(queryByTestId("gallery-thumb-image")).toBeNull();
    expect(getByTestId("media-load-retry")).toBeTruthy();
  });

  it("drops the row only after the server confirms it is gone", async () => {
    mockExists.mockResolvedValue(false);
    const onMissing = jest.fn();
    const { getByTestId } = await render(
      <GalleryThumbnail attachmentId="gone" size={40} onMissing={onMissing} />,
    );
    await act(async () => {
      getByTestId("gallery-thumb-image").props.onError();
    });
    expect(onMissing).toHaveBeenCalledTimes(1);
    expect(onMissing).toHaveBeenCalledWith("gone");
  });

  it("reloads the image when Retry is pressed", async () => {
    const { getByTestId, queryByTestId } = await render(
      <GalleryThumbnail attachmentId="flaky" size={40} />,
    );
    await act(async () => {
      getByTestId("gallery-thumb-image").props.onError();
    });
    expect(queryByTestId("gallery-thumb-image")).toBeNull();
    await fireEvent.press(getByTestId("media-load-retry"));
    expect(getByTestId("gallery-thumb-image")).toBeTruthy();
  });
});
