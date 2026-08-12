'use client'

import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from 'react'

export type Phase =
  | 'processing'
  | 'verifying'
  | 'revealed'
  | 'unlocked'
  | 'planned'

export type VerifyAnswer = 'yes' | 'no' | 'notsure'
export type CallOutcome = 'fixing' | 'pushback' | 'voicemail' | null

type CaseState = {
  phase: Phase
  verifyAnswers: Record<string, VerifyAnswer>
  unlocked: boolean
  callOutcome: CallOutcome
  resolved: boolean
  hasEob: boolean
  email: string
}

type CaseContextValue = CaseState & {
  setPhase: (p: Phase) => void
  answerVerify: (id: string, a: VerifyAnswer) => void
  setUnlocked: (v: boolean) => void
  setCallOutcome: (o: CallOutcome) => void
  setResolved: (v: boolean) => void
  setHasEob: (v: boolean) => void
  setEmail: (v: string) => void
  reset: () => void
}

const DEFAULT_STATE: CaseState = {
  phase: 'processing',
  verifyAnswers: {},
  unlocked: false,
  callOutcome: null,
  resolved: false,
  hasEob: true,
  email: '',
}

const STORAGE_KEY = 'tyndale-case-v1'

const CaseContext = createContext<CaseContextValue | null>(null)

export function CaseProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<CaseState>(DEFAULT_STATE)
  const [hydrated, setHydrated] = useState(false)

  useEffect(() => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY)
      if (raw) setState({ ...DEFAULT_STATE, ...JSON.parse(raw) })
    } catch {
      // ignore
    }
    setHydrated(true)
  }, [])

  useEffect(() => {
    if (!hydrated) return
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(state))
    } catch {
      // ignore
    }
  }, [state, hydrated])

  const value: CaseContextValue = {
    ...state,
    setPhase: (phase) => setState((s) => ({ ...s, phase })),
    answerVerify: (id, a) =>
      setState((s) => ({
        ...s,
        verifyAnswers: { ...s.verifyAnswers, [id]: a },
      })),
    setUnlocked: (unlocked) => setState((s) => ({ ...s, unlocked })),
    setCallOutcome: (callOutcome) => setState((s) => ({ ...s, callOutcome })),
    setResolved: (resolved) => setState((s) => ({ ...s, resolved })),
    setHasEob: (hasEob) => setState((s) => ({ ...s, hasEob })),
    setEmail: (email) => setState((s) => ({ ...s, email })),
    reset: () => setState(DEFAULT_STATE),
  }

  return <CaseContext.Provider value={value}>{children}</CaseContext.Provider>
}

export function useCase() {
  const ctx = useContext(CaseContext)
  if (!ctx) throw new Error('useCase must be used within CaseProvider')
  return ctx
}
