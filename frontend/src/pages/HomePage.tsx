import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, TaskStatus } from '../api/client'
import TaskCard from '../components/TaskCard'
import { Search, Loader2, BookOpen, TrendingUp, Target } from 'lucide-react'

const GAP_DIRECTIONS = [
  { value: '', label: 'All Gap Types' },
  { value: 'Methodological Gap', label: 'Methodological Gap (方法论空白)' },
  { value: 'Knowledge Gap', label: 'Knowledge Gap (知识空白)' },
  { value: 'Evidence Gap', label: 'Evidence Gap (证据空白)' },
  { value: 'Theoretical Gap', label: 'Theoretical Gap (理论空白)' },
  { value: 'Population Gap', label: 'Population Gap (人群空白)' },
  { value: 'Contextual/Time Gap', label: 'Contextual/Time Gap (情境/时间空白)' },
]

export default function HomePage() {
  const navigate = useNavigate()

  const [query, setQuery] = useState('')
  const [gapDirection, setGapDirection] = useState('')
  const [timeRange, setTimeRange] = useState('2022-')
  const [maxResults, setMaxResults] = useState(50)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState('')
  const [recentTasks, setRecentTasks] = useState<TaskStatus[]>([])
  const [loadingTasks, setLoadingTasks] = useState(true)

  useEffect(() => {
    api.listTasks(0, 10)
      .then(data => setRecentTasks(data.tasks))
      .catch(() => setRecentTasks([]))
      .finally(() => setLoadingTasks(false))
  }, [])

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!query.trim()) return

    setIsSubmitting(true)
    setSubmitError('')

    try {
      const res = await api.createTask({
        query: query.trim(),
        gap_direction: gapDirection,
        time_range: timeRange,
        max_results: maxResults,
      })
      navigate(`/tasks/${encodeURIComponent(res.task_id)}`)
    } catch (err) {
      setSubmitError(err instanceof Error ? err.message : 'Failed to create task')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-10 space-y-12">

      {/* Hero */}
      <div className="text-center space-y-4">
        <h1 className="text-4xl font-bold text-slate-900">
          Research Gap Analysis
        </h1>
        <p className="text-lg text-slate-600 max-w-2xl mx-auto">
          Enter a research topic and let AI agents automatically search papers,
          analyze methodological gaps, and generate comprehensive gap reports.
        </p>
      </div>

      {/* Feature pills */}
      <div className="flex flex-wrap justify-center gap-6">
        {[
          { icon: Search, text: 'Semantic Scholar Search' },
          { icon: BookOpen, text: 'PDF Analysis' },
          { icon: Target, text: 'Gap Identification' },
          { icon: TrendingUp, text: 'Research Synthesis' },
        ].map(({ icon: Icon, text }) => (
          <div key={text} className="flex items-center gap-2 text-sm text-slate-500">
            <Icon className="w-4 h-4 text-primary-500" />
            {text}
          </div>
        ))}
      </div>

      {/* Task creation form */}
      <div className="card max-w-2xl mx-auto">
        <h2 className="text-lg font-semibold text-slate-900 mb-6">
          Start a New Analysis
        </h2>

        <form onSubmit={handleSubmit} className="space-y-5">
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1.5">
              Research Query <span className="text-red-500">*</span>
            </label>
            <textarea
              value={query}
              onChange={e => setQuery(e.target.value)}
              placeholder="e.g., LLM在职位推荐领域的方法论空白"
              rows={3}
              className="input-field resize-none"
              required
            />
            <p className="mt-1 text-xs text-slate-500">
              Describe your research topic in Chinese or English
            </p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1.5">
                Gap Direction
              </label>
              <select
                value={gapDirection}
                onChange={e => setGapDirection(e.target.value)}
                className="input-field"
              >
                {GAP_DIRECTIONS.map(opt => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1.5">
                Year Range
              </label>
              <input
                type="text"
                value={timeRange}
                onChange={e => setTimeRange(e.target.value)}
                placeholder="e.g., 2020-2026"
                className="input-field"
              />
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1.5">
              Max Papers to Search
            </label>
            <input
              type="number"
              value={maxResults}
              onChange={e => setMaxResults(parseInt(e.target.value) || 50)}
              min={1}
              max={200}
              className="input-field max-w-40"
            />
          </div>

          {submitError && (
            <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
              {submitError}
            </div>
          )}

          <button
            type="submit"
            disabled={isSubmitting || !query.trim()}
            className="btn-primary w-full flex items-center justify-center gap-2"
          >
            {isSubmitting ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                Creating Task...
              </>
            ) : (
              <>
                <Search className="w-4 h-4" />
                Start Analysis
              </>
            )}
          </button>
        </form>
      </div>

      {/* Recent tasks */}
      <div>
        <h2 className="text-xl font-semibold text-slate-900 mb-4">Recent Tasks</h2>

        {loadingTasks ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="w-6 h-6 animate-spin text-slate-400" />
          </div>
        ) : recentTasks.length === 0 ? (
          <div className="text-center py-12 text-slate-500">
            No tasks yet. Create one above to get started.
          </div>
        ) : (
          <div className="space-y-3">
            {recentTasks.map(task => (
              <TaskCard key={task.task_id} task={task} />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
