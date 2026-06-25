import Constants from 'expo-constants';

import { config } from '@/lib/config';

const EXPO_GO_MESSAGE =
  'Google Sign-In requires a dev build (pnpm expo run:android). In Expo Go, use "Continue as Dev User".';

export function isExpoGo(): boolean {
  return Constants.appOwnership === 'expo';
}

export async function signInWithGoogleIdToken(): Promise<string> {
  if (isExpoGo()) {
    throw new Error(EXPO_GO_MESSAGE);
  }

  const { GoogleSignin, statusCodes } = await import(
    '@react-native-google-signin/google-signin'
  );

  GoogleSignin.configure({
    webClientId: config.googleWebClientId,
    iosClientId: config.googleIosClientId,
    offlineAccess: false,
  });

  try {
    await GoogleSignin.hasPlayServices({ showPlayServicesUpdateDialog: true });
    const response = await GoogleSignin.signIn();
    const idToken = response.data?.idToken;
    if (!idToken) {
      throw new Error('Google Sign-In did not return an ID token.');
    }
    return idToken;
  } catch (error: unknown) {
    const err = error as { code?: string; message?: string };
    if (err.code === statusCodes.SIGN_IN_CANCELLED) {
      throw new Error('Sign-in cancelled');
    }
    if (err.code === statusCodes.IN_PROGRESS) {
      throw new Error('Sign-in already in progress');
    }
    if (err.code === statusCodes.PLAY_SERVICES_NOT_AVAILABLE) {
      throw new Error('Google Play Services not available');
    }
    throw new Error(err.message ?? 'Google Sign-In failed.');
  }
}

export async function signOutGoogle() {
  if (isExpoGo()) return;
  try {
    const { GoogleSignin } = await import('@react-native-google-signin/google-signin');
    await GoogleSignin.signOut();
  } catch {
    // Best-effort
  }
}
