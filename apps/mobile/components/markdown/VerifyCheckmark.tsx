import { useMemo } from "react";
import { View } from "react-native";
import { Icon } from "@/components/Icon";

import { makeVerifyCheckStyles } from "@/components/markdown/markdownContentStyles";
import { useTheme } from "@/lib/theme";

export function VerifyCheckmark() {
  const theme = useTheme();
  const s = useMemo(() => makeVerifyCheckStyles(theme), [theme]);
  return (
    <View style={s.badge}>
      <Icon name="checkmark" size={13} color={theme.onPrimary} />
    </View>
  );
}
