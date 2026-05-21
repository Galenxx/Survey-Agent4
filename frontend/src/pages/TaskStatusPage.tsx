import { useState, useEffect, useCallback, useRef } from 'react'
import { useParams, Link, useNavigate } from 'react-router-dom'
import { api, TaskStatus, SSEEvent } from '../api/client'
import LogViewer from '../components/LogViewer'
import {
  Loader2,
  CheckCircle,
  XCircle,
  RefreshCw,
  ArrowLeft,
  FileText,
  ChevronDown,
  ChevronRight,
  Search,
  Filter,
  Brain,
  BarChart3,
  BookOpen,
} from 'lucide-react'

// The 6 agents shown in the pipeline, in execution order
const PIPELINE_AGENTS = [
  { name: 'router',      label: 'Router',      icon: Search,     description: 'Query analysis and search planning' },
  { name: 'searcher',    label: 'Searcher',    icon: Search,     description: 'Paper retrieval from Semantic Scholar' },
  { name: 'filter',      label: 'Filter',       icon: Filter,     description: 'Relevance classification' },
  { name: 'analyzer',    label: 'Analyzer',     icon: Brain,      description: 'Gap identification and analysis' },
  { name: 'synthesizer', label: 'Synthesizer', icon: BarChart3,  description: 'Report generation' },
]

// Manager is shown separately (runs in parallel / delegates)
const MANAGER_AGENT = { name: 'manager', label: 'Manager', icon: BookOpen, description: 'Orchestration and coordination' }

const ALL_AGENTS = [...PIPELINE_AGENTS, MANAGER_AGENT]

// Map CrewAI agent roles to our agent names
function matchAgentRole(role: string): string | null {
  const r = role.toLowerCase()
  if (r.includes('router')) return 'router'
  if (r.includes('searcher')) return 'searcher'
  if (r.includes('filter') || r.includes('classifier')) return 'filter'
  if (r.includes('analyzer') || r.includes('gap')) return 'analyzer'
  if (r.includes('synthesizer') || r.includes('report')) return 'synthesizer'
  if (r.includes('manager') || r.includes('orchestrat')) return 'manager'
  return null
}

// Build a log entry from an SSE event
function buildLogLine(event: SSEEvent): string {
  const time = new Date().toLocaleTimeString('zh-CN')
  switch (event.type) {
    case 'crew_started':
      return `[${time}] [CREW] Analysis started - Topic: ${event.inputs?.user_input || 'N/A'}`
    case 'crew_completed':
      return `[${time}] [CREW] Analysis completed successfully`
    case 'crew_failed':
      return `[${time}] [CREW] Analysis failed: ${event.error}`
    case 'task_started':
      return `[${time}] [TASK] Starting: ${event.task_name}`
    case 'task_completed':
      return `[${time}] [TASK] Completed: ${event.task_name}`
    case 'task_failed':
      return `[${time}] [TASK] Failed: ${event.task_name} - ${event.error}`
    case 'agent_started':
      return `[${time}] [AGENT] ${event.agent_role} started working on: ${event.task_name}`
    case 'agent_completed':
      return `[${time}] [AGENT] ${event.agent_role} completed`
    case 'agent_error':
      return `[${time}] [AGENT] ${event.agent_role} error: ${event.error}`
    case 'tool_started': {
      const args = Object.entries(event.tool_args).map(([k, v]) => `${k}=${v}`).join(', ')
      return `[${time}] [TOOL] ${event.tool_name} started ${args ? `(${args})` : ''}`
    }
    case 'tool_finished': {
      const truncated = event.output.length > 500 ? event.output.slice(0, 500) + '\n... (truncated)' : event.output
      return `[${time}] [TOOL] ${event.tool_name} finished ${event.from_cache ? '(cached) ' : ''}\n${truncated}`
    }
    case 'tool_error':
      return `[${time}] [TOOL] ${event.tool_name} error: ${event.error}`
    default:
      return `[${time}] ${JSON.stringify(event)}`
  }
}

// Build additional detail log entries from an SSE event (for thinking/input/output)
function buildDetailLogLines(event: SSEEvent): string[] {
  const time = new Date().toLocaleTimeString('zh-CN')
  const lines: string[] = []

  // Agent thinking/prompt (show on agent_started with extended info)
  if (event.type === 'agent_started' && (event as any).prompt) {
    const prompt = (event as any).prompt as string
    if (prompt.length > 0) {
      lines.push(`[${time}] [THINKING] Agent prompt:\n${prompt.slice(0, 2000)}${prompt.length > 2000 ? '\n... (truncated)' : ''}`)
    }
  }

  // Agent output (show on agent_completed with extended info)
  if (event.type === 'agent_completed' && (event as any).output) {
    const output = (event as any).output as string
    if (output.length > 0) {
      lines.push(`[${time}] [OUTPUT] Agent output:\n${output.slice(0, 3000)}${output.length > 3000 ? '\n... (truncated)' : ''}`)
    }
  }

  // Tool input (show on tool_started with extended info)
  if (event.type === 'tool_started' && (event as any).input) {
    const input = (event as any).input as string
    if (input.length > 0) {
      lines.push(`[${time}] [INPUT] Tool input:\n${input.slice(0, 2000)}${input.length > 2000 ? '\n... (truncated)' : ''}`)
    }
  }

  return lines
}

type AgentStatus = 'idle' | 'running' | 'done' | 'error'

interface AgentState {
  status: AgentStatus
  logs: string[]
  fullLog?: string  // complete log content from file
}

export default function TaskStatusPage() {
  const { taskId } = useParams<{ taskId: string }>()
  const navigate = useNavigate()
  const decodedTaskId = decodeURIComponent(taskId || '')

  const [task, setTask] = useState<TaskStatus | null>(null)
  const [agentStates, setAgentStates] = useState<Record<string, AgentState>>(
    Object.fromEntries(ALL_AGENTS.map(a => [a.name, { status: 'idle', logs: [], fullLog: undefined as string | undefined }]))
  )
  const [expandedAgents, setExpandedAgents] = useState<Record<string, boolean>>(
    Object.fromEntries(ALL_AGENTS.map(a => [a.name, false]))
  )
  const [error, setError] = useState('')
  const [sseConnected, setSseConnected] = useState(false)

  // Track which pipeline agent is currently active
  const activePipelineAgent = useRef<string | null>(null)

  const fetchStatus = useCallback(async () => {
    if (!decodedTaskId) return
    try {
      const data = await api.getTaskStatus(decodedTaskId)
      setTask(data)
      setError('')

      // Initialize agent states from API response (for completed tasks loaded from disk)
      if (data.agent_logs && data.agent_logs.length > 0) {
        setAgentStates(prev => {
          const next = { ...prev }
          for (const entry of data.agent_logs!) {
            const agentKey = entry.agent
            if (agentKey in next) {
              next[agentKey] = {
                status: (entry.status === 'done' ? 'done' : 'error') as AgentStatus,
                logs: entry.logs,
              }
            }
          }
          return next
        })
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch status')
    }
  }, [decodedTaskId])

  // Handle incoming SSE events
  const handleSSEEvent = useCallback((event: SSEEvent) => {
    const logLine = buildLogLine(event)
    const detailLines = buildDetailLogLines(event)
    const now = new Date().toLocaleTimeString('zh-CN')

    if (event.type === 'connected') {
      setSseConnected(true)
      return
    }

    // Determine agent name: use agent_key if available, otherwise fuzzy-match agent_role
    let agentName: string | null = null
    if ('agent_key' in event && event.agent_key) {
      agentName = event.agent_key
    } else if ('agent_role' in event && event.agent_role) {
      agentName = matchAgentRole(event.agent_role)
    } else if ('task_name' in event && event.task_name) {
      agentName = matchAgentRole(event.task_name)
    }

    setAgentStates(prev => {
      const next = { ...prev }
      const allLogs = [logLine, ...detailLines]

      switch (event.type) {
        case 'crew_started':
          next.manager = {
            ...next.manager,
            status: 'running',
            logs: [...next.manager.logs, `[${now}] [SYSTEM] Analysis pipeline started`],
          }
          activePipelineAgent.current = 'router'
          next.router = { ...next.router, status: 'running', logs: [...next.router.logs, `[${now}] [SYSTEM] Router is ready`] }
          break

        case 'crew_completed':
          next.manager = {
            ...next.manager,
            status: 'done',
            logs: [...next.manager.logs, `[${now}] [SYSTEM] Analysis completed successfully`],
          }
          PIPELINE_AGENTS.forEach(a => {
            if (next[a.name].status === 'idle' || next[a.name].status === 'running') {
              next[a.name] = { ...next[a.name], status: 'done' }
            }
          })
          activePipelineAgent.current = null
          break

        case 'crew_failed':
          next.manager = {
            ...next.manager,
            status: 'error',
            logs: [...next.manager.logs, `[${now}] [ERROR] ${('error' in event && event.error) || 'Unknown error'}`],
          }
          PIPELINE_AGENTS.forEach(a => {
            if (next[a.name].status === 'running') {
              next[a.name] = { ...next[a.name], status: 'error' }
            }
          })
          activePipelineAgent.current = null
          break

        case 'task_started':
          if (agentName && agentName !== 'manager') {
            next[agentName] = { ...next[agentName], status: 'running', logs: [...next[agentName].logs, ...allLogs] }
          }
          break

        case 'task_completed': {
          if (activePipelineAgent.current) {
            const current = activePipelineAgent.current
            next[current] = { ...next[current], status: 'done', logs: [...next[current].logs, ...allLogs] }
          }
          if (agentName && agentName !== 'manager') {
            activePipelineAgent.current = agentName
          }
          break
        }

        case 'task_failed':
          if (activePipelineAgent.current) {
            next[activePipelineAgent.current] = {
              ...next[activePipelineAgent.current],
              status: 'error',
              logs: [...next[activePipelineAgent.current].logs, ...allLogs],
            }
          }
          break

        case 'agent_started':
          if (agentName === 'manager') {
            next.manager = { ...next.manager, status: 'running', logs: [...next.manager.logs, ...allLogs] }
          } else if (agentName) {
            next[agentName] = { ...next[agentName], status: 'running', logs: [...next[agentName].logs, ...allLogs] }
            activePipelineAgent.current = agentName
          }
          break

        case 'agent_completed':
          if (agentName === 'manager') {
            next.manager = { ...next.manager, status: 'done', logs: [...next.manager.logs, logLine] }
          } else if (agentName) {
            next[agentName] = { ...next[agentName], status: 'done', logs: [...next[agentName].logs, ...allLogs] }
            activePipelineAgent.current = null
          }
          break

        case 'agent_error':
          if (agentName === 'manager') {
            next.manager = { ...next.manager, status: 'error', logs: [...next.manager.logs, ...allLogs] }
          } else if (agentName) {
            next[agentName] = { ...next[agentName], status: 'error', logs: [...next[agentName].logs, ...allLogs] }
          }
          break

        case 'agent_log': {
          const agentKey = (event as any).agent_key as string
          const logContent = (event as any).log_content as string
          if (agentKey && agentKey in next && logContent) {
            next[agentKey] = { ...next[agentKey], fullLog: logContent }
          }
          break
        }

        case 'tool_started':
        case 'tool_finished':
        case 'tool_error':
          if (agentName) {
            next[agentName] = { ...next[agentName], logs: [...next[agentName].logs, ...allLogs] }
          } else if (activePipelineAgent.current) {
            next[activePipelineAgent.current] = {
              ...next[activePipelineAgent.current],
              logs: [...next[activePipelineAgent.current].logs, ...allLogs],
            }
          }
          break
      }

      return next
    })
  }, [])

  // Connect to SSE stream
  useEffect(() => {
    if (!decodedTaskId) return

    const cleanup = api.connectTaskStream(decodedTaskId, handleSSEEvent)
    return cleanup
  }, [decodedTaskId, handleSSEEvent])

  // Poll for status as fallback / to catch completion
  useEffect(() => {
    fetchStatus()
    if (!task || task.status === 'running') {
      const interval = setInterval(fetchStatus, 3000)
      return () => clearInterval(interval)
    }
  }, [fetchStatus, task?.status])

  // When task completes/fails, mark appropriate agents
  useEffect(() => {
    if (!task) return
    if (task.status === 'completed' || task.status === 'failed') {
      setAgentStates(prev => {
        const next = { ...prev }
        const finalStatus: AgentStatus = task.status === 'completed' ? 'done' : 'error'
        ALL_AGENTS.forEach(a => {
          if (prev[a.name].status === 'idle' || prev[a.name].status === 'running') {
            next[a.name] = { ...next[a.name], status: finalStatus }
          }
        })
        return next
      })
    }
  }, [task?.status])

  // Auto-expand manager when crew starts
  useEffect(() => {
    const managerState = agentStates.manager
    if (managerState && managerState.logs.length > 0 && !expandedAgents.manager) {
      setExpandedAgents(prev => ({ ...prev, manager: true }))
    }
  }, [agentStates.manager?.logs.length])

  if (error && !task) {
    return (
      <div className="max-w-4xl mx-auto px-4 py-12 text-center">
        <XCircle className="w-12 h-12 text-red-500 mx-auto mb-4" />
        <h2 className="text-xl font-semibold text-slate-900 mb-2">Task Not Found</h2>
        <p className="text-slate-600 mb-6">{error}</p>
        <Link to="/" className="btn-primary">
          <ArrowLeft className="w-4 h-4 mr-2 inline" />
          Back to Home
        </Link>
      </div>
    )
  }

  const isRunning = task?.status === 'running'
  const isDone = task?.status === 'completed'
  const isFailed = task?.status === 'failed'

  return (
    <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">

      {/* Header */}
      <div className="flex items-start gap-4">
        <button
          onClick={() => navigate('/')}
          className="mt-1 btn-secondary p-2"
          title="Back to home"
        >
          <ArrowLeft className="w-4 h-4" />
        </button>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-3 flex-wrap">
            <h1 className="text-2xl font-bold text-slate-900 truncate">
              {task?.task_name || decodedTaskId}
            </h1>
            {isRunning && (
              <span className="status-badge status-running">
                <Loader2 className="w-3 h-3 animate-spin mr-1" />
                Running
              </span>
            )}
            {isDone && (
              <span className="status-badge status-completed">
                <CheckCircle className="w-3 h-3 mr-1" />
                Completed
              </span>
            )}
            {isFailed && (
              <span className="status-badge status-failed">
                <XCircle className="w-3 h-3 mr-1" />
                Failed
              </span>
            )}
            {sseConnected && isRunning && (
              <span className="status-badge" style={{ background: '#dbeafe', color: '#1d4ed8' }}>
                <span className="inline-block w-2 h-2 rounded-full bg-blue-500 mr-1 animate-pulse" />
                Live
              </span>
            )}
          </div>
          {task?.task_id && (
            <p className="text-xs text-slate-400 mt-1 font-mono truncate">
              {task.task_id}
            </p>
          )}
          {task?.start_time && (
            <p className="text-sm text-slate-500 mt-1">
              Started: {new Date(task.start_time).toLocaleString('zh-CN')}
              {task.end_time && ` — Finished: ${new Date(task.end_time).toLocaleString('zh-CN')}`}
            </p>
          )}
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={fetchStatus}
            className="btn-secondary p-2"
            title="Refresh"
          >
            <RefreshCw className={`w-4 h-4${isRunning ? ' animate-spin' : ''}`} />
          </button>
          {isDone && (
            <Link
              to={`/reports/${encodeURIComponent(decodedTaskId)}`}
              className="btn-primary flex items-center gap-2"
            >
              <FileText className="w-4 h-4" />
              View Report
            </Link>
          )}
        </div>
      </div>

      {/* Error banner */}
      {isFailed && task?.error && (
        <div className="p-4 bg-red-50 border border-red-200 rounded-xl text-red-700">
          <p className="font-medium">Task Failed</p>
          <p className="text-sm mt-1">{task.error}</p>
        </div>
      )}

      {/* Success summary */}
      {isDone && task?.summary && (
        <div className="p-4 bg-green-50 border border-green-200 rounded-xl text-green-800">
          <p className="text-sm">{task.summary}</p>
        </div>
      )}

      {/* Agent pipeline */}
      <div className="card">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-slate-900">Analysis Pipeline</h2>
          <div className="flex items-center gap-2">
            {/* Pipeline progress indicator */}
            {isRunning && (
              <div className="flex items-center gap-1">
                {PIPELINE_AGENTS.map((agent) => {
                  const state = agentStates[agent.name]
                  return (
                    <div
                      key={agent.name}
                      className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-medium transition-colors ${
                        state.status === 'done' ? 'bg-green-500 text-white' :
                        state.status === 'running' ? 'bg-blue-500 text-white animate-pulse' :
                        state.status === 'error' ? 'bg-red-500 text-white' :
                        'bg-slate-200 text-slate-400'
                      }`}
                      title={`${agent.label}: ${state.status}`}
                    >
                      {state.status === 'done' ? '✓' :
                       state.status === 'running' ? '●' :
                       state.status === 'error' ? '✗' : '○'}
                    </div>
                  )
                })}
              </div>
            )}
          </div>
        </div>

        <div className="space-y-2">
          {ALL_AGENTS.map((agent) => {
            const state = agentStates[agent.name] || { status: 'idle' as AgentStatus, logs: [] }
            const isExpanded = expandedAgents[agent.name] || false

            return (
              <div key={agent.name} className="border border-slate-200 rounded-lg overflow-hidden">
                <button
                  onClick={() => setExpandedAgents(prev => ({ ...prev, [agent.name]: !prev[agent.name] }))}
                  className="w-full flex items-center gap-3 p-3 hover:bg-slate-50 transition-colors text-left"
                >
                  <div className="flex-shrink-0">
                    {state.status === 'done' ? (
                      <CheckCircle className="w-5 h-5 text-green-500" />
                    ) : state.status === 'error' ? (
                      <XCircle className="w-5 h-5 text-red-500" />
                    ) : state.status === 'running' ? (
                      <div className="relative">
                        <Loader2 className="w-5 h-5 text-blue-500 animate-spin" />
                      </div>
                    ) : (
                      <div className="w-5 h-5 rounded-full border-2 border-slate-300" />
                    )}
                  </div>
                  <span className="font-medium text-slate-900">{agent.label}</span>
                  <span className="text-sm text-slate-500 hidden sm:inline">{agent.description}</span>
                  {state.status === 'running' && (
                    <span className="text-xs text-blue-600 font-medium ml-2 animate-pulse">running...</span>
                  )}
                  {state.logs.length > 0 && (
                    <span className="text-xs text-slate-400 ml-auto">
                      {state.logs.length} event{state.logs.length !== 1 ? 's' : ''}
                    </span>
                  )}
                  {isExpanded ? (
                    <ChevronDown className="w-4 h-4 text-slate-400 ml-auto" />
                  ) : (
                    <ChevronRight className="w-4 h-4 text-slate-400 ml-auto" />
                  )}
                </button>

                {isExpanded && (
                  <div className="border-t border-slate-200">
                    {state.fullLog || state.logs.length > 0 ? (
                      <LogViewer
                        fullLog={state.fullLog}
                        content={state.logs.join('\n')}
                      />
                    ) : (
                      <div className="p-4 text-sm text-slate-400 italic">
                        {state.status === 'idle' ? 'Waiting...' : 'No log output yet...'}
                      </div>
                    )}
                  </div>
                )}
              </div>
            )
          })}
        </div>
      </div>

    </div>
  )
}
