// The web app's palette, converted from its OKLCH tokens, so both apps look like one product.
export const colors = {
  background: '#FBF9F5',
  foreground: '#1A222E',
  card: '#FFFFFF',
  primary: '#00584C',
  primaryForeground: '#FFFFFF',
  secondary: '#EFECE7',
  muted: '#F2F0EB',
  mutedForeground: '#515962',
  accent: '#DFF2ED',
  accentForeground: '#00372F',
  destructive: '#B32322',
  border: '#DDDAD5',
  input: '#7A8189',
  shown: '#095C34',
  shownSoft: '#DDF6E4',
  partly: '#7E4F04',
  partlySoft: '#FEEDC9',
  missing: '#AC312C',
  missingSoft: '#FFE9E6',
} as const;

export const space = { xs: 4, sm: 8, md: 12, lg: 16, xl: 24, xxl: 32 } as const;

export const radius = { sm: 6, md: 10, lg: 14 } as const;

// Apple and Google both ask for touch targets of at least 44 points.
export const MIN_TOUCH = 44;

export const type = {
  title: { fontSize: 26, fontWeight: '700', lineHeight: 32 },
  heading: { fontSize: 19, fontWeight: '600', lineHeight: 25 },
  body: { fontSize: 16, lineHeight: 23 },
  small: { fontSize: 14, lineHeight: 20 },
} as const;
