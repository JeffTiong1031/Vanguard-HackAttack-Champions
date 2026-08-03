/** Typed error classes for programmatic error handling. */
export class ApiError extends Error {
  constructor(message: string, readonly status: number) {
    super(message);
    this.name = 'ApiError';
  }
}

export class UnauthorisedError extends ApiError {
  constructor() {
    super('unauthorised', 401);
    this.name = 'UnauthorisedError';
  }
}

export class NetworkError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'NetworkError';
  }
}

/** Typed fetch wrapper. `credentials: 'include'` carries the HttpOnly session
 *  cookie the admin login sets — the console never holds a token itself. */
async function call<T>(method: 'GET' | 'POST', path: string, body?: unknown): Promise<T> {
  let response: Response;
  try {
    response = await fetch(path, {
      method,
      credentials: 'include',
      headers: body ? { 'content-type': 'application/json' } : undefined,
      body: body ? JSON.stringify(body) : undefined,
    });
  } catch (err) {
    throw new NetworkError(`Could not reach the policy service. Is it running? (${err instanceof Error ? err.message : String(err)})`);
  }

  if (response.status === 401) throw new UnauthorisedError();
  if (!response.ok) throw new ApiError(`${method} ${path} failed: ${response.status}`, response.status);

  if (response.status === 204 || response.headers.get('content-length') === '0') {
    return undefined as T;
  }

  try {
    return (await response.json()) as T;
  } catch (err) {
    return undefined as T;
  }
}

export const api = {
  get: <T,>(path: string) => call<T>('GET', path),
  post: <T,>(path: string, body?: unknown) => call<T>('POST', path, body),
};

export type Tool = {
  llm_id: string; host: string; display_name: string;
  status: 'approved' | 'blocked';
};
export type TokenRow = {
  id: string; department: string; label: string; created_at: string; revoked: number;
};
export type RequestRow = {
  id: string; reason: string; status: 'pending' | 'approved' | 'denied';
  created_at: string; department: string; display_name: string;
  host: string; llm_id: string;
};
export type Usage = {
  by_department: { department: string; events: number }[];
  by_tool: { host: string; events: number }[];
  by_category: { category: string; events: number }[];
};
export type AppealRow = {
  id: string; decision_type: string; category: string; employee_reason: string;
  disclosed_text: string | null; status: 'pending' | 'upheld' | 'overturned';
  admin_note: string | null; created_at: string; department: string;
};

export type Scope = 'company' | 'department';

export type Session = {
  role: Scope;
  org_id: string;
  org_name: string;
  department_id?: string;
  department?: string;
};

export type LoginResult = {
  role: Scope;
  org_id: string;
  org_name: string;
  department_id?: string;
  department?: string;
};

export type Department = {
  id: string;
  name: string;
  created_at: string;
  active_tokens: number;
};
