import type { PlanFeature, PlanId } from "@/lib/plan";
import type { SearchSource } from "@/lib/searchSources";

export type { SearchSource };

/** Voices both read-aloud and live talk speak (the server's UserVoice). */
export type UserVoice =
  | "marin"
  | "cedar"
  | "alloy"
  | "ash"
  | "ballad"
  | "coral"
  | "echo"
  | "sage"
  | "shimmer"
  | "verse";

export type User = {
  id: string;
  email: string;
  name: string | null;
  avatar_url: string | null;
  default_model: string;
  plan: PlanId;
  /** What the plan includes (display only; the server checks every request). */
  features?: PlanFeature[];
  enabled_models: string[] | null;
  response_style: string;
  /** Three follow-up questions under a reply; on unless the user turned it off. */
  follow_up_suggestions_enabled?: boolean;
  /** Web search and photo lookups (Settings → Data controls); on unless turned off. */
  web_search_enabled?: boolean;
  response_tone: string;
  memory_enabled: boolean;
  memory_include_sensitive?: boolean;
  push_notifications_enabled: boolean;
  /** Each push kind's own switch, under the master one. */
  push_reminders_enabled?: boolean;
  /** Read-aloud and live talk voice; null is the server default. */
  tts_voice?: UserVoice | null;
  email_reminders_enabled?: boolean;
  reminder_lead_minutes: number;
  locale: string;
  timezone: string;
  location: string | null;
  location_enabled: boolean;
  custom_instructions: string | null;
  age: number | null;
  country: string | null;
  job: string | null;
  created_at: string;
  sign_in_provider?: "google" | "apple" | "dev";
  /** Signs in with Apple (alone or beside Google); deleting asks Apple once more. */
  apple_linked?: boolean;
  quiet_hours_enabled?: boolean;
  quiet_hours_start_minute?: number;
  quiet_hours_end_minute?: number;
};

export type Chat = {
  id: string;
  title: string | null;
  model: string;
  pinned: boolean;
  archived?: boolean;
  created_at: string;
  updated_at: string;
};

export type Feedback = "up" | "down" | null;

export type MessagePage = {
  messages: Message[];
  has_more: boolean;
};

export type Message = {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  model: string | null;
  feedback?: Feedback;
  /** Related subject questions for the latest reply. Tap sends the string. */
  related_prompts?: string[] | null;
  search_sources?: SearchSource[];
  local_image_uri?: string | null;
  local_file_uri?: string | null;
  local_file_name?: string | null;
  local_file_content_type?: string | null;
  /** Client-only FlashList key — stable while `id` changes streaming → persisted. */
  renderKey?: string;
  /** Client-only: image generation stopped or failed (inline card + retry). */
  image_gen_failure?: "canceled" | "failed";
  image_gen_error?: string;
  /** Client-only: stream was stopped or the provider died after tokens started. */
  generationStopped?: boolean;
  created_at: string;
};

export type Memory = {
  id: string;
  type: string;
  /** The memory document this fact belongs to (profile, tech-stack, area:recall, …). */
  topic?: string;
  text: string;
  confidence: number | null;
  status?: "active" | "muted" | "superseded";
  sensitivity?: string | null;
  last_confirmed_at?: string | null;
  source_chat_id?: string | null;
  source_chat_title?: string | null;
  created_at: string;
  updated_at: string;
};

export const RECURRENCE_RULES = ["daily", "weekdays", "weekly", "monthly"] as const;
export type RecurrenceRule = (typeof RECURRENCE_RULES)[number];

export type Todo = {
  id: string;
  content: string;
  topic: string;
  checked: boolean;
  due_at: string | null;
  recurrence_rule?: RecurrenceRule | null;
  sort_order: number | null;
  chat_id: string | null;
  created_at: string;
  updated_at: string;
};

export type SearchResult = {
  match_type: "message" | "title";
  message_id: string | null;
  chat_id: string;
  chat_title: string | null;
  content: string;
  role: string;
  created_at: string;
};

export type HomeUrgentTodo = {
  id: string;
  content: string;
  topic: string;
  due_at: string;
  minutes_until: number;
};

export type HomeStarter = {
  id?: string;
  text: string;
  prompt: string;
  kind: "time" | "memory" | "chat" | "general" | "todo";
  chat_id?: string;
};

export type HomeScreen = {
  greeting: string;
  subtitle: string | null;
  urgent_todos: HomeUrgentTodo[];
  starters: HomeStarter[];
};

export type ChatList = {
  pinned: Chat[];
  today: Chat[];
  yesterday: Chat[];
  last_7_days: Chat[];
  this_month: Chat[];
  older: Chat[];
  archived: Chat[];
};

export type Usage = {
  date: string;
  input_tokens: number;
  output_tokens: number;
  daily_limit: number;
  used_tokens?: number;
  remaining: number;
  context_token_budget?: number;
  recent_message_window?: number;
};

/** One entry of GET /models. The server also sends prices and quota
 * multipliers; the phone neither shows nor keeps them, so it leaves them out. */
export type ModelInfo = {
  id: string;
  label: string;
  description: string;
  tier: string;
  plan_access: "free" | "pro";
  available: boolean;
  healthy?: boolean;
  latency_p50_ms?: number | null;
  health_samples?: number;
};

export type AuthResult = {
  access_token: string;
  refresh_token: string;
  user: User;
};

export type AuthSession = {
  id: string;
  device_label: string | null;
  platform: string | null;
  created_at: string | null;
  last_seen_at: string | null;
  current: boolean;
};
