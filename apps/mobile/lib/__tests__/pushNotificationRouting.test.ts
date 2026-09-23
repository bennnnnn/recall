jest.mock("@/lib/api", () => ({
  api: {
    registerPushToken: jest.fn(),
    unregisterPushToken: jest.fn(),
    recordProductEvents: jest.fn(),
    updateMe: jest.fn(),
  },
}));

jest.mock("@/lib/installationId", () => ({
  getInstallationId: jest.fn().mockResolvedValue("dev-1"),
}));

jest.mock("expo-constants", () => ({
  __esModule: true,
  default: { expoConfig: { extra: { eas: { projectId: "p1" } } } },
}));

jest.mock("expo-notifications", () => ({
  getPermissionsAsync: jest.fn(),
  requestPermissionsAsync: jest.fn(),
  setNotificationChannelAsync: jest.fn(),
  getExpoPushTokenAsync: jest.fn(),
  setNotificationHandler: jest.fn(),
}));

jest.mock("react-native", () => ({
  Platform: { OS: "ios" },
  AppState: { addEventListener: () => ({ remove: jest.fn() }) },
}));

import { handlePushNotificationResponse } from "@/lib/pushNotifications";

function fakeRouter() {
  return { push: jest.fn(), replace: jest.fn() };
}

describe("handlePushNotificationResponse: job_search_ready", () => {
  it("opens the dedicated My Job dashboard", async () => {
    const router = fakeRouter();
    await handlePushNotificationResponse(router, {
      type: "job_search_ready",
      screen: "my-job",
      profile_id: "profile-1",
    });
    expect(router.push).toHaveBeenCalledWith("/my-job");
  });

  it("also routes on the dedicated screen value", async () => {
    const router = fakeRouter();
    await handlePushNotificationResponse(router, { screen: "my-job" });
    expect(router.push).toHaveBeenCalledWith("/my-job");
  });
});

describe("handlePushNotificationResponse: learning + suggestions", () => {
  it("sends learning pushes straight to the lesson map", async () => {
    const router = fakeRouter();
    await handlePushNotificationResponse(router, {
      type: "learning_review",
      project_id: "p1",
    });
    expect(router.push).toHaveBeenCalledWith("/projects/p1/lesson");
  });

  it("routes email suggestions to To-do even when a project id is present", async () => {
    const router = fakeRouter();
    await handlePushNotificationResponse(router, {
      type: "email_suggestion",
      project_id: "p1",
    });
    expect(router.push).toHaveBeenCalledWith("/todos");
  });

  it("carries event context into To-do for calendar nudges", async () => {
    const router = fakeRouter();
    await handlePushNotificationResponse(router, {
      type: "calendar_nudge",
      event_id: "event-1",
      event_title: "Design review",
      event_start: "2026-09-18T17:30:00.000Z",
    });
    const href = router.push.mock.calls[0][0] as {
      pathname: string;
      params: { eventId: string; eventTitle: string; eventStart: string };
    };
    expect(href.pathname).toBe("/todos");
    expect(href.params).toEqual({
      eventId: "event-1",
      eventTitle: "Design review",
      eventStart: "2026-09-18T17:30:00.000Z",
    });
  });

  it("falls back to chat for a legacy nudge with no event context", async () => {
    const router = fakeRouter();
    await handlePushNotificationResponse(router, { type: "calendar_nudge" });
    expect(router.push).toHaveBeenCalledWith("/");
  });
});

describe("handlePushNotificationResponse: already on target", () => {
  it("replaces instead of stacking a duplicate route", async () => {
    const router = fakeRouter();
    await handlePushNotificationResponse(
      router,
      { type: "todo_due", todo_id: "t1" },
      "/todos",
    );
    expect(router.push).not.toHaveBeenCalled();
    expect(router.replace).toHaveBeenCalledWith({
      pathname: "/todos",
      params: { highlight: "t1" },
    });
  });
});
