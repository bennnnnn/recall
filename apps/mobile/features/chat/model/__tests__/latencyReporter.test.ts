import { reportChatTurnOutcome } from "@/features/chat/model/latencyReporter";
import { analyticsApi } from "@/lib/api/analytics";

jest.mock("react-native", () => ({ Platform: { OS: "ios" } }));
jest.mock("expo-constants", () => ({ expoConfig: { version: "1.2.3" } }));
jest.mock("@/lib/auth", () => ({ getToken: jest.fn(async () => "tok") }));
jest.mock("@/lib/installationId", () => ({ getInstallationId: jest.fn(async () => "install-1") }));
jest.mock("@/lib/api/analytics", () => ({
  analyticsApi: { recordProductEvents: jest.fn(async () => undefined) },
}));

describe("reportChatTurnOutcome", () => {
  it("sends one chat_turn_outcome event holding only its enumerated properties", async () => {
    await reportChatTurnOutcome({ completion: "error", error_code: "busy", tool: "searching" });

    const record = analyticsApi.recordProductEvents as jest.Mock;
    expect(record).toHaveBeenCalledTimes(1);
    const [token, events] = record.mock.calls[0];
    expect(token).toBe("tok");
    expect(events).toEqual([
      expect.objectContaining({
        name: "chat_turn_outcome",
        properties: { completion: "error", error_code: "busy", tool: "searching" },
        platform: "ios",
        app_version: "1.2.3",
        installation_id: "install-1",
      }),
    ]);
  });
});
