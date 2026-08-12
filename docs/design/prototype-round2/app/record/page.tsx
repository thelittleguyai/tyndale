import { redirect } from 'next/navigation'

// The rich logged-in hub now lives at /home. Keep /record as a permanent
// redirect so older links (and the case-detail back button) land on the hub.
export default function RecordPage() {
  redirect('/home')
}
