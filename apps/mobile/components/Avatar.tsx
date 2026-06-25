import { Image, StyleSheet, Text, View } from 'react-native';

import { C } from '@/constants/Colors';

function initials(name: string | null): string {
  if (!name) return '?';
  const letters = name
    .split(' ')
    .map((w) => w[0])
    .filter(Boolean)
    .slice(0, 2)
    .join('')
    .toUpperCase();
  return letters || '?';
}

/** Google profile picture when available, otherwise the user's initials. */
export function Avatar({
  name,
  uri,
  size = 34,
}: {
  name: string | null;
  uri?: string | null;
  size?: number;
}) {
  const dim = { width: size, height: size, borderRadius: size / 2 };
  if (uri) {
    return <Image source={{ uri }} style={[dim, { backgroundColor: C.surface }]} />;
  }
  return (
    <View style={[dim, a.fallback]}>
      <Text style={[a.text, { fontSize: size * 0.4 }]}>{initials(name)}</Text>
    </View>
  );
}

const a = StyleSheet.create({
  fallback: { backgroundColor: C.primary, alignItems: 'center', justifyContent: 'center' },
  text: { color: '#fff', fontWeight: '700' },
});
