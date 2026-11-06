import { existsSync } from 'node:fs';
import type { ExpoConfig } from 'expo/config';

const apiUrl = process.env.EXPO_PUBLIC_API_URL ?? 'http://localhost:8000';
// Plain http is only for testing against a computer nearby. A real release talks to an https API,
// and then both platforms keep blocking unencrypted traffic.
const allowsPlainHttp = apiUrl.startsWith('http://');
// Android notifications need Firebase's file. Until it's added, the app builds without them.
const hasFirebaseConfig = existsSync('./google-services.json');

const config: ExpoConfig = {
  name: 'CareerFit',
  slug: 'careerfit',
  scheme: 'careerfit',
  version: '1.0.0',
  orientation: 'portrait',
  icon: './assets/icon.png',
  userInterfaceStyle: 'light',
  ios: {
    bundleIdentifier: 'com.sadullaev.careerfit',
    supportsTablet: true,
    infoPlist: {
      // Only standard HTTPS is used, which is exempt from US export paperwork.
      ITSAppUsesNonExemptEncryption: false,
      ...(allowsPlainHttp ? { NSAppTransportSecurity: { NSAllowsLocalNetworking: true } } : {}),
    },
  },
  android: {
    package: 'com.sadullaev.careerfit',
    adaptiveIcon: {
      backgroundColor: '#E6F4FE',
      foregroundImage: './assets/android-icon-foreground.png',
      backgroundImage: './assets/android-icon-background.png',
      monochromeImage: './assets/android-icon-monochrome.png',
    },
    predictiveBackGestureEnabled: false,
    // The camera only takes pictures of pages, so the microphone is never needed.
    blockedPermissions: ['android.permission.RECORD_AUDIO'],
    ...(hasFirebaseConfig ? { googleServicesFile: './google-services.json' } : {}),
  },
  plugins: [
    'expo-router',
    'expo-font',
    'expo-secure-store',
    'expo-web-browser',
    'expo-localization',
    [
      'expo-camera',
      {
        cameraPermission: 'CareerFit uses the camera to scan the pages of your resume.',
        microphonePermission: false,
        recordAudioAndroid: false,
      },
    ],
    ['expo-notifications', { color: '#00584C', defaultChannel: 'reports' }],
    ['expo-build-properties', { android: { usesCleartextTraffic: allowsPlainHttp } }],
  ],
  extra: {
    // The Expo project (@sadulllaev/careerfit) that builds and push notifications belong to. It isn't secret.
    eas: { projectId: 'ea3c9c4e-cbc4-4dba-8f34-819e2d23830d' },
  },
};

export default config;
