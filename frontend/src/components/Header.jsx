import { RefreshCw, Calendar, Download, ExternalLink, Wifi, WifiOff } from 'lucide-react'
import { api } from '../lib/api'
import styles from './Header.module.css'

const WEEKDAY = ['Mon','Tue','Wed','Thu','Fri','Sat','Sun']

function formatAge(mins) {
  if (mins == null) return '—'
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins}m ago`
  return `${Math.floor(mins/60)}h ago`
}

export default function Header({ status, loading, onScrape, filters }) {
  const scraping = status?.scraping

  function handleDownload() {
    api.downloadIcs({ banks: filters.banks, cards: filters.cards })
  }

  function handleAddToGoogle() {
    // For local use: download the ICS and prompt user to open with Google Calendar
    const icsUrl = api.icsUrl({ banks: filters.banks, cards: filters.cards })
    const fullUrl = window.location.origin + icsUrl
    // Google Calendar 'Add by URL' (requires public URL; works locally if GCal can reach it)
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
                Scraping…
              </span>
            ) : (
              <span className={styles.fresh}>
                <span className={styles.dot} />
                {status.offer_count} offers · updated {formatAge(status.cache_age_minutes)}
              </span>
            )}
          </div>
        )}

        <div className={styles.actions}>
          <button
            className={styles.btnGhost}
            onClick={onScrape}
            disabled={scraping || loading}
            title="Re-scrape all banks now"
          >
            <RefreshCw size={15} className={scraping ? styles.spinning : undefined} />
            Refresh
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
