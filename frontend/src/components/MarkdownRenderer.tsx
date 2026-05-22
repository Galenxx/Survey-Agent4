import ReactMarkdown from 'react-markdown'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism'

function buildTableHtml(headerCells: string[], bodyRows: string[][]): string {
  const colCount = headerCells.length
  const thCells = headerCells.map((c, i) => {
    const align = i === colCount - 1 ? 'text-right' : 'text-left'
    return `<th class="px-4 py-2.5 text-xs font-semibold uppercase tracking-wider ${align}" style="background:#f1f5f9;border-bottom:2px solid #cbd5e1;color:#475569;white-space:nowrap;">${c.trim()}</th>`
  }).join('')
  const tbody = bodyRows.map(row => {
    const tds = row.map((c, i) => {
      const align = i === colCount - 1 ? 'text-right' : ''
      return `<td class="px-4 py-3 text-sm ${align}" style="border-bottom:1px solid #e2e8f0;vertical-align:top;color:#334155;">${c.trim()}</td>`
    }).join('')
    return `<tr>${tds}</tr>`
  }).join('')
  return `<table style="width:100%;border-collapse:collapse;border:1px solid #e2e8f0;border-radius:8px;"><thead><tr>${thCells}</tr></thead><tbody>${tbody}</tbody></table>`
}

function extractTables(text: string): (string | { table: { header: string[], body: string[][] } })[] {
  const TABLE_RE = /(\|[^\n]*\|)\n(\|[^\n]*\|)\n((?:\|[^\n]*\|\n?)+)/g
  const SEPARATOR_RE = /\|[\s\-:|]+\|/
  const parts: (string | { table: { header: string[], body: string[][] } })[] = []
  let lastIndex = 0
  let match
  while ((match = TABLE_RE.exec(text)) !== null) {
    const separatorLine = match[2]
    if (!SEPARATOR_RE.test(separatorLine)) continue
    const before = text.slice(lastIndex, match.index)
    if (before) parts.push(before)
    const headerCells = match[1].split('|').filter((_, i, a) => i > 0 && i < a.length - 1)
    const bodyRows = match[3].trim().split('\n').map(line =>
      line.split('|').filter((_, i, a) => i > 0 && i < a.length - 1)
    )
    parts.push({ table: { header: headerCells, body: bodyRows } })
    lastIndex = match.index + match[0].length
  }
  const rest = text.slice(lastIndex)
  if (rest) parts.push(rest)
  return parts
}

interface MarkdownRendererProps {
  content: string
}

export default function MarkdownRenderer({ content }: MarkdownRendererProps) {
  const parts = extractTables(content)
  return (
    <div className="prose prose-slate max-w-none">
      {parts.map((part, idx) =>
        typeof part === 'string' ? (
          <ReactMarkdown key={idx} components={{
            h1: ({ children }) => <h1 className="text-2xl font-bold text-slate-900 mt-8 mb-4 pb-2 border-b border-slate-200">{children}</h1>,
            h2: ({ children }) => <h2 className="text-xl font-semibold text-slate-900 mt-6 mb-3">{children}</h2>,
            h3: ({ children }) => <h3 className="text-lg font-semibold text-slate-800 mt-4 mb-2">{children}</h3>,
            h4: ({ children }) => <h4 className="text-base font-semibold text-slate-800 mt-3 mb-2">{children}</h4>,
            blockquote: ({ children }) => <blockquote className="border-l-4 border-primary-500 bg-slate-50 pl-4 py-2 my-4 rounded-r">{children}</blockquote>,
            code: ({ className, children, ...props }) => {
              const inline = !className
              const match = /language-(\w+)/.exec(className || '')
              const language = match ? match[1] : ''
              const codeStr = String(children).replace(/\n$/, '')
              if (inline) return <code className="bg-slate-100 text-slate-800 px-1.5 py-0.5 rounded text-sm font-mono" {...props}>{children}</code>
              return <div className="my-4 rounded-lg overflow-hidden"><SyntaxHighlighter style={oneDark} language={language || 'text'} PreTag="div" customStyle={{ margin: 0, borderRadius: 0 }}>{codeStr}</SyntaxHighlighter></div>
            },
            a: ({ href, children }) => <a href={href} target="_blank" rel="noopener noreferrer" className="text-primary-600 hover:text-primary-700 underline">{children}</a>,
            ul: ({ children }) => <ul className="list-disc pl-6 my-2 space-y-1">{children}</ul>,
            ol: ({ children }) => <ol className="list-decimal pl-6 my-2 space-y-1">{children}</ol>,
            li: ({ children }) => <li className="text-slate-700">{children}</li>,
            p: ({ children }) => <p className="my-3 text-slate-700 leading-relaxed">{children}</p>,
            hr: () => <hr className="my-6 border-slate-200" />,
            strong: ({ children }) => <strong className="font-semibold text-slate-900">{children}</strong>,
          }}>{part}</ReactMarkdown>
        ) : (
          <div key={idx} className="overflow-x-auto my-4 rounded-lg border border-slate-200 shadow-sm"
            dangerouslySetInnerHTML={{ __html: buildTableHtml(part.table.header, part.table.body) }} />
        )
      )}
    </div>
  )
}
