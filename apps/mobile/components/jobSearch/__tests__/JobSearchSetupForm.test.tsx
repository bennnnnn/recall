import { Alert } from "react-native";
import { fireEvent, render, waitFor } from "@testing-library/react-native";

import { JobSearchSetupForm } from "@/components/jobSearch/JobSearchSetupForm";

const mockPickDocument = jest.fn();
const mockUpload = jest.fn();
const mockUser = { plan: "pro", job: "Registered Nurse", location: "Berlin" };

jest.mock("@/contexts/AuthContext", () => ({
  useAuth: () => ({ token: "token-a", user: mockUser }),
}));
jest.mock("@/lib/attachments", () => ({
  pickDocument: (...args: unknown[]) => mockPickDocument(...args),
  uploadChatAttachment: (...args: unknown[]) => mockUpload(...args),
}));
jest.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (key: string) => key }),
}));
jest.mock("@/components/Icon", () => ({ Icon: () => null }));
jest.mock("@/components/jobSearch/LocationFields", () => ({
  EMPTY_PLACE: { city: "", region: "", country: "" },
  composePlace: () => "Berlin",
  parsePlace: () => ({ city: "Berlin", region: "", country: "" }),
  LocationFields: () => null,
}));
jest.mock("@/components/jobSearch/SearchableMultiSelect", () => ({
  SearchableMultiSelect: () => null,
}));
jest.mock("@/components/settings/SettingsPickerSheet", () => ({
  SettingsPickerSheet: () => null,
}));
jest.mock("@/components/todos/ReminderDateTimePicker", () => ({
  ReminderDateTimePicker: () => null,
}));
jest.mock("@/components/AppSheet", () => ({
  AppSheet: ({ children }: { children: React.ReactNode }) => {
    const React = jest.requireActual<typeof import("react")>("react");
    const { View } = jest.requireActual("react-native");
    return React.createElement(View, null, children);
  },
}));

beforeEach(() => {
  jest.clearAllMocks();
  jest.spyOn(Alert, "alert").mockImplementation(() => {});
  mockPickDocument.mockResolvedValue({
    localUri: "file:///resume.pdf",
    contentType: "application/pdf",
    fileName: "resume.pdf",
    kind: "file",
  });
});

afterEach(() => jest.restoreAllMocks());

async function reachResumeStep(screen: Awaited<ReturnType<typeof render>>) {
  await fireEvent.press(screen.getByText("common.next"));
  await fireEvent.press(screen.getByText("common.next"));
}

test("always shows localized resume upload failure copy", async () => {
  mockUpload.mockRejectedValue(new Error("raw provider detail"));
  const screen = await render(
    <JobSearchSetupForm
      initial={null}
      busy={false}
      onClose={jest.fn()}
      onSave={jest.fn(async () => false)}
    />,
  );
  await reachResumeStep(screen);
  await fireEvent.press(screen.getByText("my_job.resume_upload_cta"));

  await waitFor(() =>
    expect(Alert.alert).toHaveBeenCalledWith(
      "my_job.resume_upload_failed_title",
      "my_job.resume_upload_failed_body",
    ),
  );
  expect(Alert.alert).not.toHaveBeenCalledWith(
    expect.anything(),
    expect.stringContaining("raw provider detail"),
  );
});

test("keeps setup open when save returns false", async () => {
  const onClose = jest.fn();
  const onSave = jest.fn(async () => false);
  const screen = await render(
    <JobSearchSetupForm
      initial={null}
      busy={false}
      onClose={onClose}
      onSave={onSave}
    />,
  );
  await fireEvent.press(screen.getByText("common.next"));
  await fireEvent.press(screen.getByText("common.next"));
  await fireEvent.press(screen.getByText("common.next"));
  await fireEvent.press(screen.getByText("my_job.start_search"));

  await waitFor(() => expect(onSave).toHaveBeenCalledTimes(1));
  expect(onClose).not.toHaveBeenCalled();
  expect(screen.getByText("my_job.start_search")).toBeTruthy();
});

test("moves through all setup steps and back without saving", async () => {
  const onSave = jest.fn(async () => true);
  const screen = await render(
    <JobSearchSetupForm
      initial={null}
      busy={false}
      onClose={jest.fn()}
      onSave={onSave}
    />,
  );

  expect(screen.getByText("my_job.step0_title")).toBeTruthy();
  await fireEvent.press(screen.getByText("common.next"));
  expect(screen.getByText("my_job.step1_title")).toBeTruthy();
  await fireEvent.press(screen.getByText("common.next"));
  expect(screen.getByText("my_job.step2_title")).toBeTruthy();
  await fireEvent.press(screen.getByText("common.next"));
  expect(screen.getByText("my_job.step3_title")).toBeTruthy();

  await fireEvent.press(screen.getByText("common.back"));

  expect(screen.getByText("my_job.step2_title")).toBeTruthy();
  expect(onSave).not.toHaveBeenCalled();
});
