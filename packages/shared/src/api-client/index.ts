import type {
  HealthResponse,
  Profile,
  Document,
  TargetRole,
  Analysis,
} from '../types/index.js';
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

async function request<T>(
  baseUrl: string,
  path: string,
  options: RequestInit & { token?: string | undefined } = {},
): Promise<T> {
  const { token, ...fetchOptions } = options;
  const headers: HeadersInit = {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...(fetchOptions.headers ?? {}),
  };

  const res = await fetch(`${baseUrl}${path}`, { ...fetchOptions, headers });

  if (!res.ok) {
    let body: unknown;
    try {
      body = await res.json();
    } catch {
      body = await res.text();
    }
    throw new ApiError(res.status, `API error ${res.status}: ${path}`, body);
  }

  return res.json() as Promise<T>;
}

export function createApiClient(baseUrl: string, getToken?: () => string | null) {
  const auth = () => getToken?.() ?? undefined;

  return {
    health: {
      check: () => request<HealthResponse>(baseUrl, '/health'),
    },

    profile: {
      get: () => request<Profile>(baseUrl, '/profile', { token: auth() ?? undefined }),
      delete: () =>
        request<void>(baseUrl, '/profile', { method: 'DELETE', token: auth() ?? undefined }),
    },

    documents: {
      list: () =>
        request<Document[]>(baseUrl, '/documents', { token: auth() ?? undefined }),
      addPortfolioLink: (data: PortfolioLinkInput) =>
        request<Document>(baseUrl, '/documents/portfolio', {
          method: 'POST',
          body: JSON.stringify(data),
          token: auth() ?? undefined,
        }),
      delete: (id: string) =>
        request<void>(baseUrl, `/documents/${id}`, {
          method: 'DELETE',
          token: auth() ?? undefined,
        }),
      parseStatus: (id: string) =>
        request<{ status: string }>(baseUrl, `/documents/${id}/status`, {
          token: auth() ?? undefined,
        }),
    },

    targetRoles: {
      create: (data: TargetRoleInput) =>
        request<TargetRole>(baseUrl, '/target-roles', {
          method: 'POST',
          body: JSON.stringify(data),
          token: auth() ?? undefined,
        }),
      list: () =>
        request<TargetRole[]>(baseUrl, '/target-roles', { token: auth() ?? undefined }),
    },

    analyses: {
      start: (targetRoleId: string) =>
        request<{ analysisId: string }>(baseUrl, '/analyses', {
          method: 'POST',
          body: JSON.stringify({ targetRoleId }),
          token: auth() ?? undefined,
        }),
      get: (id: string) =>
        request<Analysis>(baseUrl, `/analyses/${id}`, { token: auth() ?? undefined }),
      list: () =>
        request<Analysis[]>(baseUrl, '/analyses', { token: auth() ?? undefined }),
    },
  };
}

export type ApiClient = ReturnType<typeof createApiClient>;
