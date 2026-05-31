'use client';

export function ChatTranscript({
  messages,
}: {
  messages: Array<{ role: string; content: string; timestamp?: string }>;
}) {
  if (!messages.length) {
    return (
      <p className="text-sm text-white/40">
        No chat history for this case yet. (The user↔Tyndale conversation store lands in a
        later phase; case data here comes from uploads, findings, and the audit stream.)
      </p>
    );
  }
  return (
    <div className="space-y-2">
      {messages.map((m, i) => (
        <div
          key={i}
          className={`rounded-xl px-3 py-2 text-sm ${
            m.role === 'user' ? 'bg-white/5 text-white/80' : 'bg-teal-deep text-white'
          }`}
        >
          <p className="mb-0.5 text-[11px] uppercase tracking-wide text-white/40">{m.role}</p>
          <p className="leading-5">{m.content}</p>
        </div>
      ))}
    </div>
  );
}
