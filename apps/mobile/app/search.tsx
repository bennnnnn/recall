import { useCallback, useEffect, useRef, useState } from "react";
import {
  ActivityIndicator,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { Redirect, useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useTranslation } from "react-i18next";

import { C } from "@/constants/Colors";
import { useAuth } from "@/contexts/AuthContext";
import { api, SearchResult } from "@/lib/api";

export default function SearchScreen() {
  const { token } = useAuth();
  const { t } = useTranslation();
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(false);
  const inputRef = useRef<TextInput>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const [error, setError] = useState(false);

  if (!token) return <Redirect href="/login" />;

  const doSearch = useCallback(
    async (q: string) => {
      if (!token || !q.trim()) {
        setResults([]);
        setSearched(false);
        setError(false);
        return;
      }
      setLoading(true);
      setSearched(true);
      setError(false);
      try {
        const data = await api.search(token, q.trim());
        setResults(data.results);
      } catch {
        setError(true);
        setResults([]);
      } finally {
        setLoading(false);
      }
    },
    [token],
  );

  const onChangeText = (text: string) => {
    setQuery(text);
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => {
      void doSearch(text);
    }, 300);
  };

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  // Clean up debounce timer on unmount.
  useEffect(() => {
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, []);

  const openChat = (chatId: string) => {
    router.dismissAll();
    router.push({ pathname: "/", params: { chatId } });
  };

  return (
    <View style={[s.root, { paddingTop: insets.top }]}>
      {/* Search bar */}
      <View style={s.bar}>
        <Ionicons name="search-outline" size={20} color={C.textSecondary} />
        <TextInput
          ref={inputRef}
          style={s.input}
          placeholder={t("search.placeholder")}
          placeholderTextColor={C.textTertiary}
          value={query}
          onChangeText={onChangeText}
          returnKeyType="search"
          autoCorrect={false}
        />
        {query ? (
          <Pressable
            onPress={() => {
              setQuery("");
              setResults([]);
              setSearched(false);
            }}
            hitSlop={8}
          >
            <Ionicons name="close-circle" size={20} color={C.textTertiary} />
          </Pressable>
        ) : null}
      </View>

      {/* Results */}
      {loading ? (
        <View style={s.center}>
          <ActivityIndicator size="small" color={C.primary} />
        </View>
      ) : error ? (
        <View style={s.center}>
          <Ionicons
            name="cloud-offline-outline"
            size={48}
            color={C.textTertiary}
            style={s.hintIcon}
          />
          <Text style={s.hint}>{t("common.error")}</Text>
        </View>
      ) : !searched ? (
        <View style={s.center}>
          <Ionicons
            name="search-outline"
            size={48}
            color={C.primary}
            style={s.hintIcon}
          />
          <Text style={s.hint}>{t("search.empty")}</Text>
        </View>
      ) : results.length === 0 ? (
        <View style={s.center}>
          <Ionicons
            name="search-outline"
            size={48}
            color={C.textTertiary}
            style={s.hintIcon}
          />
          <Text style={s.hint}>{t("search.no_results")}</Text>
        </View>
      ) : (
        <View style={s.list}>
          {results.map((r) => (
            <Pressable
              key={r.message_id}
              style={s.resultItem}
              onPress={() => openChat(r.chat_id)}
            >
              <View style={s.resultHeader}>
                <Ionicons
                  name={r.role === "user" ? "person-outline" : "sparkles-outline"}
                  size={14}
                  color={C.textSecondary}
                />
                <Text style={s.chatTitle} numberOfLines={1}>
                  {r.chat_title ?? t("common.untitled")}
                </Text>
              </View>
              <Text style={s.snippet} numberOfLines={2}>
                {r.content}
              </Text>
            </Pressable>
          ))}
        </View>
      )}
    </View>
  );
}

const s = StyleSheet.create({
  root: { flex: 1, backgroundColor: C.bg },
  bar: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    paddingHorizontal: 14,
    paddingVertical: 10,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: C.border,
  },
  input: {
    flex: 1,
    fontSize: 16,
    color: C.text,
    paddingVertical: 4,
  },
  center: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: 32,
  },
  hint: { fontSize: 15, color: C.textSecondary, textAlign: "center" },
  hintIcon: { opacity: 0.4, marginBottom: 12 },
  list: { flex: 1 },
  resultItem: {
    paddingHorizontal: 16,
    paddingVertical: 14,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: C.border,
    gap: 4,
  },
  resultHeader: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    marginBottom: 2,
  },
  chatTitle: { fontSize: 13, color: C.textSecondary, flex: 1 },
  snippet: { fontSize: 15, lineHeight: 21, color: C.text },
});
