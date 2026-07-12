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
};

export type Chat = {
  id: string;
  title: string | null;
  model: string;
  pinned: boolean;
  archived?: boolean;
  project_id?: string | null;
  quiz_mode?: "exam" | "chat" | null;
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
  recalled?: number;
  memory_hints?: string[];
  context_summarized?: number;
  search_sources?: SearchSource[];
  local_image_uri?: string | null;
  local_file_uri?: string | null;
  local_file_name?: string | null;
  local_file_content_type?: string | null;
  /** Client-only: server fell back to another model for this reply. */
  fallback_used?: boolean;
  /** Client-only FlashList key — stable while `id` changes streaming → persisted. */
  renderKey?: string;
  /** Client-only: reasoning shown during stream, kept through layout settle to avoid list bounce. */
  reasoning_preview?: string;
  created_at: string;
};

export type Memory = {
  id: string;
  type: string;
  text: string;
  confidence: number | null;
  created_at: string;
  updated_at: string;
};

export type Todo = {
  id: string;
  content: string;
  topic: string;
  checked: boolean;
  due_at: string | null;
  sort_order: number | null;
  chat_id: string | null;
  project_id?: string | null;
  created_at: string;
  updated_at: string;
};

/** Product learning kinds: English vocabulary + general knowledge. */
export type ProjectKind = "language" | "vocabulary" | "trivia";
export type LanguageLevel = "level1" | "level2" | "level3" | "level4" | "level5" | "level6";
export type VocabStatus = "new" | "learning" | "mastered";

export type Project = {
  id: string;
  title: string;
  description: string | null;
  kind: ProjectKind;
  target_language: string;
  native_language: string | null;
  level: LanguageLevel;
  daily_goal: number | null;
  archived: boolean;
  created_at: string;
  updated_at: string;
  /** Present on list responses for language/trivia projects. */
  stats?: ProjectStats;
};

export type ProjectItem = {
  id: string;
  list_title: string;
  content: string;
  note: string | null;
  definition: string | null;
  example_sentence: string | null;
  status: VocabStatus;
  mastered: boolean;
  mastered_at: string | null;
  last_reviewed_at: string | null;
  last_incorrect_at?: string | null;
  review_count: number;
  pronunciation_url: string | null;
  created_at: string;
};

export type ProjectStats = {
  total: number;
  new_count: number;
  learning_count: number;
  mastered_count: number;
  added_this_week: number;
  due_for_review: number;
  mastered_today: number;
  missed_today?: number;
  pending_today: number;
  last_mastery_at?: string | null;
  streak_days?: number;
  days_inactive?: number | null;
  quiz_accuracy_pct?: number | null;
  suggested_level?: "up" | "down" | null;
};

export type ProjectDailyHistoryDay = {
  date: string;
  weekday: number;
  mastered_count: number;
  missed_count: number;
  daily_goal: number;
  goal_met: boolean;
  status: "complete" | "partial" | "skipped" | "today" | "inactive";
};

export type ProjectListGroup = {
  list_title: string;
  items: ProjectItem[];
};

export type ProjectDetail = Project & {
  mastered_count: number;
  total_count: number;
  stats: ProjectStats;
  daily_history: ProjectDailyHistoryDay[];
  daily_items_by_date: Record<string, ProjectItem[]>;
  daily_missed_by_date?: Record<string, ProjectItem[]>;
  lists: ProjectListGroup[];
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
  kind: "time" | "memory" | "chat" | "general" | "todo" | "project";
};

export type HomeProjectHighlight = {
  project_id: string;
  title: string;
  kind: "language" | "trivia";
  daily_goal: number;
  mastered_today: number;
  missed_today?: number;
  cue: "start" | "continue" | "not_started_today" | "missed_yesterday" | "finish_pending";
  streak_days?: number;
  days_inactive?: number | null;
  due_for_review?: number;
  suggested_level?: "up" | "down" | null;
};

export type HomeScreen = {
  greeting: string;
  subtitle: string | null;
  project_highlight: HomeProjectHighlight | null;
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
  status: string;
  created_at: string;
  gmail_message_id: string;
};

export type AuthResult = {
  access_token: string;
  refresh_token: string;
  user: User;
};
