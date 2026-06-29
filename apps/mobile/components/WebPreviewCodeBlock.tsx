import { useState } from "react";
import { StyleSheet, TouchableOpacity, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";

import { CodeBlock } from "@/components/CodeBlock";
import { HtmlPreviewModal } from "@/components/HtmlPreviewModal";
import { C } from "@/constants/Colors";
import { openHtmlInBrowser } from "@/lib/openHtmlPreview";

type Props = {
  code: string;
  lang?: string;
};

/** HTML fence: syntax-highlighted code + preview modal + bottom actions. */
export function WebPreviewCodeBlock({ code, lang = "html" }: Props) {
  const [modalOpen, setModalOpen] = useState(false);

  return (
    <>
      <CodeBlock
        code={code}
        lang={lang}
        headerExtra={
          <TouchableOpacity
            style={[s.iconBtn, modalOpen && s.iconBtnActive]}
            onPress={() => setModalOpen(true)}
            activeOpacity={0.6}
            accessibilityLabel="Preview HTML"
          >
            <Ionicons
              name="play-outline"
              size={16}
              color={modalOpen ? C.primary : C.textSecondary}
            />
          </TouchableOpacity>
        }
        footerExtra={
          <View style={s.footerActions}>
            <TouchableOpacity
              style={s.iconBtn}
              onPress={() => setModalOpen(true)}
              activeOpacity={0.6}
              accessibilityLabel="Preview HTML"
            >
              <Ionicons name="play-outline" size={18} color={C.textSecondary} />
            </TouchableOpacity>
            <TouchableOpacity
              style={s.iconBtn}
              onPress={() => void openHtmlInBrowser(code)}
              activeOpacity={0.6}
              accessibilityLabel="Open in browser"
            >
              <Ionicons name="open-outline" size={18} color={C.textSecondary} />
            </TouchableOpacity>
          </View>
        }
      />

      {modalOpen ? (
        <HtmlPreviewModal visible html={code} onClose={() => setModalOpen(false)} />
      ) : null}
    </>
  );
}

const s = StyleSheet.create({
  footerActions: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
  },
  iconBtn: {
    width: 36,
    height: 36,
    borderRadius: 8,
    alignItems: "center",
    justifyContent: "center",
  },
  iconBtnActive: {
    backgroundColor: C.primaryLight,
  },
});
