import { useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import * as Clipboard from 'expo-clipboard';
import { Ionicons } from '@expo/vector-icons';

import { C } from '@/constants/Colors';

/**
 * Dependency-free syntax highlighting. A small tokenizer (comments, strings,
 * numbers, keywords) good enough for the common languages people paste, with a
 * graceful monochrome fallback for anything it doesn't recognise.
 */

const TOKEN_COLORS = {
  plain: C.codeText,
  comment: '#7C8B9A',
  string: '#E5A06E',
  number: '#B5CEA8',
  keyword: '#7AA2F7',
};

const KEYWORDS = new Set([
  'abstract', 'and', 'as', 'async', 'await', 'bool', 'boolean', 'break', 'case', 'catch', 'char',
  'class', 'const', 'continue', 'def', 'default', 'defer', 'del', 'delete', 'do', 'double', 'elif',
  'else', 'end', 'enum', 'except', 'export', 'extends', 'False', 'final', 'finally', 'float', 'fn',
  'for', 'from', 'func', 'function', 'global', 'go', 'if', 'impl', 'implements', 'import', 'in',
  'instanceof', 'int', 'interface', 'is', 'lambda', 'let', 'long', 'map', 'match', 'mod', 'mut',
  'new', 'nil', 'None', 'none', 'nonlocal', 'not', 'null', 'or', 'package', 'pass', 'private',
  'protected', 'pub', 'public', 'raise', 'return', 'self', 'short', 'static', 'str', 'string',
  'struct', 'super', 'switch', 'this', 'throw', 'trait', 'True', 'true', 'false', 'try', 'type',
  'typeof', 'undefined', 'use', 'var', 'void', 'where', 'while', 'with', 'yield', 'echo', 'fi',
  'then', 'done', 'local', 'select', 'chan', 'val', 'when',
]);

const HASH_COMMENT_LANGS = new Set([
  'python', 'py', 'bash', 'sh', 'shell', 'zsh', 'ruby', 'rb', 'yaml', 'yml', 'toml', 'r', 'perl',
  'makefile', 'dockerfile', 'ini', 'conf', 'elixir', 'ex',
]);

const COMMENT_JS = String.raw`\/\/[^\n]*|\/\*[\s\S]*?\*\/`;
const COMMENT_HASH = String.raw`#[^\n]*`;
const STRING_RE = String.raw`\`(?:\\.|[^\`\\])*\`|"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'`;
const NUMBER_RE = String.raw`\b\d[\w.]*\b`;
const WORD_RE = String.raw`[A-Za-z_$][\w$]*`;

type Token = { text: string; color: string };

function buildTokenRegex(lang: string): RegExp {
  const hash = HASH_COMMENT_LANGS.has(lang.toLowerCase());
  const comment = (hash ? COMMENT_HASH + '|' : '') + COMMENT_JS;
  return new RegExp(
    `(${comment})|(${STRING_RE})|(${NUMBER_RE})|(${WORD_RE})|(\\s+)|([^\\s])`,
    'g',
  );
}

function tokenize(code: string, lang: string): Token[] {
  const re = buildTokenRegex(lang);
  const tokens: Token[] = [];
  let match: RegExpExecArray | null;
  while ((match = re.exec(code)) !== null) {
    if (match[1]) tokens.push({ text: match[1], color: TOKEN_COLORS.comment });
    else if (match[2]) tokens.push({ text: match[2], color: TOKEN_COLORS.string });
    else if (match[3]) tokens.push({ text: match[3], color: TOKEN_COLORS.number });
    else if (match[4]) {
      tokens.push({
        text: match[4],
        color: KEYWORDS.has(match[4]) ? TOKEN_COLORS.keyword : TOKEN_COLORS.plain,
      });
    } else {
      tokens.push({ text: match[0], color: TOKEN_COLORS.plain });
    }
  }
  return tokens;
}

export function CodeBlock({ code, lang }: { code: string; lang: string }) {
  const [copied, setCopied] = useState(false);
  const tokens = tokenize(code, lang);

  const onCopy = async () => {
    await Clipboard.setStringAsync(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  return (
    <View style={s.wrap}>
      <View style={s.header}>
        {lang ? <Text style={s.lang}>{lang}</Text> : <View />}
        <Pressable style={s.copyBtn} onPress={onCopy} hitSlop={6}>
          <Ionicons
            name={copied ? 'checkmark-outline' : 'copy-outline'}
            size={13}
            color="#AEAEAE"
          />
          <Text style={s.copyText}>{copied ? ' Copied' : ' Copy'}</Text>
        </Pressable>
      </View>
      <ScrollView horizontal showsHorizontalScrollIndicator={false}>
        <Text style={s.code} selectable>
          {tokens.map((t, i) => (
            <Text key={i} style={{ color: t.color }}>
              {t.text}
            </Text>
          ))}
        </Text>
      </ScrollView>
    </View>
  );
}

const s = StyleSheet.create({
  wrap: { backgroundColor: C.codeBg, borderRadius: 12, overflow: 'hidden', marginVertical: 6 },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: '#333',
  },
  lang: { fontSize: 12, color: C.codeLang, fontWeight: '600' },
  copyBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 6,
    backgroundColor: '#2C2C2E',
  },
  copyText: { fontSize: 12, color: '#AEAEAE' },
  code: { fontFamily: 'SpaceMono', fontSize: 13, color: C.codeText, lineHeight: 20, padding: 12 },
});
