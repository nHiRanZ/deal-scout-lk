import { RefreshCw, Calendar, Download, Sun, Moon } from 'lucide-react'
import { api } from '../lib/api'
import { useTheme } from '../hooks/useTheme'
import styles from './Header.module.css'

function formatLastSynced(isoStr) {
  if (!isoStr) return '—'
  const d = new Date(isoStr)
  const now = new Date()
  const isToday = d.toDateString() === now.toDateString()
  const time = d.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit', hour12: true })
  if (isToday) return `Today at ${time}`
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }) + ' at ' + time
}

export default function Header({ status, filters }) {
  const scraping = status?.scraping
  const { theme, toggle } = useTheme()

  function handleDownload() {
    api.downloadIcs({ banks: filters.banks, cards: filters.cards })
  }

  function handleAddToGoogle() {
    const icsUrl = api.icsUrl({ banks: filters.banks, cards: filters.cards })
    const fullUrl = window.location.origin + icsUrl
    const gcUrl = `https://calendar.google.com/calendar/r/settings/addbyurl?url=${encodeURIComponent(fullUrl)}`
    window.open(gcUrl, '_blank')
  }

  return (
    <header className={styles.header}>
      <div className={styles.brand}>
        <span className={styles.logo}>🛒</span>
        <div>
          <h1 className={styles.title}>LK Deals</h1>
          <p className={styles.subtitle}>Sri Lanka Bank Supermarket Offers</p>
        </div>
      </div>

      <div className={styles.meta}>
        {status && (
          <div className={styles.status}>
            {scraping ? (
              <span className={styles.scraping}>
                <RefreshCw size={13} className={styles.spinning} />
                Syncing…
              </span>
            ) : (
              <span className={styles.fresh}>
                <span className={styles.dot} />
                {status.offer_count} offers · synced {formatLastSynced(status.last_scraped)}
              </span>
            )}
          </div>
        )}

        <div className={styles.actions}>
          <button
            className={styles.btnTheme}
            onClick={toggle}
            title={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
          >
            {theme === 'dark' ? <Sun size={15} /> : <Moon size={15} />}
          </button>

          <button className={styles.btnOutline} onClick={handleDownload} title="Download ICS file">
            <Download size={15} />
            Download .ics
          </button>

          <button className={styles.btnAccent} onClick={handleAddToGoogle} title="Add to Google Calendar">
            <Calendar size={15} />
            Add to Google Cal
          </button>
        </div>
      </div>
    </header>
  )
}
