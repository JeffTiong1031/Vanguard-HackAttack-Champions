/**
 * Appeal client. BACKGROUND SERVICE WORKER ONLY (same reason as client.ts: a
 * content script cannot fetch http:// on a LAN address).
 *
 * 🔴 I3: the payload is class + reason. `disclosed_text` is attached ONLY when
 * the caller passes it -- which the modal does only when the employee ticks the
 * opt-in box. The key is omitted entirely otherwise, so it can never default to
 * carrying the prompt.
 */
import { getPolicyBase } from './config';
import { getEnrolment } from './store';

export type AppealInput = {
  decisionType: 'ethics' | 'pii';
  category: string;
  reason: string;
  disclosedText?: string;
  /** A hash of the blocked prompt (never the text). Lets an overturned ethics
   *  appeal grant a one-time pass on that exact prompt. */
  promptHash?: string;
};

export type AppealRow = {
  id: string;
  decision_type: string;
  category: string;
  status: 'pending' | 'upheld' | 'overturned';
  admin_note: string | null;
  created_at: string;
  decided_at: string | null;
};

export async function submitAppeal(input: AppealInput): Promise<void> {
  const enrolment = await getEnrolment();
  if (!enrolment) throw new Error('Not enrolled.');
  const base = await getPolicyBase();
  const body: Record<string, unknown> = {
    pseudo_id: enrolment.pseudo_id,
    decision_type: input.decisionType,
    category: input.category,
    reason: input.reason,
  };
  if (input.disclosedText) body.disclosed_text = input.disclosedText;
  if (input.promptHash) {
    body.prompt_hash = input.promptHash;
    body.scope_fingerprint = input.promptHash;
  }
  const res = await fetch(`${base}/v1/appeals`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`Appeal failed (${res.status}).`);
}

/**
 * Returns true when `promptHash` matches an appeal that was approved by a manager.
 * Uses the persistent /v1/appeals/approved-scopes endpoint — approved prompts
 * are never consumed/burned and remain passable until the policy changes.
 */
export async function grantPassIfAllowed(promptHash: string): Promise<boolean> {
  const enrolment = await getEnrolment();
  if (!enrolment) return false;
  const base = await getPolicyBase();
  try {
    const res = await fetch(`${base}/v1/appeals/approved-scopes?pseudo_id=${encodeURIComponent(enrolment.pseudo_id)}`);
    if (!res.ok) return false;
    const approvedScopes = (await res.json()) as string[];
    return approvedScopes.includes(promptHash);
  } catch {
    return false;
  }
}

export async function fetchMyAppeals(): Promise<AppealRow[]> {
  const enrolment = await getEnrolment();
  if (!enrolment) return [];
  const base = await getPolicyBase();
  const res = await fetch(`${base}/v1/appeals?pseudo_id=${encodeURIComponent(enrolment.pseudo_id)}`);
  if (!res.ok) return [];
  return (await res.json()) as AppealRow[];
}
