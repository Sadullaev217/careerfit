import type { HealthResponse, Document, TargetRole, Analysis, Me } from '../types/index.js';
import type { TargetRoleInput, PortfolioLinkInput } from '../schemas/index.js';

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
    public readonly body?: unknown,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

type GetToken = () => string | null | undefined | Promise<string | null | undefined>;

export function createApiClient(baseUrl: string, getToken?: GetToken) {
  async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
    const token = await getToken?.();
    const res = await fetch(`${baseUrl}${path}`, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
    });

    const text = await res.text();
    let body: unknown = text;
    try {
      body = text ? JSON.parse(text) : undefined;
    } catch {
      // Non-JSON error pages are kept as text.
    }
    if (!res.ok) throw new ApiError(res.status, `API error ${res.status}: ${path}`, body);
    return body as T;
  }

  const post = <T>(path: string, data: unknown) =>
    request<T>(path, { method: 'POST', body: JSON.stringify(data) });

  return {
    health: {
      check: () => request<HealthResponse>('/health'),
    },
    account: {
      me: () => request<Me>('/me'),
      delete: () => request<void>('/account', { method: 'DELETE' }),
    },
    documents: {
      list: () => request<Document[]>('/documents'),
      addPortfolioLink: (data: PortfolioLinkInput) => post<Document>('/documents/portfolio', data),
      delete: (id: string) => request<void>(`/documents/${id}`, { method: 'DELETE' }),
      parseStatus: (id: string) => request<{ status: string }>(`/documents/${id}/status`),
    },
    targetRoles: {
      create: (data: TargetRoleInput) => post<TargetRole>('/target-roles', data),
      list: () => request<TargetRole[]>('/target-roles'),
    },
    analyses: {
      start: (targetRoleId: string) => post<{ analysisId: string }>('/analyses', { targetRoleId }),
      get: (id: string) => request<Analysis>(`/analyses/${id}`),
      list: () => request<Analysis[]>('/analyses'),
    },
  };
}

export type ApiClient = ReturnType<typeof createApiClient>;
