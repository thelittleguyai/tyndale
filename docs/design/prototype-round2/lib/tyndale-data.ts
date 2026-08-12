// Locked example content set (§8). Sarah / Blue Shield PPO / Riverside Imaging.
// These exact values and copy strings are doctrine — restyle containers, not words.

export const money = (n: number) =>
  n.toLocaleString('en-US', { style: 'currency', currency: 'USD' })

export const AUDIT = {
  patient: 'Sarah',
  payer: 'Blue Shield',
  plan: 'Blue Shield PPO',
  provider: 'Riverside Imaging Center',
  serviceDate: '6/14',
  service: 'MRI of the left knee + office visit',
  billed: 2347.18,
  insurerSays: 1184.6,
  shouldOwe: 612.4,
  gap: 572.2,
  responseDeadline: 'July 24',
  deductibleMet: 1850,
  deductibleTotal: 2000,
}

export type Severity = 'high' | 'medium' | 'neutral'

export type Finding = {
  id: string
  title: string
  detail: string
  impact: number
  severity: Severity
  source: string
}

export const FINDINGS: Finding[] = [
  {
    id: 'duplicate-mri',
    title: 'You were charged twice for the same MRI',
    detail:
      'The MRI of your left knee appears as two separate line items on the same date of service. It should be billed once.',
    impact: 389.0,
    severity: 'high',
    source: 'your itemized bill · CPT 73721 billed 2×',
  },
  {
    id: 'coinsurance-rate',
    title: 'The wrong coinsurance rate was applied',
    detail:
      'Your insurer applied 30% coinsurance. Your plan documents put in-network imaging at 20%. That 10% difference is yours to keep.',
    impact: 118.2,
    severity: 'medium',
    source: 'your plan documents · Summary of Benefits',
  },
  {
    id: 'facility-fee',
    title: 'A facility fee was billed against a deductible you already met',
    detail:
      'You had already met your deductible before this visit, so this facility fee should have been covered at your plan rate — not passed to you in full.',
    impact: 65.0,
    severity: 'medium',
    source: 'your EOB · deductible status $1,850 of $2,000',
  },
]

export type Verification = {
  id: string
  line: string
  aside: string
}

export const VERIFICATIONS: Verification[] = [
  {
    id: 'mri',
    line: 'An MRI of your left knee',
    aside: 'about 30 minutes in the scanner',
  },
  {
    id: 'office-visit',
    line: 'A short office visit with the doctor',
    aside: 'to review why you needed the scan',
  },
  {
    id: 'second-mri',
    line: 'A second, separate MRI on the same day',
    aside: 'this is the one that looks doubled up',
  },
]

export const PLAN_STEPS = [
  {
    id: 'call-insurer',
    order: '1',
    title: 'Call Blue Shield',
    targets: 389.0,
    subtitle: 'The duplicate MRI charge and the coinsurance rate',
    phone: '1-800-555-0142',
    claim: 'CLM-4471902',
    script: [
      {
        heading: 'When they pick up',
        body: "Hi, I'm calling about claim CLM-4471902 for a date of service on June 14th. I've reviewed my EOB against my plan documents and I've found two issues I'd like corrected.",
      },
      {
        heading: 'The problem',
        body: 'First, an MRI of my left knee, CPT 73721, was billed twice on the same day. It was only performed once. Second, my coinsurance was processed at 30%, but my Summary of Benefits lists in-network imaging at 20%.',
      },
      {
        heading: 'The ask',
        body: "I'd like the duplicate line removed and the claim reprocessed at my correct 20% coinsurance rate. Can you open a reprocessing request today?",
      },
      {
        heading: 'Get it in writing',
        body: "Can you give me a reference number for this request, and confirm the date I should expect the corrected EOB? I'd like that in writing or by email if possible.",
      },
    ],
    pushback: [
      {
        theyMight: '“The claim was processed correctly.”',
        youSay:
          "My Summary of Benefits lists in-network imaging at 20% coinsurance. Can you read me the coinsurance rate on file for this claim so we can compare?",
      },
      {
        theyMight: '“We only see one MRI charge.”',
        youSay:
          'My itemized bill shows CPT 73721 on two separate lines for June 14th. Can we walk through the line items together?',
      },
    ],
  },
  {
    id: 'call-billing',
    order: '2',
    title: "Call the imaging center's billing office",
    targets: 183.0,
    subtitle: 'The facility fee and the corrected balance',
    phone: '1-800-555-0177',
    claim: 'Account RIV-88231',
    script: [
      {
        heading: 'When they pick up',
        body: "Hi, I'm calling about account RIV-88231 for a visit on June 14th. I'd like to go over a facility fee on my itemized bill.",
      },
      {
        heading: 'The problem',
        body: 'A facility fee was billed against my deductible, but my deductible was already met before this visit. It should have been adjusted to my plan rate.',
      },
      {
        heading: 'The ask',
        body: "Can you rebill this line reflecting that my deductible was met, and send me an updated itemized statement once it's corrected?",
      },
      {
        heading: 'Get it in writing',
        body: "Please note the correction on my account and send the updated statement to my email. Can I get a reference number for today's call?",
      },
    ],
    pushback: [
      {
        theyMight: '“That fee is standard and non-negotiable.”',
        youSay:
          'I understand the fee itself is standard. My issue is how it was applied to my deductible — which my EOB shows was already met. Can we look at that together?',
      },
    ],
  },
  {
    id: 'escalate',
    order: '3',
    title: 'If either one pushes back — the escalation',
    targets: 0,
    subtitle: 'A supervisor, then a written appeal or state complaint',
    phone: '',
    claim: '',
    script: [
      {
        heading: 'Ask for a supervisor',
        body: "I'd like to escalate this to a supervisor. I've identified a billing error with documentation and I'd like it reviewed for a formal appeal.",
      },
      {
        heading: 'Put it in writing',
        body: 'I want to file a written appeal. Can you tell me the address or portal for appeals and the deadline to submit?',
      },
      {
        heading: 'The next rung',
        body: "If we can't resolve this, I understand I can file a complaint with my state's Department of Insurance. I'd prefer to settle it with you first.",
      },
    ],
    pushback: [],
  },
]

export type CaseStatus = 'resolved' | 'waiting' | 'needs'

export type RecordCase = {
  id: string
  provider: string
  service: string
  date: string
  status: CaseStatus
  statusLabel: string
  recovered: number
  deadline?: string
}

export const RECORD_CASES: RecordCase[] = [
  {
    id: 'riverside-0614',
    provider: 'Riverside Imaging Center',
    service: 'MRI left knee + office visit',
    date: 'Jun 14, 2026',
    status: 'waiting',
    statusLabel: 'Waiting on insurer — due July 24',
    recovered: 0,
    deadline: 'July 24',
  },
  {
    id: 'mercy-lab-0322',
    provider: 'Mercy General Lab',
    service: 'Bloodwork panel',
    date: 'Mar 22, 2026',
    status: 'resolved',
    statusLabel: 'Resolved — recovered $214',
    recovered: 214,
  },
  {
    id: 'valley-er-0108',
    provider: 'Valley Urgent Care',
    service: 'Urgent care visit',
    date: 'Jan 8, 2026',
    status: 'needs',
    statusLabel: 'Needs your EOB',
    recovered: 0,
  },
]

export const LIFETIME_RECOVERED = 786.2
export const TOTAL_MEMBER_SAVINGS = 504100

export const DISCLAIMER =
  'Tyndale provides medical billing and coverage advocacy, not medical, legal, or financial advice.'

// ── Dashboard / relationship (§4.6, §8) ──────────────────────────────────
export const USER = {
  firstName: 'Sarah',
  plan: 'Blue Shield PPO',
  deductibleMet: 1850,
  deductibleTotal: 2000,
  oopMet: 3200,
  oopTotal: 5000,
}

// "Remembers your case" proof — the second plan detail (§4.1.5, §8)
export const REMEMBERED_CASE = {
  plan: 'UnitedHealthcare Choice Plus',
  deductibleMet: 1750,
  openCase: 'St. Anne — appeal due Jul 24',
  priorRecoveries: 890,
  priorBills: 2,
}

// Quick check-in — surfaces FIRST on login (§4.6)
export const CHECK_IN = {
  id: 'riverside-0614',
  prompt: 'You were going to call Blue Shield — how did it go?',
  context:
    'This is about the duplicate MRI charge and the 30% coinsurance rate on your Riverside Imaging visit. Together they target $507 back.',
  provider: 'Riverside Imaging Center',
  target: 507.2,
}

// ── Landing bands ─────────────────────────────────────────────────────────
export const GROUNDING_CHIPS = [
  'CPT / NCCI code rules',
  "Your plan's benefits",
  'Your EOBs',
  'Your deductible & out-of-pocket max',
  'Published hospital & insurer prices',
  'Federal & state law',
  "Your insurer's own policies",
]

export const COMPARISON: { generic: string; tyndale: string }[] = [
  {
    generic: "Takes the insurer's numbers at face value",
    tyndale: "Independently recomputes, then audits your insurer's own math",
  },
  {
    generic: 'Guesses a "usual" price from memory',
    tyndale: 'Checks against real published prices',
  },
  {
    generic: 'Two different answers if you ask twice',
    tyndale: 'Deterministic math, and shows its work',
  },
  {
    generic: 'Can invent a citation',
    tyndale: 'Cites the actual statute or plan clause so you can verify',
  },
]

export const AUDIT_WORKLINES = [
  'Read your bill & codes',
  "Double-checked your doctor's charges",
  'Scanned for duplicate charges',
  "Checked your plan's rules",
  'Compared to published prices',
]

export const STATS: { value: string; label: string }[] = [
  { value: '74%', label: 'of people who disputed a billing error got it corrected' },
  { value: '19%', label: 'of claims are denied, yet fewer than 1% ever appealed' },
  { value: '100M+', label: 'Americans carry medical debt' },
  { value: '45%', label: "of hospitals don't routinely send an itemized bill in 30 days" },
]

export const STATS_SOURCE = 'Sources: JAMA · KFF. Every stat verified and cited.'

export const TIPS = [
  'Always demand the itemized bill',
  'Catch duplicate & unbundled charges',
  'Use the $400 dispute right',
  'Anchor to the posted cash price',
  'Claim charity care most never hear about',
  'Win the appeal insurers expect you to skip',
]

// ── Feature surfaces (§4.8) ───────────────────────────────────────────────
export const ESTIMATE_EXAMPLE = {
  procedure: 'MRI, left knee (CPT 73721)',
  provider: 'Riverside Imaging Center',
  low: 180,
  expected: 210,
  high: 260,
  listPrice: 890,
  rationale:
    "You've met $1,850 of your $2,000 deductible, so this MRI should cost you about $210 — not the $890 list price.",
  sources: ['Your plan: Blue Shield PPO', 'Published rate: CMS + hospital price file'],
}

export type DoctorResult = {
  id: string
  name: string
  specialty: string
  distance: string
  network: string
  rating: number
  reviews: number
  costSignal: string
}

export const DOCTORS: DoctorResult[] = [
  {
    id: 'chen',
    name: 'Dr. Amara Chen',
    specialty: 'Orthopedic surgery',
    distance: '2.1 mi',
    network: 'Listed in-network — confirm with one call',
    rating: 4.8,
    reviews: 212,
    costSignal: 'Lower-cost for your plan',
  },
  {
    id: 'okafor',
    name: 'Dr. James Okafor',
    specialty: 'Orthopedic surgery',
    distance: '3.4 mi',
    network: 'Listed in-network — confirm with one call',
    rating: 4.6,
    reviews: 156,
    costSignal: 'Average cost',
  },
  {
    id: 'reyes',
    name: 'Dr. Nina Reyes',
    specialty: 'Sports medicine',
    distance: '5.0 mi',
    network: 'Network status unclear — worth a call before booking',
    rating: 4.9,
    reviews: 98,
    costSignal: 'Cost signal thin — ask for a quote',
  },
]

export type VisitCheckItem = {
  id: string
  label: string
  detail: string
  status: 'done' | 'action' | 'pending'
  action?: string
}

export const VISIT_PLAN: { provider: string; date: string; items: VisitCheckItem[] } = {
  provider: 'Riverside Orthopedics',
  date: 'Aug 12',
  items: [
    {
      id: 'referral',
      label: 'Referral on file',
      detail: 'Your PPO does not require a referral for orthopedics.',
      status: 'done',
    },
    {
      id: 'priorauth',
      label: 'Prior authorization for imaging',
      detail:
        'If they order an MRI, your plan needs prior auth first. Confirm it is submitted and get the auth number.',
      status: 'action',
      action: "Call script: confirm prior auth & get the auth #",
    },
    {
      id: 'preventive',
      label: 'Preventive vs. billable',
      detail:
        'This is a follow-up visit, so it will likely be billable toward your deductible — not a free preventive visit.',
      status: 'pending',
    },
  ],
}
