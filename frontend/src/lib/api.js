const BASE = import.meta.env.VITE_API_BASE ?? '/api'

async function get(path) {
  const res = await fetch(BASE + path)
  if (!res.ok) throw new Error(`API ${path} → ${res.status}`)
  return res.json()
}

export const api = {
  status: () => get('/status'),
  banks: () => get('/banks'),
  supermarkets: () => get('/supermarkets'),

  offers: (filters = {}) => {
    const p = new URLSearchParams()
    if (filters.banks?.length)   p.set('banks', filters.banks.join(','))
    if (filters.cards)           p.set('cards', filters.cards)
    if (filters.supermarket)     p.set('supermarket', filters.supermarket)
    if (filters.activeToday)     p.set('active_today', 'true')
    if (filters.activeWeek)      p.set('active_week', 'true')
    return get('/offers?' + p.toString())
  },

  triggerScrape: (banks = []) => {
    const p = banks.length ? `?banks=${banks.join(',')}` : ''
    return fetch(BASE + '/scrape' + p, { method: 'POST' }).then(r => r.json())
  },

  icsUrl: (filters = {}) => {
    const p = new URLSearchParams()
    if (filters.banks?.length) p.set('banks', filters.banks.join(','))
    if (filters.cards)         p.set('cards', filters.cards)
    return BASE + '/ics?' + p.toString()
  },

  downloadIcs: async (filters = {}) => {
    const url = api.icsUrl(filters)
    const res = await fetch(url)
    const blob = await res.blob()
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob)
    a.download = 'lk_bank_offers.ics'
    a.click()
  },
}
