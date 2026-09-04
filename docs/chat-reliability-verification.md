# Chat reliability patch — verification and release gates

Scope: eight reviewed gaps (draft persistence, settled rendering, relevant memory,
technical follow-up routing, document coverage, real image edits, voice interruption,
and voice lookups). No new surfaces or banned UX. Text and image providers are unchanged;
dictation, cloud read-aloud, and Live Talk use OpenAI directly.

## Automated checks

- Full mobile suite passed: 256 suites / 2,020 tests. Regression
  cases cover deferred image updaters, upload cancellation, delayed voice events,
  in-place transcript reconciliation, and image-reference persistence.
- Full backend run: 3,231 passed; 26 PostgreSQL setup errors (localhost:5432 unavailable),
  and five unchanged link-preview tests failed because public DNS was unavailable.
  Do not interpret these as a fully green integration run.
- Offline rerun: 3,239 passed, with the 26 database cases excluded and five
  DNS-dependent cases deselected. The final canonical voice-source persistence
  regression also passed in the 18-test Realtime suite.
- API Ruff and mypy (590 files), mobile TypeScript, and lint error checks pass.
  Existing lint warnings remain. Mypy required `--no-incremental` after a cache crash.
- Provider calls were mocked. No live API requests or new credential creation.

## Before release

- Configure an authorized `OPENAI_API_KEY` on the backend. Key creation was rejected
  in this session; no key was created or installed. Verify dictation, read-aloud,
  and Realtime model access separately before rollout.
- Rebuild the mobile dev client for `expo-device`. Test physical iOS and Android:
  loudspeaker/headphones/Bluetooth, echo, speaking over buffered audio, mute, stop,
  disconnect/reconnect, delayed transcripts, and interrupted web lookup.
- Interrupted replies currently become the existing “Generation stopped.” text:
  exact word-to-playback alignment is not available. This avoids saving unspoken
  generated text as a delivered answer, but loses already-heard partial text.
- Verify web/memory lookups on a real call, source chips after reopening, exhausted
  quota, disabled memory, expired session, and missing/slow results. Voice tools
  cannot send mail or create reminders; only memory and web search are exposed.
- Run PostgreSQL repository integration tests against a disposable migrated database.
- Smoke-test real image editing and regeneration with the configured image model.
  References are user-owned bytes, not arbitrary fetched URLs; persistence is atomic,
  and retries retain the original reference ID.
- Reindex or re-upload older documents to gain expanded coverage. Limits remain:
  500 text-layer PDF pages / 200k extracted characters / configured chunk budget;
  XLSX 10k rows and 256 columns per sheet; PPTX 500 slides. Scanned-PDF OCR has its
  existing separate budget. No arbitrary spreadsheet execution or embedded-chart reading.
- Check long streamed math/code/chart replies on-device after settling and reopening;
  canonical formatting now runs after streaming. Review any end-of-stream layout movement.
- Test email edits with slow/failing saves, edits during save, Done, immediate follow-up,
  image send, and thread navigation. A failed flush must keep the composer draft.

## Protocol references

- [OpenAI Realtime conversations](https://developers.openai.com/api/docs/guides/realtime-conversations)
- [OpenAI text-to-speech](https://developers.openai.com/api/docs/guides/text-to-speech)
- [OpenRouter image references](https://openrouter.ai/docs/guides/overview/multimodal/image-generation)
- [Expo SDK 57 Device](https://docs.expo.dev/versions/v57.0.0/sdk/device/)
