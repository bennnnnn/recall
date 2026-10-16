import { ReactNode } from "react";
import { Image } from "expo-image";
import { Text } from "react-native";

import { type AstNode, astText } from "@/components/markdown/markdownAstHelpers";
import type { MdImgStyles, StyleMap } from "@/components/markdown/markdownContentStyles";
import { isAllowedImageUri } from "@/lib/images/imageUriPolicy";
import { openAllowedUrl } from "@/lib/linkSchemePolicy";
import { openPlaceLink } from "@/lib/openPlaceLink";
import { isGenericSearchUrl } from "@/lib/placesList";

export function linkRules(mdImg: MdImgStyles) {
  return {
    image: (node: { key: string; attributes: { src?: string; alt?: string } }) => {
      const src = node.attributes?.src;
      // Block insecure-scheme / local-file image URIs (tracking pixels, file:
      // exfil, content:). Only https/data/blob render; everything else is
      // dropped silently so a malicious or misformed URL can't auto-load.
      if (!isAllowedImageUri(src)) return null;
      const alt = node.attributes?.alt?.trim() ?? "";
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
      const label = astText(node);
      return (
        <Text
          key={node.key}
          style={styles.link}
          accessibilityRole="link"
          onPress={() => {
            // Reject javascript:/data:/file:/etc. before handing to the OS link
            // handler — model-emitted markdown can include arbitrary URLs and
            // Linking.openURL executes the payload on some platforms.
            if (isGenericSearchUrl(href)) {
              void openPlaceLink(href, label);
            } else {
              void openAllowedUrl(href);
            }
          }}
          suppressHighlighting
        >
          {children}
        </Text>
      );
    },
  };
}
