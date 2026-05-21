const API_BASE = '/api'

export interface TaskStatus {
  task_id: string
  task_name: string
  status: 'running' | 'completed' | 'failed'
  start_time?: string
  end_time?: string
  summary?: string
  error?: string
  agent_logs?: AgentLogEntry[]
}

export interface AgentLogEntry {
  agent: string
  status: string
  logs: string[]
}

export interface TaskCreate {
  query: string
}

export interface TaskCreateResponse {
  task_id: string
  status: string
}

export interface TaskListResponse {
  tasks: TaskStatus[]
  total: number
}

// SSE Event types matching the backend
export interface SSECrewStartedEvent {
  type: 'crew_started'
  crew_name: string
  inputs?: Record<string, string>
}

export interface SSECrewCompletedEvent {
  type: 'crew_completed'
  output: string
}

export interface SSECrewFailedEvent {
  type: 'crew_failed'
  error: string
}

export interface SSETaskStartedEvent {
  type: 'task_started'
  task_id: string
  task_name: string
  agent_key: string
}

export interface SSETaskCompletedEvent {
  type: 'task_completed'
  task_id: string
  task_name: string
  output: string
}

export interface SSETaskFailedEvent {
  type: 'task_failed'
  task_id: string
  task_name: string
  error: string
}

export interface SSEAgentStartedEvent {
  type: 'agent_started'
  agent_role: string
  agent_key: string
  task_name: string
  prompt?: string
}

export interface SSEAgentCompletedEvent {
  type: 'agent_completed'
  agent_role: string
  agent_key: string
  task_name: string
  output: string
}

export interface SSEAgentErrorEvent {
  type: 'agent_error'
  agent_role: string
  agent_key: string
  task_name: string
  error: string
}

export interface SSEToolStartedEvent {
  type: 'tool_started'
  agent_role: string
  agent_key: string
  tool_name: string
  tool_args: Record<string, string>
  task_name: string
  crew_task_id: string
  input?: string
}

export interface SSEToolFinishedEvent {
  type: 'tool_finished'
  agent_role: string
  agent_key: string
  tool_name: string
  output: string
  task_name: string
  from_cache: boolean
  crew_task_id: string
}

export interface SSEToolErrorEvent {
  type: 'tool_error'
  agent_role: string
  agent_key: string
  tool_name: string
  error: string
  task_name: string
  crew_task_id: string
}

export interface SSEAgentLogEvent {
  type: 'agent_log'
  agent_key: string
  log_content: string
}

export interface SSEConnectedEvent {
  type: 'connected'
  task_id: string
}

export type SSEEvent =
  | SSECrewStartedEvent
  | SSECrewCompletedEvent
  | SSECrewFailedEvent
  | SSETaskStartedEvent
  | SSETaskCompletedEvent
  | SSETaskFailedEvent
  | SSEAgentStartedEvent
  | SSEAgentCompletedEvent
  | SSEAgentErrorEvent
  | SSEToolStartedEvent
  | SSEToolFinishedEvent
  | SSEToolErrorEvent
  | SSEAgentLogEvent
  | SSEConnectedEvent

type SSEEventHandler = (event: SSEEvent) => void

async function fetchJSON<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || `HTTP ${res.status}`)
  }
  return res.json() as Promise<T>
}

export const api = {
  healthCheck: () =>
    fetchJSON<{ status: string }>(`${API_BASE}/health`),

  createTask: (data: TaskCreate) =>
    fetchJSON<TaskCreateResponse>(`${API_BASE}/tasks`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  listTasks: (skip = 0, limit = 20) =>
    fetchJSON<TaskListResponse>(`${API_BASE}/tasks?skip=${skip}&limit=${limit}`),

  getTaskStatus: (taskId: string) =>
    fetchJSON<TaskStatus>(`${API_BASE}/tasks/${encodeURIComponent(taskId)}`),

  deleteTask: (taskId: string) =>
    fetch(`${API_BASE}/tasks/${encodeURIComponent(taskId)}`, { method: 'DELETE' }),

  getReport: (taskId: string) =>
    fetchJSON<{ task_id: string; report_content: string }>(
      `${API_BASE}/reports/${encodeURIComponent(taskId)}`
    ),

  getAgentLog: (taskId: string, agent: string) =>
    fetchJSON<{ task_id: string; agent: string; log_content: string }>(
      `${API_BASE}/reports/${encodeURIComponent(taskId)}/logs/${encodeURIComponent(agent)}`
    ),

  getDataFile: (taskId: string, name: string) =>
    fetch(`${API_BASE}/reports/${encodeURIComponent(taskId)}/data/${encodeURIComponent(name)}`).then(r => r.json()),

  getPapers: (taskId: string) =>
    fetch(`${API_BASE}/reports/${encodeURIComponent(taskId)}/papers`).then(r => r.json()),

  downloadReport: (taskId: string) => {
    window.open(`${API_BASE}/reports/${encodeURIComponent(taskId)}/download`, '_blank')
  },

  /**
   * Connect to SSE stream for real-time task events.
   * Returns a cleanup function.
   */
  connectTaskStream: (taskId: string, onEvent: SSEEventHandler): () => void => {
    const url = `${API_BASE}/tasks/${encodeURIComponent(taskId)}/stream`
    const es = new EventSource(url)

    es.addEventListener('connected', (e: MessageEvent) => {
      try {
        const data = JSON.parse(e.data) as SSEEvent
        onEvent(data)
      } catch {
        // ignore parse errors
      }
    })

    es.addEventListener('message', (e: MessageEvent) => {
      try {
        const data = JSON.parse(e.data) as SSEEvent
        onEvent(data)
      } catch {
        // ignore parse errors
      }
    })

    return () => {
      es.close()
    }
  },
}
