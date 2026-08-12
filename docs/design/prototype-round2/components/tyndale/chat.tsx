import { cn } from '@/lib/utils'
import { TyndaleMark } from './brand'

export function AgentAvatar() {
  return <TyndaleMark className="h-9 w-9 shrink-0 rounded-full" />
}

/* A spoken line from Tyndale. */
export function AgentSays({
  children,
  className,
}: {
  children: React.ReactNode
  className?: string
}) {
  return (
    <div className={cn('flex items-end gap-2.5', className)}>
      <AgentAvatar />
      <div className="max-w-[85%] rounded-3xl rounded-bl-md bg-card px-4 py-3 text-[16px] leading-relaxed text-card-foreground shadow-soft ring-1 ring-border/70">
        {children}
      </div>
    </div>
  )
}

/* The user's reply. */
export function UserSays({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex justify-end">
      <div className="max-w-[85%] rounded-3xl rounded-br-md bg-primary px-4 py-3 text-[16px] leading-relaxed text-primary-foreground shadow-soft">
        {children}
      </div>
    </div>
  )
}

/* Full-width attachment beneath the avatar column — cards, moments, controls. */
export function AgentAttachment({
  children,
  className,
  inset = true,
}: {
  children: React.ReactNode
  className?: string
  inset?: boolean
}) {
  return (
    <div className={cn(inset && 'pl-[46px]', className)}>{children}</div>
  )
}
