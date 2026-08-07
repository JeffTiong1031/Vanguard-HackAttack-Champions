/**
 * Policy-service HTTP client.
 *
 * 🔴 BACKGROUND SERVICE WORKER ONLY. A content script on https://chatgpt.com
 * cannot fetch http:// on a LAN address -- Chrome blocks it as mixed content,
 * and http://localhost is a special case that does not generalise to the
 * two-laptop demo. The service worker runs on a chrome-extension:// origin,
 * which is a secure context, so it may fetch http:// with host permissions.
 * See spec section 5.4.
 */
import { POLICY_CONFIG, getPolicyBase } from './config';
import { getCachedPolicy, getEnrolment, getEtag, saveEnrolment, savePolicy } from './store';
import type { Enrolment, Policy } from './types';

async function timedFetch(url: string, init?: RequestInit): Promise<Response> {
  const abort = new AbortController();
  const timer = setTimeout(() => abort.abort(), POLICY_CONFIG.requestTimeoutMs);
  try {
    return await fetch(url, { ...init, signal: abort.signal });
  } finally {
    clearTimeout(timer);
  }
}

export async function enrol(token: string): Promise<Enrolment> {
  const base = await getPolicyBase();
  const response = await timedFetch(`${base}/v1/enroll`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ token }),
  });
  if (response.status === 401) {
    throw new Error('That enrolment token was not recognised. Check it with your admin.');
  }
  if (!response.ok) throw new Error(`Enrolment failed (${response.status}).`);

  const body = (await response.json()) as Enrolment & { policy: Policy };
  const enrolment: Enrolment = {
    org_id: body.org_id, org_name: body.org_name,
    pseudo_id: body.pseudo_id, department: body.department,
    department_id: (body as Enrolment).department_id,
  };
  await saveEnrolment(enrolment, body.policy);
  return enrolment;
}

/**
 * Conditional GET. Returns the current policy, or null if not enrolled.
 *
 * A network failure returns the CACHED policy rather than throwing. ADR 0014:
 * a dead service degrades to advisory, it never blocks the user's work.
 */
export async function refreshPolicy(): Promise<Policy | null> {
  const enrolment = await getEnrolment();
  if (!enrolment) return null;

  const base = await getPolicyBase();
  const etag = await getEtag();
  try {
    const deptParam = enrolment.department_id
      ? `&department_id=${encodeURIComponent(enrolment.department_id)}`
      : '';
    const response = await timedFetch(
      `${base}/v1/policy?org_id=${encodeURIComponent(enrolment.org_id)}${deptParam}`,
      { headers: etag ? { 'If-None-Match': etag } : {} },
    );
    if (response.status === 304) return await getCachedPolicy();
    if (!response.ok) return await getCachedPolicy();

    const policy = (await response.json()) as Policy;
    await savePolicy(policy, response.headers.get('etag'));
    return policy;
  } catch {
    return await getCachedPolicy();
  }
}

export async function sendAccessRequest(llmId: string, reason: string): Promise<void> {
  const enrolment = await getEnrolment();
  if (!enrolment) throw new Error('Not enrolled.');
  const base = await getPolicyBase();
  const response = await timedFetch(`${base}/v1/requests`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ pseudo_id: enrolment.pseudo_id, llm_id: llmId, reason }),
  });
  if (!response.ok) throw new Error(`Request failed (${response.status}).`);
}

import type { NotificationRow } from './messages';

export async function fetchNotifications(): Promise<NotificationRow[]> {
  const enrolment = await getEnrolment();
  if (!enrolment) return [];
  const base = await getPolicyBase();
  try {
    const res = await timedFetch(`${base}/v1/notifications?pseudo_id=${encodeURIComponent(enrolment.pseudo_id)}`);
    if (!res.ok) return [];
    return (await res.json()) as NotificationRow[];
  } catch {
    return [];
  }
}

export async function fetchRequests(): Promise<any[]> {
  const enrolment = await getEnrolment();
  if (!enrolment) return [];
  const base = await getPolicyBase();
  try {
    const res = await timedFetch(`${base}/v1/requests?pseudo_id=${encodeURIComponent(enrolment.pseudo_id)}`);
    if (!res.ok) return [];
    return await res.json();
  } catch {
    return [];
  }
}
