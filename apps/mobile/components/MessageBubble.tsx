import * as Clipboard from 'expo-clipboard';
import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import Markdown from 'react-native-markdown-display';
import { Animated, Image, Pressable, StyleSheet, Text, View } from 'react-native';
import { useEffect, useRef, useState, type ReactNode } from 'react';

import { C } from '@/constants/Colors';
import { CodeBlock } from '@/components/CodeBlock';
import { Message } from '@/lib/api';

// Messages taller than this get folded behind a "Show more" toggle.
const COLLAPSED_MAX_HEIGHT = 320;
const OVERFLOW_SLACK = 24;

type Props = {
  message: Message;
  isLastAssistant?: boolean;
  onRegenerate?: () => void;
  onFeedback?: (messageId: string, feedback: 'up' | 'down' | null) => void;
  onEdit?: () => void;
};

async function copyText(text: string) {
  await Clipboard.setStringAsync(text);
}

const renderRules = {
  fence: (node: { key: string; content: string; info?: string }) => (
    <CodeBlock key={node.key} code={node.content.replace(/\n$/, '')} lang={node.info?.trim() || ''} />
  ),
  code_block: (node: { key: string; content: string; info?: string }) => (
    <CodeBlock key={node.key} code={node.content.replace(/\n$/, '')} lang={node.info?.trim() || ''} />
  ),
  image: (node: { key: string; attributes: { src?: string; alt?: string } }) => {
    const src = node.attributes?.src;
    if (!src) return null;
    return <Image key={node.key} source={{ uri: src }} style={mdImg.image} resizeMode="contain" />;
  },
};

function AssistantActions({
  messageId,
  content,
  feedback,
  onFeedback,
  onRegenerate,
}: {
  messageId: string;
  content: string;
  feedback: 'up' | 'down' | null;
  onFeedback?: (messageId: string, feedback: 'up' | 'down' | null) => void;
  onRegenerate?: () => void;
}) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    await copyText(content);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  // Tapping the active rating clears it; otherwise sets it.
  const rate = (dir: 'up' | 'down') => onFeedback?.(messageId, feedback === dir ? null : dir);

  return (
    <View style={a.row}>
      <Pressable style={a.btn} onPress={handleCopy} hitSlop={8}>
        <Ionicons
          name={copied ? 'checkmark-outline' : 'copy-outline'}
          size={20}
          color={copied ? C.primary : C.textSecondary}
        />
      </Pressable>
      <Pressable style={a.btn} onPress={() => rate('up')} hitSlop={8}>
        <Ionicons
          name={feedback === 'up' ? 'thumbs-up' : 'thumbs-up-outline'}
          size={20}
          color={feedback === 'up' ? C.primary : C.textSecondary}
        />
      </Pressable>
      <Pressable style={a.btn} onPress={() => rate('down')} hitSlop={8}>
        <Ionicons
          name={feedback === 'down' ? 'thumbs-down' : 'thumbs-down-outline'}
          size={20}
          color={feedback === 'down' ? C.primary : C.textSecondary}
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

function CollapsibleContent({
  isUser,
  enabled,
  children,
}: {
  isUser: boolean;
  enabled: boolean;
  children: ReactNode;
}) {
  const [expanded, setExpanded] = useState(false);
  const [contentHeight, setContentHeight] = useState(0);

  const overflowing = enabled && contentHeight > COLLAPSED_MAX_HEIGHT + OVERFLOW_SLACK;
  const collapsed = overflowing && !expanded;

  // Fade matches the bubble background so the clipped edge looks intentional.
  const fadeColors = isUser
    ? (['rgba(108,71,255,0)', C.userBubble] as const)
    : (['rgba(240,240,245,0)', C.assistantBubble] as const);

  return (
    <View>
      <View style={collapsed ? cl.clip : undefined}>
        <View
          onLayout={(e) => {
            const h = e.nativeEvent.layout.height;
            setContentHeight((prev) => (Math.abs(prev - h) > 1 ? h : prev));
          }}>
          {children}
        </View>
        {collapsed && <LinearGradient pointerEvents="none" colors={fadeColors} style={cl.fade} />}
      </View>
      {overflowing && (
        <Pressable onPress={() => setExpanded((v) => !v)} hitSlop={6} style={cl.toggle}>
          <Text style={[cl.toggleText, isUser && cl.toggleTextUser]}>
            {expanded ? 'Show less' : 'Show more'}
          </Text>
        </Pressable>
      )}
    </View>
  );
}

function RecalledChip({ count }: { count: number }) {
  const opacity = useRef(new Animated.Value(0)).current;
  useEffect(() => {
    Animated.timing(opacity, { toValue: 1, duration: 250, useNativeDriver: true }).start();
  }, [opacity]);
  return (
    <Animated.View style={[rc.chip, { opacity }]}>
      <Ionicons name="sparkles" size={12} color={C.primary} />
      <Text style={rc.text}>Recalled {count} {count === 1 ? 'memory' : 'memories'}</Text>
    </Animated.View>
  );
}

export function MessageBubble({ message, isLastAssistant, onRegenerate, onFeedback, onEdit }: Props) {
  const isUser = message.role === 'user';
  const isStreaming = message.id === 'streaming';

  return (
    <View style={[b.row, isUser ? b.userRow : b.assistantRow]}>
      {!isUser && !isStreaming && message.recalled ? <RecalledChip count={message.recalled} /> : null}
      <View style={[b.bubble, isUser ? b.userBubble : b.assistantBubble]}>
        {/* Don't fold while still streaming — the height is changing every token */}
        <CollapsibleContent isUser={isUser} enabled={!isStreaming}>
          {isUser ? (
            <Text style={b.userText}>{message.content}</Text>
          ) : (
            <Markdown style={mdStyles} rules={renderRules as never}>
              {message.content}
            </Markdown>
          )}
        </CollapsibleContent>
      </View>

      {!isUser && !isStreaming && (
        <AssistantActions
          messageId={message.id}
          content={message.content}
          feedback={message.feedback ?? null}
          onFeedback={onFeedback}
          onRegenerate={isLastAssistant ? onRegenerate : undefined}
        />
      )}

      {isUser && onEdit && (
        <Pressable onPress={onEdit} hitSlop={8} style={b.editBtn}>
          <Ionicons name="pencil-outline" size={15} color={C.textTertiary} />
        </Pressable>
      )}
    </View>
  );
}

const mdImg = StyleSheet.create({
  image: {
    width: '100%',
    height: 200,
    borderRadius: 8,
    marginVertical: 6,
    backgroundColor: C.surface,
  },
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
  editBtn: { marginTop: 4, padding: 4 },
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
  table: {
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: C.border,
    borderRadius: 8,
    marginVertical: 8,
    overflow: 'hidden',
  },
  thead: { backgroundColor: C.surface },
  th: { flex: 1, padding: 8, fontWeight: '700', color: C.text },
  tr: { flexDirection: 'row', borderBottomWidth: StyleSheet.hairlineWidth, borderColor: C.border },
  td: { flex: 1, padding: 8, color: C.assistantText },
});

const rc = StyleSheet.create({
  chip: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    alignSelf: 'flex-start',
    backgroundColor: C.primaryLight,
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 999,
    marginBottom: 4,
  },
  text: { fontSize: 11, color: C.primary, fontWeight: '600' },
});

const cl = StyleSheet.create({
  clip: { maxHeight: COLLAPSED_MAX_HEIGHT, overflow: 'hidden' },
  fade: { position: 'absolute', left: 0, right: 0, bottom: 0, height: 44 },
  toggle: { marginTop: 6, alignSelf: 'flex-start' },
  toggleText: { fontSize: 13, fontWeight: '600', color: C.primary },
  toggleTextUser: { color: 'rgba(255,255,255,0.92)' },
});
