// Every map colour comes from the design tokens, read once when it is needed.
export function token(name: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}