import type { Enrolment, GovernanceEvent, Policy } from './types';
import type { AppealRow } from './appeals';

export type NotificationRow = {
  id: string;
  kind: string;
  title: string;
  message: string;
  status: 'unread' | 'read';
  created_at: string;
};

/** Content script -> background. Mirrors src/detection/l2/messages.ts's shape. */
export type PolicyRequest =
  | { kind: 'policy-get' }
  | { kind: 'policy-enrol'; token: string }
  | { kind: 'policy-request-access'; llmId: string; reason: string }
  | { kind: 'policy-event'; event: GovernanceEvent }
  | { kind: 'appeal-submit'; decisionType: 'ethics' | 'pii'; category: string; reason: string; disclosedText?: string; promptHash?: string }
  | { kind: 'appeals-get' }
  | { kind: 'appeal-allowance-check'; promptHash: string }
  | { kind: 'notifications-get' }
  | { kind: 'policy-requests-get' };

export type PolicyResponse =
  | { kind: 'policy-result'; ok: true; policy: Policy | null; enrolment: Enrolment | null }
  | { kind: 'policy-result'; ok: false; error: string };

export type RequestsResponse =
  | { kind: 'requests-result'; ok: true; requests: any[] }
  | { kind: 'requests-result'; ok: false; error: string };

export type AppealsResponse =
  | { kind: 'appeals-result'; ok: true; appeals: AppealRow[] }
  | { kind: 'appeals-result'; ok: false; error: string };

export type AllowanceResponse =
  | { kind: 'allowance-result'; ok: true; granted: boolean }
  | { kind: 'allowance-result'; ok: false; error: string };

export type NotificationsResponse =
  | { kind: 'notifications-result'; ok: true; notifications: NotificationRow[] }
  | { kind: 'notifications-result'; ok: false; error: string };

export function isPolicyRequest(msg: unknown): msg is PolicyRequest {
  const kind = (msg as PolicyRequest)?.kind;
  return typeof kind === 'string' && (kind.startsWith('policy-') || kind.startsWith('appeal') || kind.startsWith('notifications-'));
}
