import type { Message } from "@/lib/api";
import { parseUserMessageContent } from "@/lib/messageAttachments";

type OrphanFile = {
  uri: string;
  name: string | null | undefined;
  contentType: string | null | undefined;
};

/**
 * When a silent refetch replaces the message list, keep local preview URIs
 * from optimistic bubbles so sent images don't flash blur/spinner while the
 * remote attachment file loads.
 *
 * Optimistic sends use `local-*` ids; the server list uses UUIDs, so matching
 * by id alone is not enough — also transfer orphaned local URIs onto incoming
 * user messages that carry the same attachment markers, in order.
 */
export function mergeLocalAttachmentUris(
  previous: Message[],
  incoming: Message[],
): Message[] {
  if (previous.length === 0) return incoming;
  const byId = new Map(previous.map((m) => [m.id, m]));
  const incomingIds = new Set(incoming.map((m) => m.id));

  const orphanImageUris: string[] = [];
  const orphanFiles: OrphanFile[] = [];
  for (const m of previous) {
    if (incomingIds.has(m.id) || m.role !== "user") continue;
    if (m.local_image_uri) orphanImageUris.push(m.local_image_uri);
    if (m.local_file_uri) {
      orphanFiles.push({
        uri: m.local_file_uri,
        name: m.local_file_name,
        contentType: m.local_file_content_type,
      });
    }
  }

  const merged = incoming.map((msg) => {
    const prior = byId.get(msg.id);
    let local_image_uri = msg.local_image_uri ?? prior?.local_image_uri ?? null;
    let local_file_uri = msg.local_file_uri ?? prior?.local_file_uri ?? null;
    let local_file_name = msg.local_file_name ?? prior?.local_file_name ?? null;
    let local_file_content_type =
      msg.local_file_content_type ?? prior?.local_file_content_type ?? null;

    if (msg.role === "user" && (!local_image_uri || !local_file_uri)) {
      const parsed = parseUserMessageContent(msg.content);
      if (!local_image_uri && parsed.images.length > 0 && orphanImageUris.length > 0) {
        local_image_uri = orphanImageUris.shift() ?? null;
      }
      if (
        !local_file_uri &&
        (parsed.files.length > 0 || parsed.hasFileAttachment) &&
        orphanFiles.length > 0
      ) {
        const file = orphanFiles.shift();
        if (file) {
          local_file_uri = file.uri;
          local_file_name = local_file_name ?? file.name ?? null;
          local_file_content_type = local_file_content_type ?? file.contentType ?? null;
        }
      }
    }

    if (
      local_image_uri === (msg.local_image_uri ?? null) &&
      local_file_uri === (msg.local_file_uri ?? null) &&
      local_file_name === (msg.local_file_name ?? null) &&
      local_file_content_type === (msg.local_file_content_type ?? null)
    ) {
      return msg;
    }

    return {
      ...msg,
      local_image_uri,
      local_file_uri,
      local_file_name,
      local_file_content_type,
    };
  });

  // M11: preserve streamed-* assistant messages that haven't been persisted
  // yet. After a stream ends with `persisting: true` (finalize still running
  // or timed out), the local list holds a `streamed-<ts>` assistant bubble
  // but the server hasn't persisted the row. A foreground refetch would
  // silently drop the partial reply. Keep any streamed-* assistant message
  // from `previous` that has no server counterpart in `incoming` — the
  // server list's last assistant message (if any) means the row landed and
  // the streamed id was already replaced.
  const hasServerAssistant = incoming.some((m) => m.role === "assistant");
  if (!hasServerAssistant) {
    const streamed = previous.filter(
      (m) => m.role === "assistant" && typeof m.id === "string" && m.id.startsWith("streamed-"),
    );
    if (streamed.length > 0) {
      merged.push(...streamed);
    }
  }

  return merged;
}
