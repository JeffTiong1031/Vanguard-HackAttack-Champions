type RevealRect = Pick<DOMRect, 'top' | 'bottom'>;

type RevealCandidate = {
  classList: Pick<DOMTokenList, 'add'>;
  getBoundingClientRect(): RevealRect;
};

type Schedule = (callback: () => void) => void;

/**
 * IntersectionObserver only reports when intersection state changes. Preact can
 * reconcile an async result and remove observer-owned classes while the element
 * remains on screen, so observing it again does not guarantee another callback.
 * Restore the visible class on the next frame whenever a target is already in
 * the viewport.
 */
export function revealVisibleTarget(
  element: RevealCandidate,
  viewportHeight: number,
  schedule: Schedule = (callback) => { window.requestAnimationFrame(callback); },
): boolean {
  const rect = element.getBoundingClientRect();
  if (rect.bottom <= 0 || rect.top >= viewportHeight) return false;

  schedule(() => element.classList.add('reveal-in'));
  return true;
}
