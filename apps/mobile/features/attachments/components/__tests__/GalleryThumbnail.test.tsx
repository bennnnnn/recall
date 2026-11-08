import { act, fireEvent, render } from "@testing-library/react-native";

import { GalleryThumbnail, LOAD_TIMEOUT_MS } from "@/features/attachments/components/GalleryThumbnail";
import { attachmentRecordExists } from "@/lib/api";
import { lightTheme as mockLightTheme } from "@/lib/theme";

jest.mock("@/contexts/AuthContext", () => ({
  useAuthToken: () => "tok",
}));
jest.mock("@/lib/config", () => ({ getApiUrl: () => "http://test.local" }));
jest.mock("@/lib/api", () => ({
  attachmentRecordExists: jest.fn(async () => true),
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

  it("sends Bearer to the API's own /file", async () => {
    const { getByTestId } = await render(<GalleryThumbnail attachmentId="a" size={40} />);
    const { source } = getByTestId("gallery-thumb-image").props;
    expect(source.uri).toBe("http://test.local/attachments/a/file?w=80");
    expect(source.headers).toEqual({ Authorization: "Bearer tok" });
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

  it("keeps loading while the image arrives, and shows Retry once it stalls", async () => {
    const { getByTestId, queryByTestId } = await render(
      <GalleryThumbnail attachmentId="slow" size={40} />,
    );
    const progress = (loaded: number) =>
      getByTestId("gallery-thumb-image").props.onProgress({ loaded, total: 100 });
    await act(async () => {
      jest.advanceTimersByTime(LOAD_TIMEOUT_MS - 1_000);
      progress(40);
      jest.advanceTimersByTime(LOAD_TIMEOUT_MS - 1_000);
      progress(80);
      jest.advanceTimersByTime(LOAD_TIMEOUT_MS - 1_000);
    });
    // Three timeouts' worth since mount, never one without progress.
    expect(queryByTestId("media-load-retry")).toBeNull();
    expect(getByTestId("gallery-thumb-loading")).toBeTruthy();
    await act(async () => {
      jest.advanceTimersByTime(1_000);
    });
    expect(getByTestId("media-load-retry")).toBeTruthy();
  });

  it("starts the clock when the load starts, not when the tile mounts", async () => {
    const { getByTestId, queryByTestId } = await render(
      <GalleryThumbnail attachmentId="queued" size={40} />,
    );
    await act(async () => {
      jest.advanceTimersByTime(LOAD_TIMEOUT_MS - 1_000);
      getByTestId("gallery-thumb-image").props.onLoadStart();
      jest.advanceTimersByTime(LOAD_TIMEOUT_MS - 1_000);
    });
    expect(queryByTestId("media-load-retry")).toBeNull();
  });

  it("never turns a loaded image into Retry on a late progress event", async () => {
    const { getByTestId, queryByTestId } = await render(
      <GalleryThumbnail attachmentId="a" size={40} />,
    );
    await act(async () => {
      getByTestId("gallery-thumb-image").props.onLoad();
      getByTestId("gallery-thumb-image").props.onProgress({ loaded: 100, total: 100 });
      jest.advanceTimersByTime(LOAD_TIMEOUT_MS * 2);
    });
    expect(queryByTestId("media-load-retry")).toBeNull();
    expect(getByTestId("gallery-thumb-image")).toBeTruthy();
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

  it("asks for a 2x thumbnail, capped at the 512px the API serves", async () => {
    const phone = await render(<GalleryThumbnail attachmentId="a" size={120} />);
    expect(phone.getByTestId("gallery-thumb-image").props.source.uri)
      .toBe("http://test.local/attachments/a/file?w=240");
    const tablet = await render(<GalleryThumbnail attachmentId="b" size={400} />);
    expect(tablet.getByTestId("gallery-thumb-image").props.source.uri)
      .toBe("http://test.local/attachments/b/file?w=512");
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
