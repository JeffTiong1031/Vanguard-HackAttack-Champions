import { describe, expect, it, vi } from 'vitest';
import { revealVisibleTarget } from './reveal';

function candidate(top: number, bottom: number) {
  return {
    classList: { add: vi.fn() },
    getBoundingClientRect: () => ({ top, bottom }),
  };
}

describe('revealVisibleTarget', () => {
  it('restores reveal-in when an async result is already in the viewport', () => {
    const element = candidate(406, 505);
    const schedule = (callback: () => void) => callback();

    expect(revealVisibleTarget(element, 720, schedule)).toBe(true);
    expect(element.classList.add).toHaveBeenCalledWith('reveal-in');
  });

  it('leaves offscreen targets for IntersectionObserver to reveal on scroll', () => {
    const element = candidate(721, 800);
    const schedule = vi.fn();

    expect(revealVisibleTarget(element, 720, schedule)).toBe(false);
    expect(schedule).not.toHaveBeenCalled();
    expect(element.classList.add).not.toHaveBeenCalled();
  });
});
