import { useState, useEffect } from 'react'
import { useParams, Link, useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import MarkdownRenderer from '../components/MarkdownRenderer'
import {
  ArrowLeft,
  Download,
  Loader2,
  XCircle,
  RefreshCw,
  ExternalLink,
} from 'lucide-react'

interface PaperMeta {
  id: string
  title: string
  authors: string[]
  year?: number
  abstract?: string
  citation_count: number
  url: string
  pdf_url?: string
}

export default function ReportPage() {
  const { taskId } = useParams<{ taskId: string }>()
  const navigate = useNavigate()
  const decodedTaskId = decodeURIComponent(taskId || '')

  const [report, setReport] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [papers, setPapers] = useState<PaperMeta[]>([])
  const [papersLoading, setPapersLoading] = useState(false)

  useEffect(() => {
    async function load() {
      setLoading(true)
      setError('')
      try {
        const data = await api.getReport(decodedTaskId)
        setReport(data.report_content)
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load report')
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [decodedTaskId])

  async function loadPapers() {
    setPapersLoading(true)
    try {
      const data = await api.getPapers(decodedTaskId)
      // Try to extract papers from search_results
      const searchFile = data.data_files?.find(
        (f: { name: string }) => f.name === 'search_results'
      )
      if (searchFile?.data?.papers) {
        setPapers(searchFile.data.papers.slice(0, 20))
      } else {
        setPapers([])
      }
    } catch {
      setPapers([])
    } finally {
      setPapersLoading(false)
    }
  }

  function handleDownload() {
    api.downloadReport(decodedTaskId)
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-24">
        <Loader2 className="w-8 h-8 animate-spin text-primary-500" />
        <span className="ml-3 text-slate-600">Loading report...</span>
      </div>
    )
  }

  if (error) {
    return (
      <div className="max-w-4xl mx-auto px-4 py-12 text-center">
        <XCircle className="w-12 h-12 text-red-500 mx-auto mb-4" />
        <h2 className="text-xl font-semibold text-slate-900 mb-2">Report Not Available</h2>
        <p className="text-slate-600 mb-6">{error}</p>
        <div className="flex justify-center gap-3">
          <Link to="/" className="btn-secondary flex items-center gap-2">
            <ArrowLeft className="w-4 h-4" />
            Home
          </Link>
          <button onClick={() => navigate(`/tasks/${encodeURIComponent(decodedTaskId)}`)} className="btn-primary flex items-center gap-2">
            <RefreshCw className="w-4 h-4" />
            Check Task
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">

      {/* Header */}
      <div className="flex items-start gap-4 mb-6">
        <button onClick={() => navigate('/')} className="mt-1 btn-secondary p-2" title="Back">
          <ArrowLeft className="w-4 h-4" />
        </button>
        <div className="flex-1">
          <h1 className="text-2xl font-bold text-slate-900">
            Research Gap Analysis Report
          </h1>
          <p className="text-sm text-slate-500 mt-1 font-mono truncate">
            {decodedTaskId}
          </p>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          <Link
            to={`/tasks/${encodeURIComponent(decodedTaskId)}`}
            className="btn-secondary flex items-center gap-2"
          >
            Task Details
          </Link>
          <button onClick={handleDownload} className="btn-primary flex items-center gap-2">
            <Download className="w-4 h-4" />
            Download
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">

        {/* Papers sidebar */}
        <aside className="lg:col-span-1 space-y-4">
          <div className="card">
            <div className="flex items-center justify-between mb-3">
              <h2 className="font-semibold text-slate-900 text-sm">Papers Analyzed</h2>
              {!papersLoading && papers.length === 0 && (
                <button onClick={loadPapers} className="text-xs text-primary-600 hover:text-primary-700">
                  Load
                </button>
              )}
              {papersLoading && <Loader2 className="w-3 h-3 animate-spin text-slate-400" />}
            </div>

            {papersLoading && papers.length === 0 ? (
              <p className="text-xs text-slate-400">Loading...</p>
            ) : papers.length === 0 ? (
              <p className="text-xs text-slate-400">
                No papers loaded. Click "Load" to fetch from search results.
              </p>
            ) : (
              <ul className="space-y-3 max-h-[70vh] overflow-y-auto">
                {papers.map((paper, i) => (
                  <li key={paper.id || i} className="border-b border-slate-100 pb-3 last:border-0">
                    <p className="text-xs font-medium text-slate-800 line-clamp-2 leading-snug">
                      {paper.title}
                    </p>
                    <div className="flex items-center gap-2 mt-1">
                      {paper.year && (
                        <span className="text-xs text-slate-400">{paper.year}</span>
                      )}
                      {paper.citation_count > 0 && (
                        <span className="text-xs text-slate-400">
                          {paper.citation_count} citations
                        </span>
                      )}
                    </div>
                    {paper.url && (
                      <a
                        href={paper.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-xs text-primary-600 hover:text-primary-700 flex items-center gap-0.5 mt-1"
                      >
                        <ExternalLink className="w-3 h-3" />
                        View
                      </a>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </div>
        </aside>

        {/* Report content */}
        <article className="lg:col-span-3">
          <div className="card">
            <MarkdownRenderer content={report} />
          </div>
        </article>
      </div>
    </div>
  )
}
