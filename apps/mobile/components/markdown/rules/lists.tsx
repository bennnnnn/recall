import { ReactNode } from "react";
import { PixelRatio, Text, View, type ViewStyle } from "react-native";

import { Icon } from "@/ui/icons/Icon";
import {
  type AstNode,
  type AstParent,
  bulletDiscMetrics,
  immediateAncestorType,
  isLastListItem,
  listItemDisplayNumber,
  listItemHasNestedList,
  listLargestNumber,
  numberColumnWidth,
  parentHasType,
  shouldNumberListItem,
  taskChecked,
} from "@/components/markdown/markdownAstHelpers";
import {
  verifyCheckStyles,
  type MdMathStyles,
  type StyleMap,
} from "@/components/markdown/markdownContentStyles";
import { VerifyCheckmark } from "@/components/markdown/VerifyCheckmark";
import { Space } from "@/lib/space";
import type { Theme } from "@/lib/theme";
import { IconSize } from "@/ui/icons/sizes";

/** The list disc's size and drop at the reader's text size. */
function bulletDiscStyle(): ViewStyle {
  const { size, top } = bulletDiscMetrics(PixelRatio.getFontScale());
  return { width: size, height: size, marginTop: top };
}

export function listRules(t: Theme, mdMath: MdMathStyles) {
  return {
    list_item: (
      node: AstNode & { index: number; markup?: string },
      children: ReactNode,
      parent: AstParent[],
      styles: StyleMap,
    ) => {
      const task = taskChecked(node);
      const itemStyle = [
        styles._VIEW_SAFE_list_item as object,
        isLastListItem(parent, node.index) && (styles.lastListItem as object),
      ];
      if (parentHasType(parent, "bullet_list") && task !== null) {
        if (task) {
          return (
            <View key={node.key} style={itemStyle}>
              <View style={[mdMath.listBullet, bulletDiscStyle()]} accessible={false} />
              <View style={verifyCheckStyles.verifyRow}>
                <View style={verifyCheckStyles.verifyContent}>{children}</View>
                <VerifyCheckmark />
              </View>
            </View>
          );
        }
        return (
          <View key={node.key} style={itemStyle}>
            <Icon
              name="square"
              size={IconSize.sm}
              color={t.textTertiary}
              style={{ marginTop: 2, marginRight: Space.xs }}
            />
            <View style={styles._VIEW_SAFE_bullet_list_content as object}>
              {children}
            </View>
          </View>
        );
      }
      if (shouldNumberListItem(parent)) {
        const markup =
          immediateAncestorType(parent) === "ordered_list" ? (node.markup ?? ".") : ".";
        return (
          <View key={node.key} style={itemStyle}>
            <Text
              style={[
                styles.ordered_list_icon as object,
                { minWidth: numberColumnWidth(listLargestNumber(parent), PixelRatio.getFontScale()) },
              ]}
            >
              {listItemDisplayNumber(parent, node.index)}
              {markup}
            </Text>
            <View style={[styles._VIEW_SAFE_ordered_list_content as object, mdMath.listContent]}>
              {children}
            </View>
          </View>
        );
      }
      if (immediateAncestorType(parent) === "bullet_list") {
        return (
          <View key={node.key} style={itemStyle}>
            {listItemHasNestedList(node) ? (
              // No disc on a parent topic, but keep its column: the label lines
              // up with its siblings' text and the sub-bullets indent under it.
              <View
                style={[mdMath.listBullet, bulletDiscStyle(), mdMath.listBulletSpacer]}
                accessible={false}
                testID="md-list-bullet-spacer"
              />
            ) : (
              <View
                style={[mdMath.listBullet, bulletDiscStyle()]}
                accessible={false}
                testID="md-list-bullet"
              />
            )}
            <View style={[styles._VIEW_SAFE_bullet_list_content as object, mdMath.listContent]}>
              {children}
            </View>
          </View>
        );
      }
      return (
        <View key={node.key} style={itemStyle}>
          {children}
        </View>
      );
    },
    bullet_list: (node: AstNode, children: ReactNode, parent: unknown, styles: StyleMap) => (
      <View
        key={node.key}
        style={[
          styles._VIEW_SAFE_bullet_list as object,
          parentHasType(parent, "list_item") && (styles.nestedList as object),
        ]}
      >
        {children}
      </View>
    ),
    ordered_list: (node: AstNode, children: ReactNode, parent: unknown, styles: StyleMap) => (
      <View
        key={node.key}
        style={[
          styles._VIEW_SAFE_ordered_list as object,
          parentHasType(parent, "list_item") && (styles.nestedList as object),
        ]}
      >
        {children}
      </View>
    ),
  };
}
