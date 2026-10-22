import { reportChatTtft, reportChatTurnOutcome } from "@/features/chat/model/latencyReporter";
import { analyticsApi } from "@/lib/api/analytics";

jest.mock("react-native", () => ({ Platform: { OS: "ios" } }));
jest.mock("expo-constants", () => ({ expoConfig: { version: "1.2.3" } }));
jest.mock("@/lib/auth", () => ({ getToken: jest.fn(async () => "tok") }));
jest.mock("@/lib/installationId", () => ({ getInstallationId: jest.fn(async () => "install-1") }));
jest.mock("@/lib/api/analytics", () => ({
  analyticsApi: { recordProductEvents: jest.fn(async () => undefined) },
}));

const record = analyticsApi.recordProductEvents as jest.Mock;

describe("reportChatTurnOutcome", () => {
  beforeEach(() => record.mockClear());

  it("sends one chat_turn_outcome event holding only its enumerated properties", async () => {
    await reportChatTurnOutcome({
      completion: "error", error_code: "busy", tool: "searching", send_ready_bucket: "100_249",
    });

    expect(record).toHaveBeenCalledTimes(1);
    const [token, events] = record.mock.calls[0];
    expect(token).toBe("tok");
    expect(events).toEqual([
      expect.objectContaining({
        name: "chat_turn_outcome",
        properties: { completion: "error", error_code: "busy", tool: "searching", send_ready_bucket: "100_249" },
        platform: "ios",
        app_version: "1.2.3",
        installation_id: "install-1",
      }),
    ]);
  });
});

describe("reportChatTtft", () => {
  beforeEach(() => record.mockClear());

  it.each([
    [{ paintBucket: "lt50" as const }, { paint_bucket: "lt50" }],
    [{}, {}],
  ])("sends the paint bucket only when it was measured (%o)", async (paint, expected) => {
    await reportChatTtft({ latencyBucket: "500_999", transport: "ws", hasAttachment: false, ...paint });
    expect(record.mock.calls[0][1][0].properties).toEqual({
      latency_bucket: "500_999",
      transport: "ws",
      has_attachment: "no",
      ...expected,
    });
  });
});
