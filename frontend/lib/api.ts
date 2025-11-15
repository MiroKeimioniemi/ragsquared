const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5000';

export interface Audit {
  id: string;
  external_id: string;
  status: 'queued' | 'running' | 'completed' | 'failed';
  is_draft: boolean;
  chunk_completed: number;
  chunk_total: number;
  created_at: string;
  completed_at?: string;
  failed_at?: string;
  failure_reason?: string;
  document_id?: string;
}

export interface Document {
  id: string;
  external_id: string;
  original_filename: string;
  organization?: string;
  source_type?: string;
  description?: string;
  created_at: string;
}

export interface Citation {
  type: string;
  reference: string;
}

export interface FlagContext {
  total_tokens: number;
  manual_neighbors_count: number;
  regulation_slices_count: number;
  guidance_slices_count: number;
  evidence_slices_count: number;
  truncated?: boolean;
  manual_neighbors?: Array<{
    label: string;
    content_preview: string;
    score?: number;
    metadata?: Record<string, any>;
  }>;
  regulation_slices?: Array<{
    label: string;
    content_preview: string;
    score?: number;
  }>;
  guidance_slices?: Array<{
    label: string;
    content_preview: string;
    score?: number;
  }>;
  evidence_slices?: Array<{
    label: string;
    content_preview: string;
    score?: number;
    metadata?: Record<string, any>;
  }>;
}

export interface Flag {
  id: string;
  flag_id?: string;
  flag_type: 'RED' | 'YELLOW' | 'GREEN';
  severity_score: number;
  findings: string;
  gaps?: string[];
  recommendations?: string[];
  chunk_id: string;
  regulation_reference?: string;
  citations?: Citation[];
  context?: FlagContext;
}

export interface FlagSummary {
  compliance_score: number;
  total_flags: number;
  red_count: number;
  yellow_count: number;
  green_count: number;
}

export interface AuditWithDetails extends Audit {
  document?: Document;
  flag_summary?: FlagSummary;
  started_at?: string;
  failure_reason?: string;
}

export interface AuditorQuestion {
  question_id: string;
  regulation_reference: string;
  question_text: string;
  priority: number;
  rationale?: string;
  related_flag_ids?: string[];
  created_at: string;
}

async function fetchAPI<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const url = `${API_BASE_URL}${endpoint}`;
  const response = await fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ error: 'Unknown error' }));
    throw new Error(error.error || `HTTP ${response.status}`);
  }

  return response.json();
}

export const api = {
  audits: {
    list: async (filters?: { status?: string; is_draft?: string; limit?: number }): Promise<AuditWithDetails[]> => {
      const params = new URLSearchParams();
      if (filters?.status) params.append('status', filters.status);
      if (filters?.is_draft !== undefined) params.append('is_draft', filters.is_draft);
      if (filters?.limit) params.append('limit', filters.limit.toString());
      const response = await fetchAPI<{audits: AuditWithDetails[], count: number}>(`/api/audits?${params.toString()}`);
      return response.audits;
    },
    get: async (auditId: string): Promise<AuditWithDetails> => {
      const response = await fetchAPI<{audit: AuditWithDetails}>(`/api/audits/${auditId}`);
      const audit = response.audit;
      // If audit is completed, fetch flag summary
      if (audit.status === 'completed' && !audit.flag_summary) {
        try {
          const flags = await api.flags.list(auditId);
          if (flags.length > 0) {
            // Calculate flag summary
            const red_count = flags.filter(f => f.flag_type === 'RED').length;
            const yellow_count = flags.filter(f => f.flag_type === 'YELLOW').length;
            const green_count = flags.filter(f => f.flag_type === 'GREEN').length;
            const total_flags = flags.length;
            // Calculate compliance score (simplified fallback - backend uses exponential decay for consecutive)
            // Backend: RED = -20, YELLOW = -10, with exponential decay for consecutive flags
            // If 100% red or 100% green, score = 0
            let compliance_score = 100;
            if (total_flags > 0 && (red_count === total_flags || green_count === total_flags)) {
              compliance_score = 0;
            } else {
              compliance_score = Math.max(0, Math.min(100, 
                100 - (red_count * 20) - (yellow_count * 10)
              ));
            }
            audit.flag_summary = {
              compliance_score,
              total_flags,
              red_count,
              yellow_count,
              green_count,
            };
          }
        } catch (e) {
          // Ignore errors when fetching flags
        }
      }
      return audit;
    },
    getStatus: async (auditId: string) => {
      return fetchAPI(`/api/audits/${auditId}/status`);
    },
    resume: async (auditId: string) => {
      return fetchAPI(`/api/audits/${auditId}/resume`, { method: 'POST' });
    },
    generateFinalReport: async (auditId: string) => {
      return fetchAPI(`/review/${auditId}/final-report`, { method: 'POST' });
    },
  },
  documents: {
    upload: async (file: File, metadata?: { organization?: string; source_type?: string; description?: string }) => {
      const formData = new FormData();
      formData.append('file', file);
      if (metadata?.organization) formData.append('organization', metadata.organization);
      if (metadata?.source_type) formData.append('source_type', metadata.source_type);
      if (metadata?.description) formData.append('description', metadata.description);

      const response = await fetch(`${API_BASE_URL}/api/documents`, {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        const error = await response.json().catch(() => ({ error: 'Unknown error' }));
        throw new Error(error.error || `HTTP ${response.status}`);
      }

      return response.json();
    },
  },
  flags: {
    list: async (auditId: string, filters?: { severity?: string; regulation?: string }): Promise<Flag[]> => {
      const params = new URLSearchParams();
      if (filters?.severity) params.append('severity', filters.severity);
      if (filters?.regulation) params.append('regulation', filters.regulation);
      const response = await fetchAPI<{flags: any[], pagination: any}>(`/api/audits/${auditId}/flags?${params.toString()}`);
      // Map the API response to our Flag interface
      return response.flags.map((flag: any) => ({
        id: flag.flag_id || flag.id,
        flag_id: flag.flag_id || flag.id,
        flag_type: flag.flag_type,
        severity_score: flag.severity_score,
        findings: flag.findings,
        gaps: flag.gaps,
        recommendations: flag.recommendations,
        chunk_id: flag.chunk_id,
        regulation_reference: flag.citations?.[0]?.reference,
        citations: flag.citations,
      }));
    },
  },
  questions: {
    list: async (auditId: string): Promise<AuditorQuestion[]> => {
      const response = await fetchAPI<{flags: any[], questions?: AuditorQuestion[], pagination: any}>(`/api/audits/${auditId}/flags?include_questions=1`);
      return response.questions || [];
    },
  },
  regulations: {
    list: async (auditId: string): Promise<string[]> => {
      // Get all flags and extract unique regulation references
      const flags = await api.flags.list(auditId);
      const regulations = new Set<string>();
      flags.forEach(flag => {
        flag.citations?.forEach(citation => {
          if (citation.type === 'regulation') {
            regulations.add(citation.reference);
          }
        });
      });
      return Array.from(regulations).sort();
    },
  },
};

