import { Link } from 'react-router-dom'
import { TaskStatus } from '../api/client'
import { Clock, CheckCircle, XCircle, Loader2 } from 'lucide-react'

interface TaskCardProps {
  task: TaskStatus
}

function formatDate(iso: string | undefined): string {
  if (!iso) return '—'
  const d = new Date(iso)
  return d.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function StatusBadge({ status }: { status: string }) {
  if (status === 'running') {
    return (
      <span className="status-badge status-running flex items-center gap-1">
        <Loader2 className="w-3 h-3 animate-spin" />
        Running
      </span>
    )
  }
  if (status === 'completed') {
    return (
      <span className="status-badge status-completed flex items-center gap-1">
        <CheckCircle className="w-3 h-3" />
        Completed
      </span>
    )
  }
  return (
    <span className="status-badge status-failed flex items-center gap-1">
      <XCircle className="w-3 h-3" />
      Failed
    </span>
  )
}

export default function TaskCard({ task }: TaskCardProps) {
  const shortId = task.task_id.length > 40 ? task.task_id.slice(0, 40) + '...' : task.task_id

  return (
    <div className="card hover:shadow-md transition-shadow">
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          <h3 className="font-medium text-slate-900 truncate" title={task.task_name}>
            {task.task_name}
          </h3>
          <p className="text-xs text-slate-400 mt-1 font-mono truncate" title={task.task_id}>
            {shortId}
          </p>
          <div className="flex items-center gap-1 mt-2 text-xs text-slate-500">
            <Clock className="w-3 h-3" />
            {formatDate(task.start_time)}
          </div>
          {task.summary && (
            <p className="text-sm text-slate-600 mt-2 line-clamp-2">
              {task.summary}
            </p>
          )}
          {task.error && (
            <p className="text-sm text-red-600 mt-2 line-clamp-2">
              {task.error}
            </p>
          )}
        </div>
        <div className="flex flex-col items-end gap-2">
          <StatusBadge status={task.status} />
          {task.status === 'completed' && (
            <Link
              to={`/reports/${encodeURIComponent(task.task_id)}`}
              className="text-xs text-primary-600 hover:text-primary-700 font-medium"
            >
              View Report
            </Link>
          )}
          {task.status === 'running' && (
            <Link
              to={`/tasks/${encodeURIComponent(task.task_id)}`}
              className="text-xs text-primary-600 hover:text-primary-700 font-medium"
            >
              Track Progress
            </Link>
          )}
        </div>
      </div>
    </div>
  )
}
