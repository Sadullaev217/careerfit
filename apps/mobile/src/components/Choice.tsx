import { Pressable, StyleSheet, Text, View } from 'react-native';
import { colors, MIN_TOUCH, radius, space } from '@/theme';

/** A set of options where exactly one is picked, read out by screen readers as radio buttons. */
export function Choice<T extends string>({
  options,
  value,
  onChange,
  label,
}: {
  options: { value: T; label: string; disabled?: boolean }[];
  value: T | null;
  onChange: (next: T) => void;
  label: string;
}) {
  return (
    <View accessibilityRole="radiogroup" accessibilityLabel={label} style={styles.wrap}>
      {options.map((option) => {
        const checked = option.value === value;
        return (
          <Pressable
            key={option.value}
            accessibilityRole="radio"
            accessibilityState={{ checked, disabled: option.disabled }}
            disabled={option.disabled}
            onPress={() => onChange(option.value)}
            style={[styles.chip, checked && styles.checked, option.disabled && styles.disabled]}
          >
            <Text style={[styles.text, checked && styles.checkedText]}>{option.label}</Text>
          </Pressable>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { flexDirection: 'row', flexWrap: 'wrap', gap: space.sm },
  chip: {
    minHeight: MIN_TOUCH,
    justifyContent: 'center',
    paddingHorizontal: space.md,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.card,
  },
  checked: { borderColor: colors.primary, backgroundColor: colors.accent },
  disabled: { opacity: 0.5 },
  text: { fontSize: 15, color: colors.foreground },
  checkedText: { color: colors.accentForeground, fontWeight: '700' },
});
