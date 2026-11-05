import { StyleSheet, Text, View } from 'react-native';
import Svg, { Circle } from 'react-native-svg';
import { colors } from '@/theme';

const SIZE = 168;
const STROKE = 14;
const RADIUS = (SIZE - STROKE) / 2;
const CIRCUMFERENCE = 2 * Math.PI * RADIUS;

export function ScoreRing({ score, label, outOf }: { score: number; label: string; outOf: string }) {
  const filled = (Math.max(0, Math.min(100, score)) / 100) * CIRCUMFERENCE;
  return (
    // Read out as one sentence, because the ring itself carries no words.
    <View accessible accessibilityRole="image" accessibilityLabel={label} style={styles.wrap}>
      <Svg width={SIZE} height={SIZE}>
        <Circle cx={SIZE / 2} cy={SIZE / 2} r={RADIUS} stroke={colors.secondary} strokeWidth={STROKE} fill="none" />
        <Circle
          cx={SIZE / 2}
          cy={SIZE / 2}
          r={RADIUS}
          stroke={colors.primary}
          strokeWidth={STROKE}
          strokeLinecap="round"
          strokeDasharray={`${filled} ${CIRCUMFERENCE}`}
          fill="none"
          transform={`rotate(-90 ${SIZE / 2} ${SIZE / 2})`}
        />
      </Svg>
      <View style={styles.centre} importantForAccessibility="no-hide-descendants">
        <Text style={styles.score}>{score}</Text>
        <Text style={styles.outOf}>{outOf}</Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { width: SIZE, height: SIZE, alignSelf: 'center' },
  centre: { position: 'absolute', top: 0, right: 0, bottom: 0, left: 0, alignItems: 'center', justifyContent: 'center' },
  score: { fontSize: 48, fontWeight: '700', color: colors.foreground },
  outOf: { fontSize: 14, color: colors.mutedForeground },
});
