import { useEffect, useMemo, useState } from "react";
import { StyleSheet, View } from "react-native";
import { useTranslation } from "react-i18next";

import { useThumbnailSize } from "@/features/attachments/components/ChatMessageImage";
import { Radius } from "@/lib/radius";
import { Space } from "@/lib/space";
import { Theme, useTheme } from "@/lib/theme";
import { ActionShimmer } from "@/ui/feedback/ActionShimmer";

type Props = {
  /** The reply's photo is on its way until then (ms since epoch). */
  until: number;
};

/**
 * Where a reply's photo goes while it is still on its way (`done` said `photo_pending`): a
 * card the size of the photo's thumbnail, saying a photo is coming, so the photo swaps in
 * without moving the text. It goes when the photo comes (the message's content then holds it)
 * or once `until` passes with none.
 */
export function AnswerPhotoPlaceholder({ until }: Props) {
  const { t } = useTranslation();
  const theme = useTheme();
  const { width, height } = useThumbnailSize();
  const s = useMemo(() => makeStyles(theme, width, height), [theme, width, height]);
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    setNow(Date.now());
    const left = until - Date.now();
    if (left <= 0) return;
    const timer = setTimeout(() => setNow(Date.now()), left);
    return () => clearTimeout(timer);
  }, [until]);

  if (now >= until) return null;
  return (
    <View style={s.card} testID="answer-photo-placeholder">
      <ActionShimmer label={t("chat.status.answer_photo")} compact color={theme.textTertiary} />
    </View>
  );
}

function makeStyles(theme: Theme, width: number, height: number) {
  return StyleSheet.create({
    card: {
      width,
      height,
      // As the photo's own card (ChatMessageImage), so it takes this one's place exactly.
      borderRadius: Radius.bubble,
      backgroundColor: theme.surfaceAlt,
      alignItems: "center",
      justifyContent: "center",
      padding: Space.xs,
    },
  });
}
