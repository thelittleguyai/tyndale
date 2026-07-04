// Legal content — single source of truth for the Terms of Service, Privacy
// Policy (incl. the Data Improvement Consent + State-Specific Rights Addendum
// sections), shared by apps/mobile and apps/web-marketing.
//
// This module holds ONLY the structured copy + the single-source publication
// fields. Rendering is per-framework: apps/mobile renders these blocks with
// React Native / NativeWind; apps/web-marketing renders them with Next.js /
// Tailwind. Both import from here so the legal text lives in exactly one place.
//
// SOURCE: the launch-candidate drafts in `Additional Files/` (01_terms_of_service,
// 02_privacy_policy, 03_improvement_consent, 04_state_specific_rights_addendum).
// The text below is faithful to those drafts — formatting/wiring only, no
// re-authoring or softening of legal language.
//
// ── Publication gate (LEGAL_PUBLISHED) ────────────────────────────────────────
// The copy below is the REAL, launch-candidate legal text. It is rendered
// whether or not the flag is set. The flag only controls the DRAFT banner and
// the open fill-in fields:
//
//   LEGAL_PUBLISHED = false (default)  →  render real copy + a top "DRAFT —
//       under attorney review, not yet in effect" banner, and render the open
//       fields as obvious fill-ins ([SUPPORT EMAIL], [PRIVACY EMAIL],
//       [EFFECTIVE DATE]).
//   LEGAL_PUBLISHED = true (post-signoff)  →  banner disappears; the fields
//       resolve to the real values in LEGAL_FIELDS below. Publication becomes a
//       one-line env flip (see EXPO_PUBLIC_LEGAL_PUBLISHED / NEXT_PUBLIC_LEGAL_PUBLISHED).
//
// Each app reads its own env var and passes the resolved boolean into the
// helpers here; this module has no direct access to process.env so it stays
// framework-agnostic and testable.

// ── Single-source publication fields ─────────────────────────────────────────
// Fill these in ONE place when counsel signs off. Until then they are empty and
// the helpers below fall back to visible placeholders while the flag is false.
export const LEGAL_FIELDS = {
  /** Public support address. Used in Terms §§5, 13, 14, 18 and Privacy §9. */
  supportEmail: '', // e.g. 'support@tyndaleapp.net' — NOT YET AVAILABLE (Cowork to revisit)
  /** Privacy contact address. Used in Privacy §§9, 11, 13 and the addendum. */
  privacyEmail: '', // e.g. 'privacy@tyndaleapp.net' — NOT YET AVAILABLE (Cowork to revisit)
  /** Effective date — set on the day of publication. */
  effectiveDate: '', // e.g. 'August 1, 2026'
  /** Business entity + mailing address (already confirmed in the drafts). */
  entity: 'The Little Guy LLC d/b/a Tyndale',
  mailingAddress: '336 E University Pkwy #1043, Orem, Utah 84058',
} as const;

/** Obvious fill-in markers shown while a field is empty (draft mode). */
const PLACEHOLDER = {
  supportEmail: '[SUPPORT EMAIL]',
  privacyEmail: '[PRIVACY EMAIL]',
  effectiveDate: '[EFFECTIVE DATE]',
} as const;

/**
 * Resolve a single-source field to either its real value (once filled) or its
 * visible placeholder. Placeholders always show when the value is empty,
 * regardless of the flag, so an accidental publish can never surface a blank.
 */
export function legalField(key: keyof typeof PLACEHOLDER): string {
  const real: string = LEGAL_FIELDS[key];
  return real.trim().length > 0 ? real : PLACEHOLDER[key];
}

/** The advocacy-not-advice disclaimer, surfaced on every legal surface. */
export const ADVOCACY_DISCLAIMER =
  'Tyndale is a medical-billing and health-advocacy tool. It provides information and ' +
  'self-advocacy assistance only — it is not medical, legal, financial, or tax advice, ' +
  'and using it does not create an attorney-client relationship. For advice about your ' +
  'situation, consult a licensed professional.';

/** Banner text shown at the top of every legal surface while unpublished. */
export const DRAFT_BANNER_TEXT =
  'DRAFT — under attorney review, not yet in effect. This is launch-candidate copy; the ' +
  'fields marked in brackets are filled in on publication.';

// ── Structured content model ─────────────────────────────────────────────────
// A document is an ordered list of sections; each section has a heading and a
// list of blocks. Blocks are paragraphs, bullet lists, or a "callout" (used for
// the all-caps disclaimer/liability sections and the plain-language consent box).
export type LegalBlock =
  | { kind: 'p'; text: string }
  | { kind: 'bullets'; items: string[] }
  | { kind: 'callout'; text: string };

export interface LegalSection {
  /** Optional section number/label, e.g. '1'. Omitted for intro/contact blocks. */
  num?: string;
  heading: string;
  blocks: LegalBlock[];
}

export interface LegalDoc {
  title: string;
  /** Rendered as "Effective Date: …" — resolves via legalField('effectiveDate'). */
  showsEffectiveDate: boolean;
  /** Short intro paragraph(s) shown above the first numbered section. */
  intro: LegalBlock[];
  sections: LegalSection[];
}

// Build the docs as functions so field resolution happens at render time (after
// the consuming app has decided whether the flag is on).
export function buildTermsDoc(): LegalDoc {
  const support = legalField('supportEmail');
  return {
    title: 'Tyndale Terms of Service',
    showsEffectiveDate: true,
    intro: [
      {
        kind: 'p',
        text:
          'These Terms of Service ("Terms") are a binding agreement between you and The Little Guy LLC, ' +
          'doing business as Tyndale ("Tyndale," "we," "us," or "our"), a Utah limited liability company. ' +
          'They govern your access to and use of the Tyndale website, applications, and services (together, the "Service").',
      },
      {
        kind: 'p',
        text:
          'By creating an account or using the Service, you agree to these Terms, our Privacy Policy, and the ' +
          'acknowledgments in Section 9. If you do not agree, do not use the Service.',
      },
    ],
    sections: [
      {
        num: '1',
        heading: 'What Tyndale is — and is not',
        blocks: [
          {
            kind: 'p',
            text:
              'Tyndale is a medical-billing reconciliation and health-advocacy tool. It helps you review medical ' +
              'bills and insurance statements, identify potential billing and coverage errors, understand what you ' +
              'may owe, and take action to resolve issues.',
          },
          { kind: 'p', text: 'Tyndale does not provide, and is not a substitute for:' },
          {
            kind: 'bullets',
            items: [
              'Medical advice, diagnosis, or treatment. Tyndale is not a doctor or clinical resource and will not answer clinical questions.',
              'Legal advice or legal representation. Tyndale provides general information about billing and insurance rules and helps you advocate for yourself. It is not a law firm, does not provide legal advice, and your use of it does not create an attorney-client relationship.',
              'Financial, investment, credit, or tax advice.',
              'Any guarantee of outcome. Tyndale does not guarantee that any bill will be reduced, that any error will be corrected, that any appeal or dispute will succeed, or that you will recover any amount.',
            ],
          },
          {
            kind: 'p',
            text:
              'You are responsible for your own decisions. Tyndale provides information and assistance; you decide ' +
              'whether and how to act on it.',
          },
        ],
      },
      {
        num: '2',
        heading: 'Eligibility — adults only',
        blocks: [
          {
            kind: 'p',
            text:
              'You must be at least 18 years old and able to enter into a binding contract to use the Service, ' +
              'which is available to users in the United States only.',
          },
          {
            kind: 'p',
            text:
              'Minors may not create accounts or use the Service. A parent or legal guardian who is 18 or older may ' +
              'use the Service to manage medical bills and related matters on behalf of their minor child. By doing ' +
              "so, you represent and warrant that you are the parent or legal guardian with authority to act on the " +
              "child's behalf and to provide the child's information to Tyndale for that purpose.",
          },
          { kind: 'p', text: 'By using the Service, you represent that you meet these requirements.' },
        ],
      },
      {
        num: '3',
        heading: 'Your account',
        blocks: [
          {
            kind: 'p',
            text:
              'You must create an account to use most features. You agree to provide accurate information, keep your ' +
              'login credentials secure, and remain responsible for activity under your account. Notify us promptly ' +
              'of any unauthorized use.',
          },
          {
            kind: 'p',
            text:
              'We will never create an account on your behalf, and we will never ask you to share your password with ' +
              'us or anyone else.',
          },
        ],
      },
      {
        num: '4',
        heading: 'How the Service works, and your responsibilities',
        blocks: [
          {
            kind: 'p',
            text:
              'To help you, Tyndale relies on information you provide — uploaded documents (such as bills, insurance ' +
              'statements, and insurance cards), your answers to its questions, and, if you choose to connect it in ' +
              'the future, data from your insurer or providers.',
          },
          { kind: 'p', text: 'You are responsible for:' },
          {
            kind: 'bullets',
            items: [
              'The accuracy of the information and documents you provide.',
              'Confirming, when Tyndale asks, details it cannot verify on its own — for example, whether a billed service matches what actually happened during your care.',
              'Reviewing any communication, script, or document before you send, sign, or act on it.',
            ],
          },
          {
            kind: 'p',
            text:
              "Tyndale will never send a communication on your behalf without your explicit approval. Tyndale's " +
              'analysis is only as good as the information available to it; where information is incomplete, Tyndale ' +
              'will tell you what it can and cannot conclude.',
          },
        ],
      },
      {
        num: '5',
        heading: 'Free and paid plans; billing and cancellation',
        blocks: [
          {
            kind: 'p',
            text:
              'We offer a free tier with limited use and paid subscription plans. Current features and pricing are ' +
              'shown in the Service. As of the Effective Date, paid plans are $11.99 per month or $100 per year for ' +
              'unlimited use.',
          },
          {
            kind: 'bullets',
            items: [
              'Paid plans renew automatically until canceled. You authorize us, through our third-party payment processor, to charge your payment method at the start of each billing period.',
              'You may cancel at any time, and cancellation takes effect at the end of your current billing period. We do not provide prorated refunds for partial periods, except where required by law.',
              'We may change pricing on a going-forward basis with advance notice as required by law.',
              'We do not store your full payment card details. Payments are processed by a third-party payment processor, and you must enter your payment information yourself.',
            ],
          },
          { kind: 'p', text: `To cancel, use the account settings in the Service or contact us at ${support}.` },
        ],
      },
      {
        num: '6',
        heading: 'Intellectual property',
        blocks: [
          {
            kind: 'p',
            text:
              'The Service — including its software, content, and design — is owned by Tyndale and protected by law. ' +
              'We grant you a limited, non-exclusive, non-transferable, revocable license to use the Service for your ' +
              'personal, non-commercial purposes. You may not copy, modify, reverse-engineer, scrape, resell, or ' +
              'create derivative works from the Service.',
          },
          {
            kind: 'p',
            text:
              'Documents Tyndale generates for you, such as draft letters or summaries, are yours to use for your own ' +
              'advocacy. Information and content you provide remain yours; you grant us the license described in the ' +
              'Privacy Policy to operate the Service for you.',
          },
        ],
      },
      {
        num: '7',
        heading: 'Third-party services',
        blocks: [
          {
            kind: 'p',
            text:
              'The Service relies on third parties — for example, cloud hosting, AI processing, payment processing, ' +
              'email delivery, and (in the future) data-connection services. We are not responsible for third-party ' +
              'services, and your use of them may be governed by their own terms.',
          },
        ],
      },
      {
        num: '8',
        heading: 'Acceptable use',
        blocks: [
          { kind: 'p', text: 'You agree not to:' },
          {
            kind: 'bullets',
            items: [
              'Use the Service if you are under 18, or create an account for someone who is.',
              'Provide information about another adult without their authorization, or about a minor for whom you are not the parent or legal guardian.',
              'Provide false or fraudulent information, or use the Service to commit or facilitate fraud, including insurance fraud.',
              'Access accounts, data, or systems that are not yours.',
              'Reverse-engineer, scrape, copy, or build a competing product from the Service.',
              'Circumvent usage limits, including by creating multiple accounts to evade free-tier limits.',
              "Interfere with the Service's operation or security, or upload malicious code.",
              'Use the Service for any unlawful purpose, or rely on it as a substitute for professional medical, legal, or financial advice.',
            ],
          },
          {
            kind: 'p',
            text:
              'We may investigate suspected violations and may suspend or terminate access, remove content, and take ' +
              'legal action where appropriate.',
          },
        ],
      },
      {
        num: '9',
        heading: 'Important acknowledgments',
        blocks: [
          { kind: 'p', text: 'By using the Service, you acknowledge and agree that:' },
          {
            kind: 'bullets',
            items: [
              'It is not medical advice. For medical concerns, consult a licensed healthcare provider.',
              'It is not legal advice. Tyndale is not a law firm and provides general information and self-advocacy assistance only. Laws vary by state and change over time; applying them to your situation may require a licensed attorney. For legal advice, consult one.',
              'It is not financial or tax advice. Decisions about paying, financing, or disputing bills are yours; for financial or tax advice, consult a qualified professional.',
              'No outcome is guaranteed. Results depend on factors outside Tyndale’s control, including the decisions of providers, insurers, and government bodies.',
              'Accuracy depends on your information. Tyndale audits the information available to it but cannot detect issues in information it does not have. You are responsible for the accuracy of what you provide and for confirming details Tyndale asks you to verify.',
              'You review before you act. You are responsible for reviewing any script, summary, or draft communication before you send, sign, or rely on it.',
            ],
          },
        ],
      },
      {
        num: '10',
        heading: 'Disclaimers',
        blocks: [
          {
            kind: 'callout',
            text:
              'THE SERVICE IS PROVIDED "AS IS" AND "AS AVAILABLE," WITHOUT WARRANTIES OF ANY KIND, WHETHER EXPRESS, ' +
              'IMPLIED, OR STATUTORY, INCLUDING WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE, ' +
              'ACCURACY, AND NON-INFRINGEMENT. WE DO NOT WARRANT THAT THE SERVICE WILL BE UNINTERRUPTED OR ERROR-FREE, ' +
              'OR THAT ANY ANALYSIS, ESTIMATE, OR RECOMMENDATION WILL BE ACCURATE OR ACHIEVE ANY PARTICULAR RESULT.',
          },
        ],
      },
      {
        num: '11',
        heading: 'Limitation of liability',
        blocks: [
          {
            kind: 'callout',
            text:
              'TO THE MAXIMUM EXTENT PERMITTED BY LAW, TYNDALE AND ITS OWNERS, EMPLOYEES, AND CONTRACTORS WILL NOT BE ' +
              'LIABLE FOR ANY INDIRECT, INCIDENTAL, SPECIAL, CONSEQUENTIAL, OR PUNITIVE DAMAGES, OR FOR ANY LOSS OF ' +
              'DATA, USE, OR GOODWILL, ARISING FROM YOUR USE OF THE SERVICE. OUR TOTAL LIABILITY FOR ANY CLAIM ARISING ' +
              'FROM THE SERVICE WILL NOT EXCEED THE GREATER OF (A) THE AMOUNT YOU PAID US IN THE TWELVE MONTHS BEFORE ' +
              'THE CLAIM OR (B) ONE HUNDRED U.S. DOLLARS ($100).',
          },
          {
            kind: 'p',
            text:
              'Some states do not allow certain limitations, so some of the above may not apply to you. Nothing in ' +
              'these Terms limits liability that cannot be limited under applicable law.',
          },
        ],
      },
      {
        num: '12',
        heading: 'Indemnification',
        blocks: [
          {
            kind: 'p',
            text:
              'You agree to indemnify and hold harmless Tyndale and its owners, employees, and contractors from ' +
              "claims, damages, and expenses (including reasonable attorneys' fees) arising out of your misuse of the " +
              'Service, your violation of these Terms, or your violation of any law or third-party right.',
          },
        ],
      },
      {
        num: '13',
        heading: 'Dispute resolution; informal resolution first',
        blocks: [
          {
            kind: 'p',
            text:
              'Most disputes can be resolved quickly. Before filing any formal claim, you agree to first contact us ' +
              `at ${support} and give us 30 days to resolve the issue informally.`,
          },
        ],
      },
      {
        num: '14',
        heading: 'Binding arbitration and class-action waiver',
        blocks: [
          { kind: 'p', text: 'PLEASE READ THIS SECTION CAREFULLY — IT AFFECTS YOUR LEGAL RIGHTS.' },
          {
            kind: 'p',
            text:
              'If a dispute is not resolved informally, you and Tyndale agree to resolve it through binding individual ' +
              'arbitration rather than in court, except that either party may bring a claim in small-claims court if ' +
              'it qualifies. The arbitration will be administered by a recognized arbitration provider under its ' +
              'consumer rules, and may take place in your home state or by videoconference.',
          },
          {
            kind: 'p',
            text:
              'Class-action waiver. You and Tyndale agree that each may bring claims against the other only in an ' +
              'individual capacity, and not as a plaintiff or class member in any purported class or representative ' +
              'proceeding.',
          },
          {
            kind: 'p',
            text:
              'Your right to opt out. You may opt out of this arbitration agreement within 30 days of first accepting ' +
              `these Terms by sending notice to ${support} with your name and account email. If you opt out, disputes ` +
              'will be resolved in the state or federal courts located in Utah.',
          },
        ],
      },
      {
        num: '15',
        heading: 'Governing law',
        blocks: [
          {
            kind: 'p',
            text:
              'These Terms are governed by the laws of the State of Utah, without regard to its conflict-of-laws ' +
              "principles, except where your state's consumer-protection laws provide rights that cannot be waived by " +
              'agreement. Subject to Section 14, the state and federal courts located in Utah will have jurisdiction ' +
              'over any disputes not subject to arbitration.',
          },
        ],
      },
      {
        num: '16',
        heading: 'Changes to these Terms',
        blocks: [
          {
            kind: 'p',
            text:
              'We may update these Terms. If we make material changes, we will notify you by email or in-app notice ' +
              'and update the Effective Date. Your continued use of the Service after the changes take effect means ' +
              'you accept the updated Terms. If you do not agree, stop using the Service and close your account.',
          },
        ],
      },
      {
        num: '17',
        heading: 'Termination',
        blocks: [
          {
            kind: 'p',
            text:
              'You may stop using the Service and close your account at any time. We may suspend or terminate your ' +
              'access for violation of these Terms or for any lawful reason. Provisions that by their nature should ' +
              'survive termination — including ownership, disclaimers, limitation of liability, indemnification, and ' +
              'dispute resolution — survive.',
          },
        ],
      },
      {
        num: '18',
        heading: 'Contact',
        blocks: [
          {
            kind: 'p',
            text: `${LEGAL_FIELDS.entity}\n${LEGAL_FIELDS.mailingAddress}\n${support}`,
          },
          {
            kind: 'p',
            text:
              'By creating an account, you confirm that you are at least 18 years old and that you have read and agree ' +
              'to these Terms of Service and the Privacy Policy.',
          },
        ],
      },
    ],
  };
}

export function buildPrivacyDoc(): LegalDoc {
  const support = legalField('supportEmail');
  const privacy = legalField('privacyEmail');
  return {
    title: 'Tyndale Privacy Policy',
    showsEffectiveDate: true,
    intro: [
      {
        kind: 'p',
        text:
          'This Privacy Policy explains what information The Little Guy LLC, doing business as Tyndale ("Tyndale," ' +
          '"we," "us," or "our") collects, how we use and share it, and the choices and rights you have. It applies ' +
          'to the Tyndale website, applications, and services (the "Service"). The Service is for adults (18 or ' +
          'older) in the United States.',
      },
      {
        kind: 'p',
        text:
          'We take privacy seriously because the Service handles sensitive health and financial information. We use ' +
          'your information to provide the Service to you. We do not sell your personal information, and we do not ' +
          'use your health or financial information for advertising.',
      },
      {
        kind: 'p',
        text:
          'About our regulatory status. Tyndale is a direct-to-consumer tool. You voluntarily provide your own ' +
          'information so that Tyndale can help you with your own bills. Tyndale is not acting as a healthcare ' +
          'provider or health plan, and it is not a "covered entity" under HIPAA. We are committed to protecting ' +
          'your information and handle it in accordance with this Policy and applicable federal and state law, ' +
          'including the Federal Trade Commission Act and the FTC Health Breach Notification Rule, and applicable ' +
          'state privacy and health-data laws.',
      },
    ],
    sections: [
      {
        num: '1',
        heading: 'Information we collect',
        blocks: [
          { kind: 'p', text: 'Information you provide:' },
          {
            kind: 'bullets',
            items: [
              'Account information — your name, email address, and password; for paid plans, billing information handled by our payment processor (we do not store full card numbers).',
              'Documents you upload — such as medical bills, Explanation of Benefits (EOB) statements, insurance cards, and plan summaries — and the information extracted from them.',
              'Information about your coverage and your care that you enter or confirm.',
              'Communications you send us, such as support requests and feedback.',
            ],
          },
          {
            kind: 'p',
            text:
              "Information about minors, handled on a parent or guardian's behalf: If you use the Service to manage a " +
              "minor child's medical bills, you may provide the child's health and billing information. You represent " +
              'that you are the parent or legal guardian with authority to do so. We handle that information as ' +
              'described in this Policy. The Service is not directed to children, and children may not create accounts.',
          },
          {
            kind: 'p',
            text:
              'Information you may choose to connect in the future: If, in a future version, you choose to connect ' +
              'your insurer or provider data through a data-connection service, we will receive your coverage and ' +
              'claims information from that source to provide the Service. We will describe this clearly and obtain ' +
              'your authorization before any such connection.',
          },
          {
            kind: 'p',
            text:
              'Information collected automatically: Limited device and usage information and cookies or similar ' +
              'technologies, as described in Section 8.',
          },
        ],
      },
      {
        num: '2',
        heading: 'The sensitive nature of this information',
        blocks: [
          {
            kind: 'p',
            text:
              'Much of what you provide is health and financial information. We apply heightened protections to it, ' +
              'we do not use it for advertising, and we limit who can access it. We use it to operate the Service for ' +
              'you and — only if you separately opt in — to improve the Service, as described in Section 5.',
          },
        ],
      },
      {
        num: '3',
        heading: 'How we use your information',
        blocks: [
          { kind: 'p', text: 'We use your information to:' },
          {
            kind: 'bullets',
            items: [
              'Provide the Service — read and analyze your documents, compute what you may owe, identify potential errors, and help you take action.',
              'Maintain your account, history, and case files so the Service can remember your context and track deadlines and follow-ups for you.',
              'Communicate with you about your account, your matters, and the Service.',
              'Process your payments, through our payment processor.',
              'Maintain security, prevent fraud and abuse, and comply with law.',
              'Improve the Service — only with your separate, optional opt-in, and only after de-identification (see Section 5).',
            ],
          },
        ],
      },
      {
        num: '4',
        heading: 'How the AI uses your information',
        blocks: [
          {
            kind: 'p',
            text:
              'Tyndale uses artificial intelligence to analyze your documents and information. Your information is ' +
              'processed by AI service providers under contracts that require them to protect it and that prohibit ' +
              'them from using your information to train their own general models. The AI grounds its analysis in ' +
              'authoritative data sources and your own documents and is designed not to assert facts it cannot support.',
          },
        ],
      },
      {
        num: '5',
        heading: 'Improving the Service — separate, optional consent',
        blocks: [
          {
            kind: 'p',
            text:
              'Using your information to improve Tyndale is different from using it to serve you, and we treat it that ' +
              'way. We will use your bills, feedback, and case outcomes to improve the Service only if you separately ' +
              'opt in, and even then only after de-identification — an automated and reviewed process that removes ' +
              'information identifying you. This consent is optional, is never required to use the Service, and you ' +
              'can withdraw it at any time in your settings. See our separate Data Improvement Consent (below) for details.',
          },
        ],
      },
      {
        num: '6',
        heading: 'How we share information',
        blocks: [
          { kind: 'p', text: 'We share information only as needed to run the Service:' },
          {
            kind: 'bullets',
            items: [
              'Service providers that help us operate — such as cloud hosting, AI processing, payment processing, email delivery, and (in the future) data-connection services. They are bound by contract to protect your information and to use it only to provide services to us.',
              'At your direction — for example, a letter or communication you approve to be sent to your insurer or provider.',
              'For legal and safety reasons — to comply with law, respond to lawful requests, enforce our Terms, or protect rights and safety.',
              'In a business transfer — if we are involved in a merger, acquisition, or sale of assets, information may transfer as part of that transaction, subject to this Policy.',
            ],
          },
          {
            kind: 'p',
            text:
              'We do not sell or rent your personal information, and we do not share your health or financial ' +
              'information with advertisers.',
          },
        ],
      },
      {
        num: '7',
        heading: 'Security',
        blocks: [
          {
            kind: 'p',
            text:
              'We implement administrative, technical, and physical safeguards designed to protect your information, ' +
              'including encryption of sensitive data in transit and at rest, access controls, audit logging, and ' +
              'removal of identifying information from internal system logs. No system is perfectly secure, and we ' +
              'cannot guarantee absolute security. If a breach affecting your information occurs, we will notify you ' +
              'and applicable authorities as required by law, including the FTC Health Breach Notification Rule and ' +
              'applicable state breach-notification laws.',
          },
        ],
      },
      {
        num: '8',
        heading: 'Cookies & tracking',
        blocks: [
          { kind: 'p', text: 'We use cookies and similar technologies to operate the Service:' },
          {
            kind: 'bullets',
            items: [
              'Strictly necessary technologies that are required to run the Service, keep you logged in, and maintain security. These cannot be turned off.',
              'Functional technologies that remember your preferences.',
              'Analytics — we use privacy-respecting, first-party analytics to understand how the Service is used and to improve it. We do not use advertising or retargeting trackers, and we do not place advertising trackers on any page that handles your health or billing information.',
            ],
          },
          {
            kind: 'p',
            text:
              'We honor browser-based opt-out preference signals, such as Global Privacy Control, where required by ' +
              'law. Where applicable law requires it, we provide a mechanism to manage non-essential cookies.',
          },
        ],
      },
      {
        num: '9',
        heading: 'Your choices and rights',
        blocks: [
          {
            kind: 'bullets',
            items: [
              'Access and correction — you can view and update much of your account information in the Service.',
              'Deletion — you can request deletion of your account and associated personal information, subject to information we are required or permitted by law to retain (such as certain audit records, and de-identified data that no longer identifies you).',
              'Improvement opt-out — you can withdraw improvement consent at any time in your settings.',
              'Communications — you can opt out of non-essential emails.',
            ],
          },
          {
            kind: 'p',
            text:
              'Residents of certain states have additional rights — see the State-Specific Rights Addendum (below), ' +
              'which is part of this Policy.',
          },
          {
            kind: 'p',
            text:
              `To exercise any of these rights, contact us at ${privacy} or ${support}. We will verify your request ` +
              'as required by law before acting on it.',
          },
        ],
      },
      {
        num: '10',
        heading: 'Data retention',
        blocks: [
          {
            kind: 'p',
            text:
              'We retain your information while your account is active and as needed to provide the Service, then as ' +
              'required for legal, compliance, and audit purposes. You may request deletion as described above, ' +
              'subject to retention we are legally required or permitted to maintain.',
          },
        ],
      },
      {
        num: '11',
        heading: 'Children',
        blocks: [
          {
            kind: 'p',
            text:
              'The Service is for adults 18 and older. Children may not use the Service or create accounts. We do not ' +
              'knowingly allow children to use the Service or knowingly collect information directly from children as ' +
              "users. A parent or guardian may provide a minor's information to manage that minor's bills, as " +
              `described in Section 1. If you believe a child has created an account, contact us at ${privacy} and we ` +
              'will address it.',
          },
        ],
      },
      {
        num: '12',
        heading: 'Changes to this Policy',
        blocks: [
          {
            kind: 'p',
            text:
              'We may update this Policy. If changes are material, we will notify you and update the Effective Date.',
          },
        ],
      },
      {
        num: '13',
        heading: 'Contact',
        blocks: [
          {
            kind: 'p',
            text: `${LEGAL_FIELDS.entity}\n${LEGAL_FIELDS.mailingAddress}\n${privacy}`,
          },
        ],
      },
      // ── Data Improvement Consent (source draft 03) — surfaced here as a section
      //    of the Privacy Policy. settings.tsx presents the opt-in toggle + its
      //    own consent modal; this section is the canonical explainer it should
      //    link to. (settings.tsx is owned by another agent — see the note in the
      //    task report.)
      {
        heading: 'Data Improvement Consent (Optional)',
        blocks: [
          {
            kind: 'p',
            text:
              'This consent is optional. You can use Tyndale fully without agreeing to it, and your choice never ' +
              'changes the service you receive. It covers one thing: whether we may use your information — with ' +
              'everything that identifies you removed — to make Tyndale more accurate and helpful. It is presented ' +
              'separately from account signup and the Terms, is off by default, and is never bundled into Terms ' +
              'acceptance.',
          },
          {
            kind: 'callout',
            text:
              "Help make Tyndale better. With your permission, we'll use your bills, your feedback, and the outcomes " +
              'of your cases — with all your personal information removed — to improve how Tyndale catches errors and ' +
              'helps people. This is optional, it never affects the service you receive, and you can turn it off ' +
              'anytime in Settings.',
          },
          {
            kind: 'p',
            text:
              'What you are agreeing to, if you opt in: You allow us to use your uploaded bills and statements, your ' +
              'feedback (such as thumbs up or down and corrections), your confirmations (such as whether a billed ' +
              'service matched your care), and the outcomes of your cases — only after de-identification, an ' +
              'automated and human-reviewed process that removes information identifying you, such as your name, ' +
              'contact details, member and account numbers, and other identifiers — to evaluate and improve ' +
              "Tyndale's accuracy, including building and testing the Service's analysis and future features.",
          },
          { kind: 'p', text: 'What you are NOT agreeing to:' },
          {
            kind: 'bullets',
            items: [
              'Any use of information that still identifies you for improvement purposes.',
              'Any sale of your information.',
              'Any advertising use of your information.',
              'Any sharing of your identifiable health or financial information with third parties for their own purposes.',
            ],
          },
          {
            kind: 'p',
            text:
              'De-identification comes first. Before any of your information is used for improvement, it passes ' +
              'through a de-identification process designed to remove identifiers. Information that does not pass ' +
              'de-identification is not used for improvement. Opting in gives permission; de-identification is what ' +
              'makes the information safe to use. Both are required.',
          },
          {
            kind: 'p',
            text:
              'Withdrawing your consent. You can withdraw this consent at any time in your Settings. After you ' +
              'withdraw, we stop using your information for improvement going forward. Information that was already ' +
              'fully de-identified may remain in our improvement datasets, because it no longer identifies you.',
          },
          {
            kind: 'p',
            text:
              'Opting in is entirely your choice. Tyndale works exactly the same whether you opt in or not.',
          },
        ],
      },
      // ── State-Specific Rights Addendum (source draft 04) — surfaced here as a
      //    section of the Privacy Policy.
      {
        heading: 'State-Specific Rights Addendum',
        blocks: [
          {
            kind: 'p',
            text:
              'This Addendum is part of the Tyndale Privacy Policy and provides additional rights and disclosures for ' +
              'residents of certain states. If you are a resident of a state listed below, the corresponding section ' +
              'applies to you. If anything here conflicts with the main Privacy Policy, this Addendum controls for ' +
              'residents of that state.',
          },
          {
            kind: 'p',
            text:
              'Across all states: we do not sell your personal information, we do not "share" it for cross-context ' +
              'behavioral advertising, and we do not use your health or financial information for advertising. We ' +
              'will not discriminate against you for exercising any privacy right.',
          },
          {
            kind: 'p',
            text:
              `To exercise any right described here, contact us at ${privacy}. We will verify your identity as ` +
              'required by law before acting on your request, and we will respond within the timeframe your state’s ' +
              'law requires. If we deny a request, you may appeal by replying to our response; where your state ' +
              'provides it, you may also contact your state attorney general.',
          },
          {
            kind: 'p',
            text:
              'California. If you are a California resident, you have the right to: know and access the personal ' +
              'information we collect about you; know whether we disclose it and to whom; correct inaccurate personal ' +
              'information; delete your personal information; and limit the use of sensitive personal information ' +
              '(which includes health information). We collect the categories of information described in the Privacy ' +
              'Policy, use them for the purposes described there, and disclose them only to the service providers and ' +
              'in the situations described there. We do not sell or share your personal information as those terms ' +
              'are defined under California law. You may use an authorized agent to submit requests.',
          },
          {
            kind: 'p',
            text:
              'Virginia, Colorado, Connecticut, Utah, Texas, Oregon, Montana, and other states with comprehensive ' +
              'privacy laws. If you are a resident of a state with a comprehensive consumer privacy law, you have the ' +
              'right to: confirm whether we process your personal data and access it; correct inaccuracies; delete ' +
              'personal data; obtain a portable copy of data you provided; and opt out of targeted advertising, sale ' +
              'of personal data, and certain profiling. We do not engage in targeted advertising, sale of personal ' +
              'data, or such profiling. Health information is treated as sensitive data under these laws. Where your ' +
              'state requires your consent before processing sensitive data, we obtain it; where your state instead ' +
              'requires that we offer a way to opt out of sensitive-data processing, we provide that option. Because ' +
              'providing your health and billing information is essential to how Tyndale helps you, processing that ' +
              'information is necessary to deliver the Service you request.',
          },
          {
            kind: 'p',
            text:
              'Washington (and other consumer-health-data laws). If you are a Washington resident, the My Health My ' +
              'Data Act provides specific rights regarding "consumer health data," including the right to access it, ' +
              'to withdraw consent to its collection and sharing, and to have it deleted. We collect consumer health ' +
              'data only to provide the Service to you, with your consent; we do not sell consumer health data; and ' +
              'we do not share it except with service providers who help us operate the Service or as you direct. To ' +
              `exercise these rights, contact us at ${privacy}. Residents of other states with consumer-health-data ` +
              'laws (such as Nevada) have comparable rights, which we honor where applicable.',
          },
          {
            kind: 'p',
            text:
              'State medical-debt and billing protections. Some states provide specific protections regarding medical ' +
              'bills and medical debt, including limits on certain collection practices and on the reporting of ' +
              'medical debt. Tyndale helps you understand and exercise rights you may have, but Tyndale does not ' +
              'collect debt and is not a debt collector or a credit-reporting agency. Nothing in the Service is a ' +
              "substitute for legal advice about your rights under your state's law.",
          },
          {
            kind: 'p',
            text:
              'Auto-renewal and subscription rights. Some states have specific requirements regarding automatically ' +
              'renewing subscriptions, including clear disclosure of renewal terms and an easy way to cancel. You can ' +
              'cancel your paid plan at any time in your account settings, effective at the end of your current ' +
              'billing period, as described in the Terms of Service.',
          },
          {
            kind: 'p',
            text:
              'This Addendum will be updated as additional state laws take effect. Check the Effective Date for the ' +
              'latest version.',
          },
        ],
      },
    ],
  };
}
