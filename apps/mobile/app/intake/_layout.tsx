/**
 * Intake wizard layout (Phase CO-1A). Plain stack; each step renders its own
 * chrome (progress bar + Save & exit) via WizardShell.
 */

import { Stack } from 'expo-router';

export default function IntakeLayout() {
  return (
    <Stack
      screenOptions={{ headerShown: false, contentStyle: { backgroundColor: '#091621' } }}
    />
  );
}
