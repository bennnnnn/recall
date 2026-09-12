import { render } from "@testing-library/react-native";

import { Avatar } from "@/components/Avatar";

jest.mock("@/lib/config", () => ({ getApiUrl: () => "https://api.recall.test" }));

describe("profile photo loading", () => {
  it("authenticates an uploaded photo on Recall's API", async () => {
    const { getByTestId } = await render(
      <Avatar name="Bini" uri="/attachments/11111111-1111-4111-8111-111111111111/file" token="test-token" />,
    );
    expect(getByTestId("avatar-image").props.source).toEqual({
      uri: "https://api.recall.test/attachments/11111111-1111-4111-8111-111111111111/file",
      headers: { Authorization: "Bearer test-token" },
    });
  });

  it.each(["https://provider.test/photo.jpg", "file:///local-preview.jpg"])(
    "does not send account credentials to %s",
    async (uri) => {
      const { getByTestId } = await render(<Avatar name="Bini" uri={uri} token="test-token" />);
      expect(getByTestId("avatar-image").props.source).toEqual({ uri, headers: {} });
    },
  );
});
