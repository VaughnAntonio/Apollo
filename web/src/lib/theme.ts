import { useState } from 'react'
import { get, set } from './storage'

export type Theme = 'light' | 'dark' | 'auto'
const THEMES: Theme[] = ['light', 'dark', 'auto']

/** Light and dark pin the theme; auto follows the system through the CSS media query. */
export function applyTheme(t: Theme): void {
  if (t === 'auto') delete document.documentElement.dataset.theme
  else document.documentElement.dataset.theme = t
}

export function storedTheme(): Theme {
  const t = get('apollo.theme', 'auto') as Theme
  return THEMES.includes(t) ? t : 'auto'
}

export function useTheme(): [Theme, (t: Theme) => void] {
  const [theme, setTheme] = useState<Theme>(storedTheme)
  const choose = (t: Theme) => {
    applyTheme(t)
    set('apollo.theme', t)
    setTheme(t)
  }
  return [theme, choose]
}
