export type SurfaceAdapter = {
  host: string;
  getComposer(path?: EventTarget[]): HTMLElement | null;
  readText(path?: EventTarget[]): string | null;
  writeText(text: string, target?: HTMLElement | null): void;
  isSendControl(path: EventTarget[]): boolean;
  onPaste(cb: (text: string) => void): void;
  /** Every file input the surface uses. Re-queried each call: the provider
   *  re-mounts these on navigation (D4). */
  fileInputs(): HTMLInputElement[];
};
