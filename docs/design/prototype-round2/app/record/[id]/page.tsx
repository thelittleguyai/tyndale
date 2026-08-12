import { notFound } from 'next/navigation'
import { RECORD_CASES } from '@/lib/tyndale-data'
import { CaseSummary } from '@/components/tyndale/case-summary'

export default async function CaseDetailPage({
  params,
}: {
  params: Promise<{ id: string }>
}) {
  const { id } = await params
  const record = RECORD_CASES.find((c) => c.id === id)
  if (!record) notFound()
  return <CaseSummary record={record} />
}
