/**
 * The + sheet's "Math keyboard" row. The composer holds the math pad, so the sheet asks
 * and the mounted composer opens it (the composer's row has no calculator button: the
 * + menu holds it, and the row is +, the field, mic and live talk).
 */
import { createListenerSet } from "@/lib/listenerSet";

export const mathKeyboardRequests = createListenerSet();
