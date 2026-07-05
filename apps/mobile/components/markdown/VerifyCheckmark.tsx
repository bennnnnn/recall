import { View } from "react-native";
import { Ionicons } from "@expo/vector-icons";

import { verifyCheckStyles } from "@/components/markdown/markdownContentStyles";

export function VerifyCheckmark() {
  return (
    <View style={verifyCheckStyles.badge}>
      <Ionicons name="checkmark" size={13} color="#FFFFFF" />
    </View>
  );
}
