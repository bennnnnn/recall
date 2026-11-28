import { ReactNode } from "react";
import { Image } from "expo-image";
import { Text } from "react-native";

import { type AstNode, astText } from "@/components/markdown/markdownAstHelpers";
import type { MdImgStyles, StyleMap } from "@/components/markdown/markdownContentStyles";
import { TapToLoadImage } from "@/components/markdown/TapToLoadImage";
import { imageLoadPolicy } from "@/lib/images/imageUriPolicy";
import { isAllowedLinkUrl, openAllowedUrl } from "@/lib/linkSchemePolicy";
import { replyLinkUrl } from "@/lib/markdown/replyLinks";

export function linkRules(mdImg: MdImgStyles) {
  return {
    image: (node: { key: string; attributes: { src?: string; alt?: string } }) => {
      const src = node.attributes?.src;
      // A model-written image URL can carry the user's data (prompt
      // injection), so only the API's own and inline images load by
      // themselves; another https host waits for a tap; the rest never load.
      const policy = imageLoadPolicy(src);
      if (policy === "block" || !src) return null;
      const alt = node.attributes?.alt?.trim() ?? "";
      if (policy === "ask") {
        return <TapToLoadImage key={node.key} uri={src} alt={alt} imageStyle={mdImg.image} />;
      }
      return (
        <Image
          key={node.key}
          source={{ uri: src }}
          style={mdImg.image}
          contentFit="contain"
          cachePolicy="memory-disk"
          accessibilityRole="image"
          accessibilityLabel={alt || undefined}
          accessible={alt.length > 0}
        />
      );
    },
    link: (
      node: AstNode,
      children: ReactNode,
      _parent: unknown,
      styles: StyleMap,
    ) => {
      const href = node.attributes?.href ?? "";
      const title = node.attributes?.title ?? "";
      // A name still marked to look up (the reply is streaming) opens Maps or a search
      // (`replyLinks.ts`). The scheme guard rejects javascript:/data:/file: before the OS
      // link handler: Linking.openURL runs the payload on some platforms. A target it would
      // refuse ("#", "zunicafe.com") is drawn as the words, never as a dead link.
      const target = replyLinkUrl(href, astText(node), title);
      if (!isAllowedLinkUrl(target)) return <Text key={node.key}>{children}</Text>;
      return (
        <Text
          key={node.key}
          style={styles.link}
          accessibilityRole="link"
          onPress={() => {
            void openAllowedUrl(target);
          }}
          suppressHighlighting
        >
          {children}
        </Text>
      );
    },
  };
}
