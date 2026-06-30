import { Ionicons } from "@expo/vector-icons";
import { Href, useRouter } from "expo-router";
import { Pressable } from "react-native";

import { useTheme } from "@/lib/theme";

type Props = {
  /** Where to go when there is no back stack (e.g. opened via deep link). */
  fallback?: Href;
};

export function StackBackButton({ fallback = "/" }: Props) {
  const theme = useTheme();
  const router = useRouter();

  return (
    <Pressable
      onPress={() => {
        if (router.canGoBack()) router.back();
        else router.replace(fallback);
      }}
      hitSlop={8}
      style={{ marginLeft: 4, padding: 4 }}
    >
      <Ionicons name="chevron-back" size={24} color={theme.primary} />
    </Pressable>
  );
}
