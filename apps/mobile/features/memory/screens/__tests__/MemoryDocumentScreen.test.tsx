import { fireEvent, render } from "@testing-library/react-native";

import MemoryDocumentScreen from "@/features/memory/screens/MemoryDocumentScreen";
import type { MemoryDocument } from "@/features/memory/types";

let mockKey = "area:recall";
const mockLoad = jest.fn(async () => {});
const mockInstruct = jest.fn();
const mockDeleteDocument = jest.fn();
const mockDeleteFact = jest.fn();
const mockEditFact = jest.fn();
const mockConfirm = jest.fn(async () => true);
const mockFeedback = { error: jest.fn(), success: jest.fn() };
const mockRouter = { back: jest.fn(), push: jest.fn() };
let mockDocuments: MemoryDocument[] = [];
let mockLoading = false;

jest.mock("@/lib/auth", () => ({ getSessionGeneration: () => 1 }));
jest.mock("@/contexts/AuthContext", () => ({ useAuth: () => ({ token: "token-a" }) }));
jest.mock("@/contexts/actionFeedbackCore", () => ({ useActionFeedbackOptional: () => mockFeedback }));
jest.mock("@/lib/reportRecoverableError", () => ({
  reportRecoverableError: (_feedback: unknown, message: string) => mockFeedback.error(message),
}));
jest.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (key: string) => key, i18n: { language: "en" } }),
}));
jest.mock("@/lib/theme", () => ({ useTheme: () => ({}) }));
jest.mock("@/ui/icons/Icon", () => ({ Icon: () => null }));
jest.mock("@/ui/feedback/SkeletonLoader", () => ({ SkeletonList: () => null }));
jest.mock("@/ui/feedback/StateView", () => ({
  StateView: ({ title, onRetry }: { title: string; onRetry?: () => void }) => {
    const { Text } = jest.requireActual("react-native");
    return <Text onPress={onRetry}>{title}</Text>;
  },
}));
jest.mock("@/ui/overlay/dialogs", () => ({ confirmDialog: (...args: unknown[]) => mockConfirm(...args) }));
jest.mock("@/ui/overlay/Menu", () => ({
  Menu: ({ visible, items }: { visible: boolean; items: { key: string; label: string; onPress: () => void }[] }) => {
    const { Text, View } = jest.requireActual("react-native");
    if (!visible) return null;
    return (
      <View testID="memory-fact-menu">
        {items.map((item) => (
          <Text key={item.key} onPress={item.onPress} testID={`menu-${item.key}`}>
            {item.label}
          </Text>
        ))}
      </View>
    );
  },
}));
jest.mock("@/components/settings/SettingsFieldSheet", () => ({
  SettingsFieldSheet: ({
    visible,
    value,
    onChangeText,
    onSave,
  }: {
    visible: boolean;
    value: string;
    onChangeText: (text: string) => void;
    onSave: () => void;
  }) => {
    const { Text, TextInput, View } = jest.requireActual("react-native");
    if (!visible) return null;
    return (
      <View>
        <TextInput testID="edit-field" value={value} onChangeText={onChangeText} />
        <Text testID="edit-save" onPress={onSave}>save</Text>
      </View>
    );
  },
}));
jest.mock("expo-router", () => ({
  Redirect: () => null,
  useRouter: () => mockRouter,
  useLocalSearchParams: () => ({ key: mockKey }),
  useFocusEffect: (effect: () => void | (() => void)) => {
    const React = jest.requireActual("react");
    React.useEffect(() => effect(), [effect]);
  },
}));
jest.mock("@/features/memory/hooks/useMemoryDocuments", () => ({
  useMemoryDocuments: () => ({
    documents: mockDocuments,
    loading: mockLoading,
    load: mockLoad,
    instruct: mockInstruct,
    deleteDocument: mockDeleteDocument,
    deleteFact: mockDeleteFact,
    editFact: mockEditFact,
  }),
}));

const fact = (id: string, text: string) => ({
  id,
  type: "project",
  topic: "area:recall",
  text,
  confidence: 0.9,
  created_at: "2026-08-01T00:00:00Z",
  updated_at: "2026-08-21T00:00:00Z",
});

async function flush() {
  await new Promise<void>((resolve) => setImmediate(resolve));
}

beforeEach(() => {
  jest.clearAllMocks();
  mockKey = "area:recall";
  mockLoading = false;
  mockConfirm.mockResolvedValue(true);
  mockDocuments = [
    {
      key: "area:recall",
      group: "areas",
      title: "Recall",
      summary: "Personal AI chat app",
      updated_at: "2026-08-21T00:00:00Z",
      facts: [
        fact("f1", "As of 2026-08-01: User is building Recall with Expo"),
        fact("f2", "Recall uses FastAPI"),
      ],
    },
  ];
});

describe("MemoryDocumentScreen", () => {
  it("shows the page: title, last updated, summary and details", async () => {
    const ui = await render(<MemoryDocumentScreen />);
    expect(ui.getByText("Recall")).toBeTruthy();
    expect(ui.getByText("memory.last_updated")).toBeTruthy();
    expect(ui.getByText("Personal AI chat app")).toBeTruthy();
    // The freshness stamp is the server's, not part of the fact.
    expect(ui.getByText("User is building Recall with Expo")).toBeTruthy();
    expect(ui.getByText("Recall uses FastAPI")).toBeTruthy();
  });

  it("deletes the whole page after confirming", async () => {
    mockDeleteDocument.mockResolvedValue(true);
    const ui = await render(<MemoryDocumentScreen />);
    await fireEvent.press(ui.getByTestId("memory-document-delete"));
    await flush();

    expect(mockConfirm).toHaveBeenCalledWith(expect.objectContaining({ destructive: true }));
    expect(mockDeleteDocument).toHaveBeenCalledWith("area:recall");
    expect(mockRouter.back).toHaveBeenCalled();
  });

  it("keeps the page when delete is cancelled", async () => {
    mockConfirm.mockResolvedValue(false);
    const ui = await render(<MemoryDocumentScreen />);
    await fireEvent.press(ui.getByTestId("memory-document-delete"));
    await flush();
    expect(mockDeleteDocument).not.toHaveBeenCalled();
    expect(mockRouter.back).not.toHaveBeenCalled();
  });

  it("edits one fact from its menu", async () => {
    mockEditFact.mockResolvedValue(true);
    const ui = await render(<MemoryDocumentScreen />);
    await fireEvent.press(ui.getByTestId("memory-fact-f2"), { nativeEvent: { pageX: 10, pageY: 20 } });
    await fireEvent.press(ui.getByTestId("menu-edit"));
    await fireEvent.changeText(ui.getByTestId("edit-field"), "Recall uses FastAPI and Neon");
    await fireEvent.press(ui.getByTestId("edit-save"));
    await flush();

    expect(mockEditFact).toHaveBeenCalledWith("f2", "Recall uses FastAPI and Neon");
    expect(ui.queryByTestId("edit-field")).toBeNull();
  });

  it("deletes one fact from its menu", async () => {
    mockDeleteFact.mockResolvedValue(true);
    const ui = await render(<MemoryDocumentScreen />);
    await fireEvent(ui.getByTestId("memory-fact-f1"), "longPress", { nativeEvent: { pageX: 5, pageY: 5 } });
    await fireEvent.press(ui.getByTestId("menu-delete"));
    await flush();

    expect(mockDeleteFact).toHaveBeenCalledWith("f1");
    // Other facts remain, so the page stays open.
    expect(mockRouter.back).not.toHaveBeenCalled();
  });

  it("sends edits scoped to this page", async () => {
    mockInstruct.mockResolvedValue({ ok: true, reply: "" });
    const ui = await render(<MemoryDocumentScreen />);
    await fireEvent.changeText(ui.getByTestId("memory-composer-input"), "It also uses Neon");
    await fireEvent.press(ui.getByTestId("memory-composer-send"));

    expect(mockInstruct).toHaveBeenCalledWith("It also uses Neon", "area:recall");
    expect(mockFeedback.success).toHaveBeenCalledWith("memory.instruct_done");
  });

  it("loads when opened from a link and says when the page is gone", async () => {
    mockKey = "area:unknown";
    const ui = await render(<MemoryDocumentScreen />);
    expect(mockLoad).toHaveBeenCalled();
    await fireEvent.press(ui.getByText("memory.document_gone"));
    expect(mockRouter.back).toHaveBeenCalled();
  });
});
