# Recall UI kit (`apps/mobile/ui`)

One set of controls for the whole app, so a feature never builds its own
button, menu, picker or row. Features import each piece by its path
(`@/ui/controls/Button`); there is no barrel file. `ui/` never imports
product code (`@/features`, `@/components`, `@/contexts`, `@/hooks`,
`@/app`), which lint enforces.

Development builds show every piece in light and dark at
**Settings → About → UI kit** (`app/dev-ui.tsx`).

## Which piece for which job

| Job | Use | Instead of |
| --- | --- | --- |
| Ask before acting (delete, sign out, disconnect) | `confirmDialog()` from `overlay/dialogs` | `Alert.alert` with buttons |
| Tell something that needs reading (permission, Expo Go) | `alertDialog()` from `overlay/dialogs` | `Alert.alert` |
| A passing success or error | the toast: `useActionFeedback()` or `reportRecoverableError` | a dialog |
| Actions on a thing (⋮, long-press) | `overlay/Menu`, anchored to the button or the touch point | a bottom sheet of actions |
| Pick one of several from a row | `overlay/SelectMenu` (checked popover) | expanding options inline |
| Pick one of two to four in place | `controls/SegmentedControl` | a row of hand-made chips |
| A form, the attach sources, sharing | `overlay/Sheet` | a raw `Modal` |
| A full-screen viewer (photo, PDF, scanner) | `overlay/FullScreenModal` | a raw `Modal` |
| A time | `pickers/TimePickerDialog` (Android clock: dial, AM/PM, keyboard entry) | `@react-native-community/datetimepicker` |
| A date (month grid, year list, min/max) | `pickers/DatePickerDialog` | the native picker |
| A date then a time | `pickers/DateTimePickerDialog` | chaining native dialogs |
| Share a chat or a summary | `share/ShareSheet` (preview card, Share / Copy / PDF) | `Share.share` straight from a menu |
| Back, close, menu, ⋮ in a header | `controls/HeaderButton` (`plate`, `plain` in a `HeaderButtonGroup`, `media` over photos); `StackBackButton` in stacks | a hand-styled circle |
| A labelled action | `controls/Button` (pill; `sm` 36 / `md` 44 / `lg` 52; optional icon) | a `Pressable` styled as a button |
| An icon-only action inside content | `controls/IconButton` | a `Pressable` around `Icon` |
| Suggestions, filters, picked values, facts | `controls/Chip` (`assist`, `filter`, `input`, `tag`) | per-feature chip styles |
| Any list row | `list/ListRow` in a `list/ListGroup` (grouped) or on its own (plain) | per-feature row styles |
| Typing text | `controls/TextField` (label, helper, red error, multiline) | a styled `TextInput` |
| Searching a list | `controls/SearchField` | |
| Icons and logos | `icons/Icon` (Lucide line icons; `IconSize` ladder) and `icons/brand` `BrandMark` | `@expo/vector-icons`, PNG icons |
| Loading, empty, error | `feedback/StateView`, `feedback/SkeletonLoader` | |
| Small counts and labels | `feedback/CountBadge`, `feedback/StatusPill` | |

## Folders

- `controls/`: Button, IconButton, HeaderButton (+ HeaderButtonGroup), StackBackButton, Chip,
  SegmentedControl, TextField, SearchField, AddFab.
- `list/`: ListRow, ListGroup, ListSeparator.
- `overlay/`: Overlay (the one floating layer), Menu, SelectMenu, Dialog + DialogHost +
  `dialogs.ts`, Sheet, SheetFormHeader, FullScreenModal.
- `pickers/`: ClockDial, TimePickerDialog, DatePickerDialog, DateTimePickerDialog. The
  geometry and calendar rules live in `lib/datetime/clockDial.ts` and `calendarGrid.ts`.
- `share/`: ShareSheet.
- `icons/`: Icon, BrandMark, the icon manifest and generated glyphs, IconSize.
- `feedback/`: ActionBanner (the toast), StateView, SkeletonLoader, CountBadge, StatusPill,
  ActionShimmer.
- `hooks/`: useKeyboardHeight.

## Tokens

Pieces draw from the tokens in `lib/`: colors in `theme.ts` (`elevated` for popups, `control`
for plates and wells, `separator`, `pressed`, `wash`), type roles and `Weight` in `type.ts`,
`space.ts`, `radius.ts`, and springs in `motion.ts`. Lint rejects raw font sizes, font
weights, spacing, radii and hex colors outside a short list of domain graphics.

## How popups float

`Overlay` is the one layer every menu, dialog and picker opens in. On iOS it is a
`FullWindowOverlay`, so it can open over a sheet or another modal; on Android it is a
transparent `Modal`, which already stacks. It stays mounted through its closing fade.
`Sheet` is a real `Modal`: keep a sheet open while the OS share menu is on top of it, since
closing the presenter takes the share menu down with it on iOS (`ShareSheet` does this for you).

## Guardrails

- `@expo/vector-icons` and `@react-native-community/datetimepicker` cannot be imported.
- `Alert` and `Modal` from `react-native` only inside `ui/overlay`; `Switch` only inside `ui/`
  (use `ListRow` with `switchValue`). Tests may still spy on `Alert`.
- With no `DialogHost` mounted (tests, isolated hooks), `confirmDialog` and `alertDialog` fall
  back to `Alert.alert` with the old arguments.

## Adding an icon

Add the name and its Lucide id to `icons/manifest.json`, then run `pnpm icons`. App-only
drawings go in `icons/custom.tsx`; logos go in `icons/brand.tsx`.
