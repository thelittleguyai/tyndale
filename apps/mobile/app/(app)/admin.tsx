/**
 * Admin area — reached from the header "Admin" pill (distinct from Settings).
 * Admin-only: non-admin users are bounced to the dashboard. Real admin tooling
 * (user management, feedback/de-id review, BAA tracker) lands in a later phase;
 * for now this is the gated shell so the pill has a real destination.
 */

import { useEffect, useState } from 'react';
import { ActivityIndicator, Pressable, ScrollView, Text, View } from 'react-native';
import { Redirect, useRouter } from 'expo-router';
import { ShieldCheck } from 'lucide-react-native';

import { getUserProfile, type UserProfile } from '../../lib/api-client';

export default function AdminScreen() {
  const router = useRouter();
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getUserProfile()
      .then(setProfile)
      .catch(() => setProfile(null))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <View className="flex-1 items-center justify-center bg-navy-deep">
        <ActivityIndicator color="#fff" />
      </View>
    );
  }

  // Admin-only: bounce non-admins back to the dashboard.
  if (profile?.user_type !== 'admin') {
    return <Redirect href="/" />;
  }

  return (
    <ScrollView className="flex-1 bg-navy-deep" contentContainerStyle={{ padding: 20, paddingTop: 28 }}>
      <Pressable onPress={() => router.push('/')} className="mb-5 self-start">
        <Text className="text-sm text-white/60">← Back to dashboard</Text>
      </Pressable>

      <View className="mb-6 flex-row items-center gap-3">
        <View className="h-10 w-10 items-center justify-center rounded-xl bg-sage/20">
          <ShieldCheck size={20} color="#3DAA7E" />
        </View>
        <View className="flex-1">
          <Text className="text-3xl font-bold text-white">Admin</Text>
          <Text className="text-sm text-white/60">Signed in as {profile?.email}</Text>
        </View>
      </View>

      <Section title="Admin tools">
        <ComingSoonRow label="User management" hint="View and manage Tyndale accounts" />
        <ComingSoonRow label="Feedback & de-identification review" hint="Approve training labels before Full V1" />
        <ComingSoonRow label="BAA tracker" hint="Vendor business-associate agreement status" />
      </Section>

      <Text className="mt-8 text-center text-xs leading-5 text-white/40">
        Admin tooling is built out in a later phase — this is the gated shell. You can see it
        because your account type is "admin".
      </Text>
    </ScrollView>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <View className="mb-4 rounded-2xl border border-white/10 bg-navy-soft p-5">
      <Text className="mb-3 text-xs uppercase tracking-widest text-white/45">{title}</Text>
      {children}
    </View>
  );
}

function ComingSoonRow({ label, hint }: { label: string; hint: string }) {
  return (
    <View className="mb-3 flex-row items-center justify-between">
      <View className="flex-1 pr-3">
        <Text className="text-sm font-semibold text-white/90">{label}</Text>
        <Text className="text-xs text-white/50">{hint}</Text>
      </View>
      <View className="rounded-full bg-white/5 px-2 py-0.5">
        <Text className="text-[10px] font-semibold text-white/40">Coming soon</Text>
      </View>
    </View>
  );
}
