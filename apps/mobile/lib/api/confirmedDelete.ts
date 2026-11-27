/**
 * What a delete of everything sends to say it means it (apps/api core/delete_confirmation.py):
 * `DELETE /chats` and `DELETE /memories` delete nothing on a token alone, as `DELETE /auth/me`
 * does not. Sent only after the user confirmed the delete.
 */
export const DELETE_CONFIRMATION = "delete";

export function confirmedDelete(): RequestInit {
  return { method: "DELETE", body: JSON.stringify({ confirm: DELETE_CONFIRMATION }) };
}
