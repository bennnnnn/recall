# Recall — On-Device QA Matrix

Manual QA checklist for iOS and Android before store submission. Run against a **dev build** (not Expo Go) for native features; use **Expo Go + Dev User** for quick smoke only.

**Automated backend smoke (no device):** `./scripts/qa-smoke.sh`  
**Full local gate:** `./scripts/check.sh`

---

## Environment setup

| Step | iOS Simulator | Physical iOS | Android emulator | Physical Android |
|------|---------------|--------------|------------------|------------------|
| API running | `./scripts/dev.sh api` | same + LAN IP | same | same + `./scripts/set-lan-ip.sh` |
| Mobile start | `./scripts/dev.sh mobile-sim` | `./scripts/dev.sh mobile` | Expo dev build | Expo dev build |
| `EXPO_PUBLIC_API_URL` | `http://127.0.0.1:8000` | `http://<lan-ip>:8000` | `http://10.0.2.2:8000` (emu) or LAN | `http://<lan-ip>:8000` |

---

## 1. Authentication

| # | Test | iOS | Android | Notes |
|---|------|-----|---------|-------|
| 1.1 | Google Sign-In (dev build) | ☐ | ☐ | Requires native build + configured client IDs |
| 1.2 | Apple Sign-In (dev build, iOS) | ☐ | n/a | |
| 1.3 | Dev User (Expo Go) | ☐ | ☐ | `DEV_AUTH_ENABLED=true` on API |
| 1.4 | Session persists after app restart | ☐ | ☐ | JWT in secure store |
| 1.5 | Auto sign-out on expired refresh | ☐ | ☐ | Revoke refresh in Redis or wait 30d |
| 1.6 | Sign out clears tokens + Google session | ☐ | ☐ | |

---

## 2. Chat streaming

| # | Test | iOS | Android | Notes |
|---|------|-----|---------|-------|
| 2.1 | Send message → tokens stream | ☐ | ☐ | WebSocket primary path |
| 2.2 | Stop generation mid-stream | ☐ | ☐ | Partial reply kept |
| 2.3 | Regenerate last assistant reply | ☐ | ☐ | |
| 2.4 | Edit last user message | ☐ | ☐ | |
| 2.5 | New chat created on first message | ☐ | ☐ | No empty chat rows |
| 2.6 | Offline banner when API unreachable | ☐ | ☐ | |
| 2.7 | Quota exceeded shows plan-aware alert | ☐ | ☐ | Free vs Pro copy |

---

## 3. Rich rendering

| # | Test | iOS | Android | Notes |
|---|------|-----|---------|-------|
| 3.1 | Markdown (bold, lists, tables) | ☐ | ☐ | |
| 3.2 | Code blocks + syntax highlight | ☐ | ☐ | |
| 3.3 | Math / LaTeX | ☐ | ☐ | |
| 3.4 | Geometry / graph SVG | ☐ | ☐ | Works in Expo Go |
| 3.5 | HTML preview (WebView) | ☐ | ☐ | Dev build only |
| 3.6 | Chart / Mermaid (WebView) | ☐ | ☐ | Dev build only |
| 3.7 | PDF attachment preview | ☐ | ☐ | Dev build |

---

## 4. Attachments & voice

| # | Test | iOS | Android | Notes |
|---|------|-----|---------|-------|
| 4.1 | Image attach + send | ☐ | ☐ | |
| 4.2 | PDF attach + preview | ☐ | ☐ | |
| 4.3 | Speech → transcription → composer | ☐ | ☐ | Dev build; mic works with typed text too |
| 4.4 | Cancel voice recording (no upload) | ☐ | ☐ | Dev build |
| 4.5 | Read aloud (assistant + vocab) | ☐ | ☐ | Dev build; cloud TTS + device fallback |
| 4.6 | Export chat as PDF from the ⋯ menu | ☐ | ☐ | Full thread; headings/lists/code preserved |
| 4.7 | Export learning topic as PDF | ☐ | ☐ | Vocab words / trivia facts from project screen |
| 4.8 | Daily image cap enforced (free) | ☐ | ☐ | |
| 4.9 | Daily speech STT / TTS caps | ☐ | ☐ | Free 30 STT / 20 TTS |

---

## 5. Memory, todos, projects

| # | Test | iOS | Android | Notes |
|---|------|-----|---------|-------|
| 5.1 | Memory screen — view + delete | ☐ | ☐ | |
| 5.2 | Memory toggle in Settings | ☐ | ☐ | |
| 5.3 | Todos CRUD + reminders | ☐ | ☐ | |
| 5.4 | Learning project — vocab quiz flow | ☐ | ☐ | |
| 5.5 | Trivia project quiz | ☐ | ☐ | |
| 5.6 | Home suggestions load | ☐ | ☐ | |

---

## 6. Integrations

| # | Test | iOS | Android | Notes |
|---|------|-----|---------|-------|
| 6.1 | Google Calendar connect | ☐ | ☐ | |
| 6.2 | Calendar event create (confirm flow) | ☐ | ☐ | |
| 6.3 | Gmail connect + suggested reminders | ☐ | ☐ | Prod needs OAuth verification |

---

## 7. Push & monetization

| # | Test | iOS | Android | Notes |
|---|------|-----|---------|-------|
| 7.1 | Push permission + token registration | ☐ | ☐ | Dev build |
| 7.2 | Learning reminder push (scheduled) | ☐ | ☐ | Worker process must run |
| 7.3 | RevenueCat paywall + Pro unlock | ☐ | ☐ | Sandbox purchases |
| 7.4 | Pro quota (500k) reflected in Settings | ☐ | ☐ | |

---

## 8. Android keyboard (known risk area)

| # | Test | Android | Notes |
|---|------|---------|-------|
| 8.1 | Composer visible when keyboard open | ☐ | `softwareKeyboardLayoutMode: resize` |
| 8.2 | Send button reachable with keyboard up | ☐ | |
| 8.3 | Rotate device — layout recovers | ☐ | |

---

## 9. Theme & i18n

| # | Test | iOS | Android | Notes |
|---|------|-----|---------|-------|
| 9.1 | System / Light / Dark appearance | ☐ | ☐ | Settings → Personalization |
| 9.2 | Switch locale — UI strings update | ☐ | ☐ | At least one non-English locale |
| 9.3 | Dark theme on non-chat screens | ☐ | ☐ | Known partial rollout |

---

## 10. Composer AI features

| # | Test | iOS | Android | Notes |
|---|------|-----|---------|-------|
| 10.1 | Image generation (Pro) — composer send → inline image | ☐ | ☐ | No prompt sheet; sends immediately. Daily cap enforced (free blocked) |
| 10.2 | Image gen intent detected from plain prompt (no attach-menu row) | ☐ | ☐ | Intent → `/images/generate`; no second modal |
| 10.3 | Web search — source chips under reply, open source URL | ☐ | ☐ | `WEB_SEARCH_ENABLED=true`; MCP tool path wraps hits + chips; one Tavily reservation per turn; Redis reserve fail → DuckDuckGo (uncapped); no Tavily key → DDG |
| 10.4 | Math scanner — open, frame equation, resize (pinch), move (pan) | ☐ | ☐ | Dev build (camera). Close + cancel + reset work |
| 10.5 | Math scanner — capture → LaTeX into composer | ☐ | ☐ | Recognized expression editable before send |

---

## 11. Chat-driven settings & suggestions

| # | Test | iOS | Android | Notes |
|---|------|-----|---------|-------|
| 11.1 | Settings proposal card appears (e.g. "switch to dark mode") | ☐ | ☐ | Accept applies; reject dismisses |
| 11.2 | Appearance change via chat (dark/light/system incl. "default") | ☐ | ☐ | "default" → system; no "could not update" error |
| 11.3 | Suggestion chips load after a turn | ☐ | ☐ | Tappable follow-up prompts |
| 11.4 | Custom instructions in Settings → Preferences applied to prompts | ☐ | ☐ | Verify via a prompt that reflects them |

---

## 12. Search & navigation

| # | Test | iOS | Android | Notes |
|---|------|-----|---------|-------|
| 12.1 | Drawer search — full-text across chats/messages | ☐ | ☐ | Results show snippet + chat; tap opens chat |
| 12.2 | Link preview card under a message with URL | ☐ | ☐ | Domain line + title; tap opens in browser |
| 12.3 | Drawer open/close via edge pan + hamburger | ☐ | ☐ | No stray taps; mic press doesn't open drawer |
| 12.4 | New chat from drawer FAB; first message creates the chat | ☐ | ☐ | No empty chat rows left behind |

---

## 13. Account, profile & data controls

| # | Test | iOS | Android | Notes |
|---|------|-----|---------|-------|
| 13.1 | Onboarding completes and lands on chat | ☐ | ☐ | First-run only |
| 13.2 | Edit profile fields (name, age, country, job) | ☐ | ☐ | Saves + reflects in Settings |
| 13.3 | Data controls — export my data | ☐ | ☐ | Produces a downloadable archive |
| 13.4 | Data controls — delete account | ☐ | ☐ | Confirms; clears sessions + data |
| 13.5 | Sign out, then sign back in — state restores | ☐ | ☐ | Memories, chats, preferences persist |

---

## 14. Banned UX regressions (must NOT appear)

These were explicitly removed. If any reappears, it's a regression.

| # | Must NOT appear | iOS | Android | Notes |
|---|----------------|-----|---------|-------|
| 14.1 | "✨ Recalled N memories" chip on assistant messages | ☐ | ☐ | Backend may send `recalled`; UI must not surface |
| 14.2 | Show more / Show less on assistant message bodies | ☐ | ☐ | Code-block fold is OK; assistant body stays unfolded |
| 14.3 | `chat.model_fallback` / "switched to…" / "summarized" chips | ☐ | ☐ | Backend may send; UI must not surface |
| 14.4 | Image-gen prompt sheet / attach-menu "Generate image" | ☐ | ☐ | Composer-only; no second intercept |
| 14.5 | Project filter chips / "Link to project" on reminders | ☐ | ☐ | Schedule and Learning stay separate |
| 14.6 | Empty-state body / "Add" button duplicating the FAB | ☐ | ☐ | Learning + Schedule empty: icon + title only |
| 14.7 | Drawer Lists row / shopping checklist UI | ☐ | ☐ | Lists feature removed; do not reintroduce |

---

## Sign-off

| Platform | Build profile | Tester | Date | Pass/Fail |
|----------|---------------|--------|------|-----------|
| iOS | development / production | | | |
| Android | development / production | | | |

**Blockers:** document any failures with device model, OS version, and steps to reproduce.
