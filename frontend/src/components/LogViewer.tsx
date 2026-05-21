import { useEffect, useRef } from 'react'

interface LogViewerProps {
  content?: string
  fullLog?: string   // complete log from file (takes priority over content)
  className?: string
  autoScroll?: boolean
}

function buildLineHtml(line: string): string {
  const escaped = line
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')

  // Color-code by prefix
  if (/\[THINKING\]|\[INPUT\]|\[OUTPUT\]/.test(escaped)) {
    return `<span style="color:#a78bfa;font-style:italic">${escaped}</span>`
  }
  if (/\[\w+Agent\]/.test(escaped) || /\[AGENT\]/.test(escaped)) {
    return `<span style="color:#7c3aed;font-weight:500">${escaped}</span>`
  }
  if (/\[TOOL\]/.test(escaped)) {
    return `<span style="color:#0891b2">${escaped}</span>`
  }
  if (/\[TASK\]/.test(escaped)) {
    return `<span style="color:#d97706">${escaped}</span>`
  }
  if (/\[CREW\]/.test(escaped)) {
    return `<span style="color:#059669;font-weight:600">${escaped}</span>`
  }
  if (/\[ERROR\]|\[SYSTEM\].*fail|\[SYSTEM\].*error/i.test(escaped)) {
    return `<span style="color:#dc2626;font-weight:500">${escaped}</span>`
  }
  if (/\[SYSTEM\]/.test(escaped)) {
    return `<span style="color:#6b7280;font-style:italic">${escaped}</span>`
  }
  return `<span>${escaped}</span>`
}

export default function LogViewer({
  content = '',
  fullLog,
  className = '',
  autoScroll = true,
}: LogViewerProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const bottomRef = useRef<HTMLDivElement>(null)

  // Prefer fullLog (complete file content), fall back to streaming content
  const displayContent = fullLog || content

  useEffect(() => {
    if (autoScroll && bottomRef.current) {
      bottomRef.current.scrollIntoView({ behavior: 'smooth' })
    }
  }, [displayContent, autoScroll])

  if (!displayContent) {
    return (
      <div className={`log-viewer ${className} text-slate-500 italic`}>
        No log output yet.
      </div>
    )
  }

  const lines = displayContent.split('\n')

  return (
    <div
      ref={containerRef}
      className={`log-viewer ${className}`}
      style={{
        fontFamily: '"Fira Code", "JetBrains Mono", "Cascadia Code", monospace',
        fontSize: '12px',
        lineHeight: '1.6',
        background: '#0f172a',
        color: '#e2e8f0',
        maxHeight: '400px',
        overflowY: 'auto',
        padding: '12px',
      }}
    >
      {lines.map((line, i) => (
        <div
          key={i}
          style={{ whiteSpace: 'pre-wrap', minHeight: '1.2em' }}
          dangerouslySetInnerHTML={{ __html: buildLineHtml(line) || '&nbsp;' }}
        />
      ))}
      <div ref={bottomRef} />
    </div>
  )
}
