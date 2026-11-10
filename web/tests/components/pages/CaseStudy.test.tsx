import { render, screen, within } from '@testing-library/react'
import { expect, it } from 'vitest'
import { CaseStudy, REPORT_URL, caseStats } from '../../../src/components/pages/CaseStudy'
import { entry } from '../../fixtures'
import { mockApi } from '../../helpers'

const imported = (id: number, r: number, stage: 'eval' | 'funded', day: string) =>
  entry({ id, source: 'imported', scaled: true, side: null, r, 'pnl_$': r * 100, stage, opened_at: `${day}T14:30:00Z` })

const ROWS = [
  imported(1, 1, 'eval', '2025-07-10'),
  imported(2, -1, 'eval', '2025-07-10'),
  imported(3, 2, 'funded', '2025-08-01'),
  entry({ id: 9, source: 'manual', r: -5, stage: 'funded' }),
]

it('pairs all seven case-study questions with an Apollo feature', async () => {
  mockApi({ '/journal': ROWS })
  render(<CaseStudy />)
  const table = await screen.findByRole('table', { name: 'Questions' })
  const rows = within(table).getAllByRole('row').slice(1)
  expect(rows.map((r) => r.textContent?.slice(0, 2))).toEqual(['Q1', 'Q2', 'Q3', 'Q4', 'Q5', 'Q6', 'Q7'])
})

it('links to the R report', async () => {
  mockApi({ '/journal': ROWS })
  render(<CaseStudy />)
  const link = await screen.findByRole('link', { name: /full report/i })
  expect(link.getAttribute('href')).toBe('https://vaughnantonio.github.io/mnq-trading-case-study/analysis/report.html')
  expect(REPORT_URL).toBe(link.getAttribute('href'))
})

it('counts only the imported rows', async () => {
  mockApi({ '/journal': ROWS })
  render(<CaseStudy />)
  expect(await screen.findByText('3 trades')).toBeTruthy()
  const s = caseStats(ROWS)
  expect(s.n).toBe(3)
  expect(s.byStage).toEqual([
    { stage: 'eval', n: 2, win_rate: 0.5, mean_r: 0 },
    { stage: 'funded', n: 1, win_rate: 1, mean_r: 2 },
  ])
  expect(s.worst).toEqual({ date: '2025-07-10', n: 2, r: 0, 'pnl_$': 0 })
})

it('says how to import when the journal has no case-study rows', async () => {
  mockApi({ '/journal': [entry({ source: 'manual' })] })
  render(<CaseStudy />)
  expect(await screen.findByText(/Import the case study with python -m apollo.journal.importer/)).toBeTruthy()
})
