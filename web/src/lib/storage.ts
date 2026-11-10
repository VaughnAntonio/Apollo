// localStorage can be missing or blocked (private windows, previews), so every access is guarded.
export function get(key: string, fallback: string): string {
  try {
    return localStorage.getItem(key) ?? fallback
  } catch {
    return fallback
  }
}

export function set(key: string, value: string): void {
  try {
    localStorage.setItem(key, value)
  } catch {
    // a blocked store only loses the remembered choice
  }
}
