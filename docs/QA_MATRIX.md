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
| 4.6 | Export assistant reply as PDF | ☐ | ☐ | Headings/lists/code preserved |
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

## Sign-off

| Platform | Build profile | Tester | Date | Pass/Fail |
|----------|---------------|--------|------|-----------|
| iOS | development / production | | | |
| Android | development / production | | | |

**Blockers:** document any failures with device model, OS version, and steps to reproduce.
