/** Wire types, mirroring code/policy/app/models.py. If you change one, change both. */
export type Tool = {
  llm_id: string;
  host: string;
  display_name: string;
  status: 'approved' | 'blocked';
};

export type Category = { key: string; label: string; enabled: boolean };

export type Policy = {
  org_id: string;
  org_name: string;
  version: number;
  tools: Tool[];
  categories: Category[];
};

/** What enrolment returns and what we persist. No name, no email — the server
 *  never issues one, so there is nothing here to leak. */
export type Enrolment = {
  org_id: string;
  org_name: string;
  pseudo_id: string;
  department: string;
  department_id?: string;
};

export type GovernanceEventType =
  | 'visit_unapproved' | 'warn_shown' | 'request_sent' | 'ethics_block' | 'pii_block'
  | 'prompt_sent';

export type RiskLevel = 'low' | 'medium' | 'high';

export type GovernanceEvent = {
  host: string;
  type: GovernanceEventType;
  category?: string;
  finding_hash?: string;
  risk_level?: RiskLevel;
  ts: string;
};
