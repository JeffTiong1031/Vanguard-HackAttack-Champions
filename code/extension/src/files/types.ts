import type { Finding } from '../detection/l1/types';
import type { SpanDecisionMap } from '../ui/send-review-logic';

export type ApiErrorCode =
  | 'too_large'
  | 'unsupported_type'
  | 'password_protected'
  | 'no_text_layer'
  | 'parse_failed'
  | 'timeout'
  | 'suspicious_archive'
  | 'extract_mismatch'
  | 'redaction_failed'
  | 'network'
  | 'unauthorized';

export type Coverage = {
  read: string[];
  /** 🔴 What we did NOT read. Rendered in the File pane: a clean extract is
   *  not a clean file, and the user must be able to see that boundary. */
  not_read: string[];
  pages_total: number | null;
  pages_with_text: number | null;
};

export type FileStatus =
  | { kind: 'held' }
  | { kind: 'extracting' }
  | { kind: 'scanning' }
  | { kind: 'scanned' }
  | { kind: 'error'; code: ApiErrorCode; message: string }
  | { kind: 'error_acknowledged'; code: ApiErrorCode; message: string; reason: string };

export type HeldFile = {
  id: string;
  file: File;
  status: FileStatus;
  extract?: string;
  extractSha256?: string;
  truncated?: boolean;
  coverage?: Coverage;
  warnings?: string[];
  findings?: Finding[];
  decisions?: SpanDecisionMap;
};

export type ExtractResponse = {
  extract: string;
  /** Sent back on /v1/redact so the backend can prove it is editing the same
   *  text the user reviewed. */
  extract_sha256: string;
  chars: number;
  truncated: boolean;
  format: 'txt' | 'csv' | 'docx' | 'pdf' | 'xlsx';
  coverage: Coverage;
  warnings: string[];
};
