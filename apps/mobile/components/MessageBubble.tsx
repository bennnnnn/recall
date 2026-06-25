import * as Clipboard from 'expo-clipboard';
import { Ionicons } from '@expo/vector-icons';
import Markdown from 'react-native-markdown-display';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { useState } from 'react';

import { C } from '@/constants/Colors';
import { Message } from '@/lib/api';

type Props = {
  message: Message;
  isLastAssistant?: boolean;
  onRegenerate?: () => void;
};

async function copyText(text: string) {
  await Clipboard.setStringAsync(text);
}

const renderRules = {
  fence: (node: { key: string; content: string; info?: string }) => {
    const lang = node.info?.trim() || '';
    const code = node.content.trimEnd();
    return (
      <View key={node.key} style={cs.wrap}>
        <View style={cs.header}>
          {lang ? <Text style={cs.lang}>{lang}</Text> : <View />}
          <Pressable style={cs.copyBtn} onPress={() => copyText(code)}>
            <Ionicons name="copy-outline" size={13} color="#AEAEAE" />
            <Text style={cs.copyText}> Copy</Text>
          </Pressable>
        </View>
        <ScrollView horizontal showsHorizontalScrollIndicator={false}>
          <Text style={cs.code} selectable>{code}</Text>
        </ScrollView>
      </View>
    );
  },
};

function AssistantActions({
  content,
  onRegenerate,
}: {
  content: string;
  onRegenerate?: () => void;
}) {
  const [liked, setLiked] = useState<'up' | 'down' | null>(null);
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    await copyText(content);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  return (
    <View style={a.row}>
      <Pressable style={a.btn} onPress={handleCopy} hitSlop={8}>
        <Ionicons
          name={copied ? 'checkmark-outline' : 'copy-outline'}
          size={20}
          color={copied ? C.primary : C.textSecondary}
        />
      </Pressable>
      <Pressable
        style={a.btn}
        onPress={() => setLiked((v) => (v === 'up' ? null : 'up'))}
        hitSlop={8}>
        <Ionicons
          name={liked === 'up' ? 'thumbs-up' : 'thumbs-up-outline'}
          size={20}
          color={liked === 'up' ? C.primary : C.textSecondary}
        />
      </Pressable>
      <Pressable
        style={a.btn}
        onPress={() => setLiked((v) => (v === 'down' ? null : 'down'))}
        hitSlop={8}>
        <Ionicons
          name={liked === 'down' ? 'thumbs-down' : 'thumbs-down-outline'}
          size={20}
          color={liked === 'down' ? C.primary : C.textSecondary}
        />
      </Pressable>
      {onRegenerate && (
        <Pressable style={a.btn} onPress={onRegenerate} hitSlop={8}>
          <Ionicons name="refresh-outline" size={20} color={C.textSecondary} />
        </Pressable>
      )}
    </View>
  );
}

export function MessageBubble({ message, isLastAssistant, onRegenerate }: Props) {
  const isUser = message.role === 'user';
  const isStreaming = message.id === 'streaming';

  return (
    <View style={[b.row, isUser ? b.userRow : b.assistantRow]}>
      <View style={[b.bubble, isUser ? b.userBubble : b.assistantBubble]}>
        {isUser ? (
          <Text style={b.userText}>{message.content}</Text>
        ) : (
          <Markdown style={mdStyles} rules={renderRules as never}>
            {message.content}
          </Markdown>
        )}
      </View>

      {!isUser && !isStreaming && (
        <AssistantActions
          content={message.content}
          onRegenerate={isLastAssistant ? onRegenerate : undefined}
        />
      )}
    </View>
  );
}

const cs = StyleSheet.create({
  wrap: { backgroundColor: C.codeBg, borderRadius: 12, overflow: 'hidden', marginVertical: 6 },
  header: {
    flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center',
    paddingHorizontal: 12, paddingVertical: 8,
    borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: '#333',
  },
  lang: { fontSize: 12, color: C.codeLang, fontWeight: '600' },
  copyBtn: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 8, paddingVertical: 4, borderRadius: 6, backgroundColor: '#2C2C2E' },
  copyText: { fontSize: 12, color: '#AEAEAE' },
  code: { fontFamily: 'SpaceMono', fontSize: 13, color: C.codeText, lineHeight: 20, padding: 12 },
});

const a = StyleSheet.create({
  row: { flexDirection: 'row', alignItems: 'center', gap: 4, marginTop: 6, paddingHorizontal: 2 },
  btn: { width: 36, height: 36, alignItems: 'center', justifyContent: 'center' },
});

const b = StyleSheet.create({
  row: { marginVertical: 4, paddingHorizontal: 12 },
  userRow: { alignItems: 'flex-end' },
  assistantRow: { alignItems: 'flex-start' },
  bubble: { maxWidth: '88%', borderRadius: 18, paddingHorizontal: 14, paddingVertical: 10 },
  userBubble: { backgroundColor: C.userBubble, borderBottomRightRadius: 4 },
  assistantBubble: { backgroundColor: C.assistantBubble, borderBottomLeftRadius: 4 },
  userText: { color: C.userText, fontSize: 16, lineHeight: 22 },
});

const mdStyles = StyleSheet.create({
  body: { color: C.assistantText, fontSize: 16, lineHeight: 24 },
  code_inline: { backgroundColor: '#E8E3FF', color: C.primaryDark, borderRadius: 4, paddingHorizontal: 4, fontFamily: 'SpaceMono', fontSize: 14 },
  fence: { display: 'none' as never },
  paragraph: { marginVertical: 0 },
  bullet_list: { marginVertical: 4 },
  ordered_list: { marginVertical: 4 },
  heading1: { fontSize: 20, fontWeight: '700', marginBottom: 8 },
  heading2: { fontSize: 18, fontWeight: '700', marginBottom: 6 },
  heading3: { fontSize: 16, fontWeight: '600', marginBottom: 4 },
  strong: { fontWeight: '700' },
  em: { fontStyle: 'italic' },
  blockquote: { backgroundColor: C.surface, borderLeftWidth: 3, borderLeftColor: C.primary, paddingLeft: 12, paddingVertical: 4, marginVertical: 4, borderRadius: 4 },
  hr: { backgroundColor: C.border, height: 1, marginVertical: 12 },
  link: { color: C.primary },
});
