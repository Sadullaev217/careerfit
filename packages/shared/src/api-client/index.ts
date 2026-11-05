import type {
  HealthResponse,
  Document,
  DocumentAnalysis,
  MarketRequirements,
  TargetRole,
  Analysis,
  Me,
  PlanInfo,
  RoleSuggestion,
} from '../types/index.js';
import type { TargetRoleInput, PortfolioLinkInput } from '../schemas/index.js';

export const MAX_UPLOAD_BYTES = 10 * 1024 * 1024;

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

export function apiErrorMessage(error: unknown, fallback: string): string {
  if (error instanceof ApiError) {
    const detail = (error.body as { detail?: { message?: unknown } } | undefined)?.detail;
    if (typeof detail?.message === 'string') return detail.message;
  }
  return fallback;
}

export function apiErrorCode(error: unknown): string | null {
  if (error instanceof ApiError) {
    const detail = (error.body as { detail?: { code?: unknown } } | undefined)?.detail;
    if (typeof detail?.code === 'string') return detail.code;
  }
  return null;
}

type GetToken = () => string | null | undefined | Promise<string | null | undefined>;

function parseBody(text: string): unknown {
  try {
    return text ? JSON.parse(text) : undefined;
  } catch {
    return text;
  }
}

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

    const body = parseBody(await res.text());
    if (!res.ok) throw new ApiError(res.status, `API error ${res.status}: ${path}`, body);
    return body as T;
  }

  const post = <T>(path: string, data: unknown) =>
    request<T>(path, { method: 'POST', body: JSON.stringify(data) });

  // fetch can't report upload progress, and XMLHttpRequest works in browsers and React Native.
  async function upload<T>(
    path: string,
    form: FormData,
    onProgress?: (fraction: number) => void,
  ): Promise<T> {
    const token = await getToken?.();
    return new Promise<T>((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      xhr.open('POST', `${baseUrl}${path}`);
      if (token) xhr.setRequestHeader('Authorization', `Bearer ${token}`);
      xhr.upload.onprogress = (event) => {
        if (event.lengthComputable) onProgress?.(event.loaded / event.total);
      };
      xhr.onload = () => {
        const body = parseBody(xhr.responseText);
        if (xhr.status >= 200 && xhr.status < 300) resolve(body as T);
        else reject(new ApiError(xhr.status, `API error ${xhr.status}: ${path}`, body));
      };
      xhr.onerror = () => reject(new ApiError(0, `Network error: ${path}`));
      xhr.send(form);
    });
  }

  return {
    health: {
      check: () => request<HealthResponse>('/health'),
    },
    account: {
      me: () => request<Me>('/me'),
      plan: () => request<PlanInfo>('/account/plan'),
      delete: () => request<void>('/account', { method: 'DELETE' }),
    },
    documents: {
      list: () => request<Document[]>('/documents'),
      upload: (form: FormData, onProgress?: (fraction: number) => void) =>
        upload<Document>('/documents', form, onProgress),
      addPortfolioLink: (data: PortfolioLinkInput) => post<Document>('/documents/portfolio', data),
      delete: (id: string) => request<void>(`/documents/${id}`, { method: 'DELETE' }),
      status: (id: string) => request<Document>(`/documents/${id}/status`),
      analysis: (id: string) => request<DocumentAnalysis>(`/documents/${id}/profile`),
    },
    market: {
      roles: (query: string, language: 'en' | 'ru' = 'en') =>
        request<RoleSuggestion[]>(
          `/market/roles?${new URLSearchParams({ q: query, language }).toString()}`,
        ),
      requirements: (role: string, region?: string, language: 'en' | 'ru' = 'en') => {
        const query = new URLSearchParams({ role, language, ...(region ? { region } : {}) });
        return request<MarketRequirements>(`/market/requirements?${query.toString()}`);
      },
    },
    targetRoles: {
      create: (data: TargetRoleInput) => post<TargetRole>('/target-roles', data),
      list: () => request<TargetRole[]>('/target-roles'),
    },
    analyses: {
      start: (data: {
        documentId: string;
        role: string;
        occupationCode?: string;
        region?: string;
        language?: 'en' | 'ru';
      }) =>
        post<{ analysisId: string }>('/analyses', data),
      get: (id: string) => request<Analysis>(`/analyses/${id}`),
      list: () => request<Analysis[]>('/analyses'),
    },
    notifications: {
      register: (data: { token: string; platform: 'ios' | 'android'; language?: 'en' | 'ru' }) =>
        request<void>('/push-tokens', { method: 'PUT', body: JSON.stringify(data) }),
      remove: (token: string) =>
        request<void>(`/push-tokens/${encodeURIComponent(token)}`, { method: 'DELETE' }),
    },
  };
}

export type ApiClient = ReturnType<typeof createApiClient>;
