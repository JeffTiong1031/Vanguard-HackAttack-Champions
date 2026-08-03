import type { Finding, FindingClass } from '../detection/l1/types';
import { runL1 } from '../detection/l1';
import { rewrite, SessionNumbering } from '../mask/placeholder';

/** L1 classes eligible for typing underlines — never PERSON/ORG (ADR 0024). */
export const L1_HINT_CLASSES: ReadonlySet<FindingClass> = new Set([
  'NRIC',
  'SSM',
  'NRIC_OR_SSM_AMBIGUOUS',
  'TIN',
  'EMAIL',
  'CARD',
]);

const CLASS_WHY: Record<string, string> = {
  NRIC: 'Looks like a Malaysian identity card number.',
  SSM: 'Looks like a company registration (SSM) number.',
  NRIC_OR_SSM_AMBIGUOUS: 'Could be an IC or an SSM number — structure alone cannot tell.',
  TIN: 'Looks like a tax identification number (TIN).',
  EMAIL: 'Looks like an email address.',
  CARD: 'Looks like a payment card number.',
};

export function findingKey(f: Finding): string {
  return `${f.cls}:${f.start}:${f.end}:${f.text}`;
}

export function hintFindings(text: string): Finding[] {
  return runL1(text).filter((f) => L1_HINT_CLASSES.has(f.cls));
}

export function visibleHints(text: string, dismissed: ReadonlySet<string>): Finding[] {
  return hintFindings(text).filter((f) => !dismissed.has(findingKey(f)));
}

export function pruneDismissed(text: string, dismissed: ReadonlySet<string>): Set<string> {
  const live = new Set(hintFindings(text).map(findingKey));
  const next = new Set<string>();
  for (const key of dismissed) {
    if (live.has(key)) next.add(key);
  }
  return next;
}

export function whyFor(cls: FindingClass): string {
  return CLASS_WHY[cls] ?? `Detected as ${cls}.`;
}

export function applyOneFinding(
  text: string,
  finding: Finding,
  numbering: SessionNumbering,
): string {
  return rewrite(text, [finding], numbering).rewritten;
}

export function recommendationFor(finding: Finding, numbering: SessionNumbering): string {
  return numbering.placeholderFor(finding.cls, finding.text);
}

export type HintPopoverSize = { width: number; height: number };

/**
 * Place the typing hint inside the viewport. A mark in the lower half opens
 * upward (the normal bottom-docked chat composer); a mark in the upper half
 * opens downward. If the preferred side cannot fit, use the other side. Both
 * axes are clamped for narrow windows and browser zoom.
 */
export function placeHintPopover(
  anchor: Pick<DOMRect, 'top' | 'bottom' | 'left'>,
  size: HintPopoverSize,
  viewportWidth: number,
  viewportHeight: number,
  gap = 8,
  margin = 8,
): { top: number; left: number; placement: 'above' | 'below' } {
  const maxLeft = Math.max(margin, viewportWidth - size.width - margin);
  const left = Math.min(Math.max(margin, anchor.left), maxLeft);
  const belowTop = anchor.bottom + gap;
  const aboveTop = anchor.top - gap - size.height;
  const fitsBelow = belowTop + size.height <= viewportHeight - margin;
  const fitsAbove = aboveTop >= margin;
  const prefersAbove = (anchor.top + anchor.bottom) / 2 > viewportHeight / 2;
  let placement: 'above' | 'below';
  if (prefersAbove) placement = fitsAbove || !fitsBelow ? 'above' : 'below';
  else placement = fitsBelow || !fitsAbove ? 'below' : 'above';
  const desiredTop = placement === 'below' ? belowTop : aboveTop;
  const maxTop = Math.max(margin, viewportHeight - size.height - margin);
  const top = Math.min(Math.max(margin, desiredTop), maxTop);

  return { top, left, placement };
}

/** Map adapter-text offsets onto composer textContent (handles ZWSP drift). */
export function locateInDom(
  content: string,
  finding: Finding,
): { start: number; end: number } | null {
  if (content.slice(finding.start, finding.end) === finding.text) {
    return { start: finding.start, end: finding.end };
  }
  const idx = content.indexOf(finding.text);
  if (idx < 0) return null;
  return { start: idx, end: idx + finding.text.length };
}

export function rangeFromOffsets(
  root: Node,
  start: number,
  end: number,
): Range | null {
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  let pos = 0;
  let startNode: Text | null = null;
  let startOffset = 0;
  let endNode: Text | null = null;
  let endOffset = 0;
  let node: Node | null;
  while ((node = walker.nextNode())) {
    const text = node as Text;
    const len = text.data.length;
    if (!startNode && pos + len >= start) {
      startNode = text;
      startOffset = start - pos;
    }
    if (pos + len >= end) {
      endNode = text;
      endOffset = end - pos;
      break;
    }
    pos += len;
  }
  if (!startNode || !endNode) return null;
  const range = document.createRange();
  try {
    range.setStart(startNode, startOffset);
    range.setEnd(endNode, endOffset);
  } catch {
    return null;
  }
  return range;
}
