// TODO(mvp): Move to a versioned server endpoint (GET /privacy) so policy
// updates don't require an app-store submission. Fetch on first load, cache
// locally, and show a "policy updated" notice when the version changes.
// The endpoint should also support per-locale policy text.
export const PRIVACY_POLICY = `# Privacy Policy

**Last updated: June 2026**

## What We Collect

- **Account information**: Your name and email address from Google Sign-In.
- **Conversations**: Messages you send and responses from the AI.
- **Learned facts**: Information Recall extracts to personalize your experience (preferences, projects, facts you share).
- **Usage data**: Token counts for daily quota tracking.

## How We Use Your Data

- To provide personalized AI responses based on what you've shared.
- To improve response quality via thumbs-up/thumbs-down feedback.
- To enforce daily usage limits.

## Data Storage

Your data is stored in a secure PostgreSQL database. Memories and conversations are associated with your account and are never shared with third parties.

## AI Processing

Messages are sent to AI providers (via LiteLLM) to generate responses. These providers do not retain your data and process it only to generate the current response.

## Your Rights

- **Export**: Download all your data (chats, messages, memories) as JSON at any time from Settings.
- **Delete account**: Permanently delete your account and all associated data from Settings. This is irreversible.
- **Delete memories**: Remove individual learned facts from the Memory screen.

## Children's Privacy

Recall is not intended for users under 13. We do not knowingly collect data from children.

## Changes

We may update this policy. Check this page for the latest version.

## Contact

If you have questions about this policy or your data, reach out through the app or your account provider.`;
