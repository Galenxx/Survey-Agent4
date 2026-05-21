import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, TaskStatus } from '../api/client'
import TaskCard from '../components/TaskCard'
import { Search, Loader2, BookOpen, TrendingUp, Target } from 'lucide-react'

export default function HomePage() {
  const navigate = useNavigate()

  const [query, setQuery] = useState('')
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
      const res = await api.createTask({ query: query.trim() })
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
              placeholder="e.g., 分析LLM在职位推荐领域的方法论空白，重点关注2022年以来的研究"
              rows={3}
              className="input-field resize-none"
              required
            />
            <p className="mt-1 text-xs text-slate-500">
              支持中文和英文，Router Agent 会自动解析研究主题、搜索关键词，并推断 gap 类型、年份范围和论文数量
            </p>
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
