import { isAllowedImageUri } from "@/lib/imageUriPolicy";

describe("isAllowedImageUri", () => {
  it("allows https, data, and blob schemes", () => {
    expect(isAllowedImageUri("https://upload.wikimedia.org/wikipedia/x.png")).toBe(true);
    expect(isAllowedImageUri("https://cdn.example.com/img.webp")).toBe(true);
    expect(isAllowedImageUri("data:image/png;base64,iVBORw0KGgo=")).toBe(true);
    expect(isAllowedImageUri("blob:https://example.com/uuid")).toBe(true);
  });

  it("blocks insecure and local-file schemes", () => {
    expect(isAllowedImageUri("http://tracker.example.com/pixel.gif")).toBe(false);
    expect(isAllowedImageUri("file:///etc/passwd")).toBe(false);
    expect(isAllowedImageUri("content://media/external/images/1")).toBe(false);
    expect(isAllowedImageUri("ws://evil.example.com/exfil")).toBe(false);
    expect(isAllowedImageUri("javascript:alert(1)")).toBe(false);
  });

  it("blocks empty / malformed / bare inputs", () => {
    expect(isAllowedImageUri(undefined)).toBe(false);
    expect(isAllowedImageUri(null)).toBe(false);
    expect(isAllowedImageUri("")).toBe(false);
    expect(isAllowedImageUri("   ")).toBe(false);
    expect(isAllowedImageUri("not-a-url")).toBe(false);
    expect(isAllowedImageUri("/local/path.png")).toBe(false);
  });
});
