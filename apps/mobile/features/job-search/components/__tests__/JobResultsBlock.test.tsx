import { render, waitFor } from "@testing-library/react-native";
import { JobResultsBlock } from "../JobResultsBlock";

const mockGetJobMatch = jest.fn();
const mockPush = jest.fn();
let mockToken = "account-a-token";
jest.mock("@/contexts/AuthContext", () => ({ useAuth: () => ({ token: mockToken, user: { id: mockToken } }) }));
jest.mock("expo-router", () => ({ useRouter: () => ({ push: mockPush }) }));
jest.mock("react-i18next", () => ({ useTranslation: () => ({ t: (key: string) => key }) }));
jest.mock("@/lib/api", () => ({ api: { getJobMatch: (...args: unknown[]) => mockGetJobMatch(...args) } }));
jest.mock("../JobMatchCard", () => {
  const { Text } = jest.requireActual("react-native");
  return { JobMatchCard: ({ match }: { match: { title: string } }) => <Text>{match.title}</Text> };
});
const id = "00000000-0000-4000-8000-000000000001";
const other = "00000000-0000-4000-8000-000000000002";
beforeEach(() => { jest.clearAllMocks(); mockToken = "account-a-token"; });

test("renders owned persisted facts and rejects invented fence facts", async () => {
  mockGetJobMatch.mockResolvedValue({ id, title: "Verified server title" });
  const { getByText, queryByText } = await render(<JobResultsBlock content={JSON.stringify({ matches: [{ id, title: "Invented title" }] })} />);
  await waitFor(() => expect(getByText("Verified server title")).toBeTruthy());
  expect(queryByText("Invented title")).toBeNull();
  expect(mockGetJobMatch).toHaveBeenCalledWith(mockToken, id);
});

test("keeps valid jobs visible when another result is inaccessible", async () => {
  mockGetJobMatch.mockImplementation((_token, matchId) => matchId === id ? Promise.resolve({ id, title: "Owned job" }) : Promise.reject(new Error("not owned")));
  const { getByText } = await render(<JobResultsBlock content={JSON.stringify({ matches: [{ id }, { id: other }] })} />);
  await waitFor(() => expect(getByText("Owned job")).toBeTruthy());
  expect(getByText("my_job.refresh_error")).toBeTruthy();
});

test("clears the previous account's hydrated jobs while a new account loads", async () => {
  mockGetJobMatch.mockResolvedValueOnce({ id, title: "Account A job" });
  const content = JSON.stringify({ matches: [{ id }] });
  const { getByText, queryByText, rerender } = await render(<JobResultsBlock content={content} />);
  await waitFor(() => expect(getByText("Account A job")).toBeTruthy());
  mockToken = "account-b-token";
  mockGetJobMatch.mockReturnValue(new Promise(() => {}));
  await rerender(<JobResultsBlock content={content} />);
  expect(queryByText("Account A job")).toBeNull();
  expect(mockGetJobMatch).toHaveBeenLastCalledWith(mockToken, id);
});
