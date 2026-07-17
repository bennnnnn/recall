import type { Message } from "@/lib/api";

/**
 * When a silent refetch replaces the message list, keep local preview URIs
 * from optimistic bubbles so sent images don't flash blur/spinner while the
 * remote attachment file loads.
 */
export function mergeLocalAttachmentUris(
  previous: Message[],
  incoming: Message[],
): Message[] {
  if (previous.length === 0) return incoming;
  const byId = new Map(previous.map((m) => [m.id, m]));
  return incoming.map((msg) => {
    const prior = byId.get(msg.id);
    if (!prior) return msg;
    return {
      ...msg,
      local_image_uri: msg.local_image_uri ?? prior.local_image_uri ?? null,
      local_file_uri: msg.local_file_uri ?? prior.local_file_uri ?? null,
      local_file_name: msg.local_file_name ?? prior.local_file_name ?? null,
      local_file_content_type:
        msg.local_file_content_type ?? prior.local_file_content_type ?? null,
    };
  });
}
