# UI action feedback

Recall uses one feedback policy for user-initiated asynchronous work. The goal is to make
the affected control understandable without freezing unrelated parts of the screen.

## Policy

- Guard every action synchronously with a ref or equivalent lock. Render state alone is
  not duplicate-submit protection because two taps can arrive before React re-renders.
- Keep pending feedback local to the affected control or row. Disable only controls that
  would conflict with the operation.
- Use optimistic state for instant mutations. Keep a snapshot and restore it if persistence
  fails.
- Use a spinner in compact controls. Use `ActionShimmer` for noticeable waits whose progress
  cannot be measured. Do not shimmer measurable uploads or work that normally completes
  before the delayed indicator appears.
- Keep the action label visible while waiting when its purpose would otherwise become
  unclear.
- A visible navigation or state change is sufficient success feedback. Use the shared
  action-feedback banner and haptic only when the result is otherwise unclear.
- Send recoverable failures through `useActionFeedbackOptional`; retain a local fallback
  only where a provider might legitimately be absent.

## Semantic color and motion

- `theme.primary`: user actions and pending controls.
- `theme.accent`: active AI work only.
- `theme.success`, `theme.warning`, and `theme.danger`: outcomes only.
- No action-feedback component introduces hard-coded action colors.
- `ActionShimmer` delays motion to avoid flashes. Reduce Motion renders a static progress
  treatment, and `ActionBanner` skips its entrance animation.

## Accessibility contract

Async controls expose `accessibilityState.busy` and `disabled` while blocked. Progress
elements use the `progressbar` role and an action-specific label. Important banner outcomes
use an assertive live region; informational outcomes use a polite live region. Disabled
state, labels, and retry controls must remain meaningful without relying on color or motion.

## Audited rollout

### Shared system

- Shared `ActionShimmer`, reduced-motion fallback, and delayed animated implementation.
- Shared `Button` loading label/indicator behavior.
- App-level `ActionFeedbackProvider`, outcome banner, haptics, and accessibility announcements.

### Chat, media, and attachments

- Send: guarded prepare/send phases, busy composer control, recoverable new-chat failure,
  and restored draft/attachment.
- Pending user message: delayed “Sending…” shimmer.
- Regenerate: guarded request and compact spinner on the affected assistant action.
- Attachment picker/upload: guarded picker, disabled conflicting controls, measurable upload
  indicator, and shared failure banner.
- Voice: busy/disabled mic state, reduced-motion pulse, and accessible recording progress.
- Image generation remains composer-only; the existing retry path is preserved.

### Auth and settings

- Login and onboarding: synchronous duplicate guards, loading labels, and shared failures.
- Profile fields: per-field save state and guarded sheet controls.
- Preferences, memory, models, notifications, and Learning settings: per-control guards,
  compact busy indicators, optimistic rollback where applicable, and shared failures.

### Schedule and Learning

- Reminder create, toggle, due-date save, and delete: row-level
  busy state, duplicate guard, rollback, and operation-appropriate error copy.
- Reminder create: guarded form that stays recoverable while saving.
- Suggested reminders: guarded accept/dismiss controls and shared recovery feedback.
- Learning project create, item status update, delete, and settings: affected-control busy
  state, duplicate guard, and recoverable failure.
- Quiz answers: preserve immediate correct/wrong coloring during submission; if submission
  fails, unlock the choices so the answer can be retried.

## Deferred audit surfaces

Lower-priority actions remain intentionally unchanged until their owning workflow is audited:

- exports and share-sheet handoff
- passive cache refreshes and background synchronization
- noncritical rich-card actions outside the chat send path
- secondary integration maintenance actions

When extending the rollout, add focused tests for the guard, pending accessibility state,
rollback or retry behavior, and reduced-motion behavior where animation is involved. Do not
add animation solely for visual activity.
