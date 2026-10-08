import type { SearchSource } from "@/lib/searchSources";

export type { SearchSource };

export type User = {
  id: string;
  email: string;
  name: string | null;
  avatar_url: string | null;
  default_model: string;
  plan: "free" | "pro";
  enabled_models: string[] | null;
  response_style: string;
  response_tone: string;
  memory_enabled: boolean;
  memory_include_sensitive?: boolean;
  push_notifications_enabled: boolean;
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

export type Suggestion = {
  id: string;
  text: string;
  category: string;
  source: string;
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

export type ModelInfo = {
  id: string;
  label: string;
  description: string;
  tier: string;
  plan_access: "free" | "pro";
  available: boolean;
  input_price_per_m: number | null;
  output_price_per_m: number | null;
  quota_multiplier: number;
  healthy?: boolean;
  latency_p50_ms?: number | null;
  health_samples?: number;
};

export type GoogleCalendarStatus = {
  connected: boolean;
  email?: string | null;
  configured: boolean;
  can_write?: boolean;
};

export type GoogleCalendarEvent = {
  id: string;
  title: string;
  start_at: string;
  end_at?: string | null;
  location?: string | null;
  all_day: boolean;
  calendar_name?: string | null;
};

export type GoogleGmailStatus = {
  connected: boolean;
  email?: string | null;
  configured: boolean;
  last_sync_at?: string | null;
};

export type SuggestedReminder = {
  id: string;
  title: string;
  due_at: string | null;
  notes: string | null;
  confidence: number;
  source_snippet: string | null;
  source_sender: string | null;
  status: string;
  created_at: string;
  gmail_message_id: string;
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
