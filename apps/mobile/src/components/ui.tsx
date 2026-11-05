import { forwardRef, type ReactNode } from 'react';
import {
  ActivityIndicator,
  Pressable,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
  type TextInputInstance,
  type TextInputProps,
  type ViewStyle,
} from 'react-native';
import { colors, MIN_TOUCH, radius, space, type } from '@/theme';

export function Screen({
  children,
  refreshing,
  onRefresh,
}: {
  children: ReactNode;
  refreshing?: boolean;
  onRefresh?: () => void;
}) {
  return (
    <ScrollView
      style={styles.screen}
      contentContainerStyle={styles.screenContent}
      keyboardShouldPersistTaps="handled"
      refreshControl={
        onRefresh ? (
          <RefreshControl refreshing={Boolean(refreshing)} onRefresh={onRefresh} tintColor={colors.primary} colors={[colors.primary]} />
        ) : undefined
      }
    >
      {children}
    </ScrollView>
  );
}

export function Title({ children }: { children: ReactNode }) {
  return (
    <Text accessibilityRole="header" style={[type.title, styles.ink]}>
      {children}
    </Text>
  );
}

export function Heading({ children }: { children: ReactNode }) {
  return (
    <Text accessibilityRole="header" style={[type.heading, styles.ink]}>
      {children}
    </Text>
  );
}

export function Body({ children, style }: { children: ReactNode; style?: object }) {
  return <Text style={[type.body, styles.ink, style]}>{children}</Text>;
}

export function Muted({ children, style }: { children: ReactNode; style?: object }) {
  return <Text style={[type.small, styles.muted, style]}>{children}</Text>;
}

export function Card({ children, style }: { children: ReactNode; style?: ViewStyle }) {
  return <View style={[styles.card, style]}>{children}</View>;
}

type ButtonVariant = 'primary' | 'secondary' | 'destructive' | 'link';

export function Button({
  title,
  onPress,
  variant = 'primary',
  disabled,
  busy,
  accessibilityLabel,
}: {
  title: string;
  onPress: () => void;
  variant?: ButtonVariant;
  disabled?: boolean;
  busy?: boolean;
  accessibilityLabel?: string;
}) {
  const inactive = Boolean(disabled || busy);
  return (
    <Pressable
      accessibilityRole={variant === 'link' ? 'link' : 'button'}
      accessibilityLabel={accessibilityLabel}
      accessibilityState={{ disabled: inactive, busy: Boolean(busy) }}
      disabled={inactive}
      onPress={onPress}
      style={({ pressed }) => [
        styles.button,
        buttonStyles[variant],
        inactive && styles.inactive,
        pressed && !inactive && styles.pressed,
      ]}
    >
      {busy && <ActivityIndicator color={variant === 'primary' ? colors.primaryForeground : colors.primary} />}
      <Text style={[styles.buttonText, buttonTextStyles[variant]]}>{title}</Text>
    </Pressable>
  );
}

type FieldProps = TextInputProps & { label: string; hint?: string; error?: string | null };

export const Field = forwardRef<TextInputInstance, FieldProps>(function Field({ label, hint, error, style, ...props }, ref) {
  return (
    <View style={styles.field}>
      <Text style={[type.small, styles.label]}>{label}</Text>
      <TextInput
        ref={ref}
        accessibilityLabel={label}
        accessibilityHint={error ?? hint}
        placeholderTextColor={colors.mutedForeground}
        style={[styles.input, error ? styles.inputError : null, style]}
        {...props}
      />
      {hint && !error && <Muted>{hint}</Muted>}
      {error && (
        <Text accessibilityLiveRegion="polite" style={[type.small, styles.errorText]}>
          {error}
        </Text>
      )}
    </View>
  );
});

export function Notice({ children, tone = 'info' }: { children: ReactNode; tone?: 'info' | 'error' }) {
  return (
    <View
      accessibilityRole={tone === 'error' ? 'alert' : 'text'}
      accessibilityLiveRegion={tone === 'error' ? 'assertive' : 'polite'}
      style={[styles.notice, tone === 'error' && styles.noticeError]}
    >
      <Text style={[type.small, tone === 'error' ? styles.errorText : styles.ink]}>{children}</Text>
    </View>
  );
}

export function Badge({ label, tone = 'neutral' }: { label: string; tone?: 'neutral' | 'shown' | 'partly' | 'missing' }) {
  return (
    <View style={[styles.badge, badgeStyles[tone]]}>
      <Text style={[styles.badgeText, badgeTextStyles[tone]]}>{label}</Text>
    </View>
  );
}

export function Segmented<T extends string>({
  options,
  value,
  onChange,
}: {
  options: { value: T; label: string; disabled?: boolean }[];
  value: T;
  onChange: (next: T) => void;
}) {
  return (
    <View accessibilityRole="tablist" style={styles.segmented}>
      {options.map((option) => {
        const selected = option.value === value;
        return (
          <Pressable
            key={option.value}
            accessibilityRole="tab"
            accessibilityState={{ selected, disabled: option.disabled }}
            disabled={option.disabled}
            onPress={() => onChange(option.value)}
            style={[styles.segment, selected && styles.segmentSelected, option.disabled && styles.inactive]}
          >
            <Text numberOfLines={1} style={[type.small, selected ? styles.segmentTextSelected : styles.ink]}>
              {option.label}
            </Text>
          </Pressable>
        );
      })}
    </View>
  );
}

export function Loading() {
  return (
    <View style={styles.loading}>
      <ActivityIndicator size="large" color={colors.primary} />
    </View>
  );
}

export function Divider() {
  return <View style={styles.divider} />;
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.background },
  screenContent: { padding: space.lg, gap: space.lg, paddingBottom: space.xxl },
  ink: { color: colors.foreground },
  muted: { color: colors.mutedForeground },
  card: {
    backgroundColor: colors.card,
    borderColor: colors.border,
    borderWidth: StyleSheet.hairlineWidth,
    borderRadius: radius.lg,
    padding: space.lg,
    gap: space.md,
  },
  button: {
    minHeight: MIN_TOUCH + 4,
    borderRadius: radius.md,
    paddingHorizontal: space.lg,
    alignItems: 'center',
    justifyContent: 'center',
    flexDirection: 'row',
    gap: space.sm,
  },
  buttonText: { fontSize: 16, fontWeight: '600', textAlign: 'center' },
  inactive: { opacity: 0.5 },
  pressed: { opacity: 0.8 },
  field: { gap: space.xs },
  label: { color: colors.foreground, fontWeight: '600' },
  input: {
    minHeight: MIN_TOUCH + 4,
    borderColor: colors.input,
    borderWidth: 1,
    borderRadius: radius.md,
    paddingHorizontal: space.md,
    fontSize: 16,
    color: colors.foreground,
    backgroundColor: colors.card,
  },
  inputError: { borderColor: colors.destructive },
  errorText: { color: colors.destructive },
  notice: {
    borderRadius: radius.md,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.border,
    backgroundColor: colors.card,
    padding: space.md,
  },
  noticeError: { borderColor: colors.destructive, backgroundColor: colors.missingSoft },
  badge: { alignSelf: 'flex-start', borderRadius: 999, paddingHorizontal: space.sm, paddingVertical: 2 },
  badgeText: { fontSize: 13, fontWeight: '600' },
  segmented: {
    flexDirection: 'row',
    backgroundColor: colors.secondary,
    borderRadius: radius.md,
    padding: 3,
  },
  segment: {
    flex: 1,
    minHeight: MIN_TOUCH,
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: radius.sm,
    paddingHorizontal: space.xs,
  },
  segmentSelected: { backgroundColor: colors.card },
  segmentTextSelected: { color: colors.primary, fontWeight: '700' },
  loading: { flex: 1, alignItems: 'center', justifyContent: 'center', backgroundColor: colors.background },
  divider: { height: StyleSheet.hairlineWidth, backgroundColor: colors.border },
});

const buttonStyles = StyleSheet.create({
  primary: { backgroundColor: colors.primary },
  secondary: { backgroundColor: colors.card, borderWidth: 1, borderColor: colors.border },
  destructive: { backgroundColor: colors.destructive },
  link: { minHeight: MIN_TOUCH, paddingHorizontal: 0, alignSelf: 'flex-start' },
});

const buttonTextStyles = StyleSheet.create({
  primary: { color: colors.primaryForeground },
  secondary: { color: colors.foreground },
  destructive: { color: colors.primaryForeground },
  link: { color: colors.primary },
});

const badgeStyles = StyleSheet.create({
  neutral: { backgroundColor: colors.secondary },
  shown: { backgroundColor: colors.shownSoft },
  partly: { backgroundColor: colors.partlySoft },
  missing: { backgroundColor: colors.missingSoft },
});

const badgeTextStyles = StyleSheet.create({
  neutral: { color: colors.foreground },
  shown: { color: colors.shown },
  partly: { color: colors.partly },
  missing: { color: colors.missing },
});
