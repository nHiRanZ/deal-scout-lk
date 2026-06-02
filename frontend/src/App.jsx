import { useState } from 'react'
import { LayoutGrid, Table2, CalendarDays, Loader2 } from 'lucide-react'
import { useOffers } from './hooks/useOffers'
import { api } from './lib/api'
import Header from './components/Header'
import Filters from './components/Filters'
import OfferCard from './components/OfferCard'
import BankCompare from './components/BankCompare'
import CalendarView from './components/CalendarView'
import styles from './App.module.css'

const VIEWS = [
  { id: 'cards',    label: 'Cards',    Icon: LayoutGrid },
  { id: 'calendar', label: 'Calendar', Icon: CalendarDays },
  { id: 'compare',  label: 'Compare',  Icon: Table2 },
]

export default function App() {
  const [view, setView] = useState('cards')

  const {
    offers, status, banks, supermarkets,
    loading, error,
    selectedBanks, setSelectedBanks,
    cardFilter, setCardFilter,
    smFilter, setSmFilter,
    activeToday, setActiveToday,
    activeWeek, setActiveWeek,
    triggerScrape,
  } = useOffers()

  const headerFilters = {
    banks: selectedBanks,
    cards: cardFilter !== 'both' ? cardFilter : undefined,
  }

  return (
    <div className={styles.app}>
      <Header
        status={status}
        loading={loading}
        onScrape={triggerScrape}
        filters={headerFilters}
      />

      <div className={styles.shell}>
        <Filters
          banks={banks}
          supermarkets={supermarkets}
          selectedBanks={selectedBanks} setSelectedBanks={setSelectedBanks}
          cardFilter={cardFilter} setCardFilter={setCardFilter}
          smFilter={smFilter} setSmFilter={setSmFilter}
          activeToday={activeToday} setActiveToday={setActiveToday}
          activeWeek={activeWeek} setActiveWeek={setActiveWeek}
        />

        <main className={styles.main}>
          {/* View switcher */}
          <div className={styles.toolbar}>
            <div className={styles.viewTabs}>
              {VIEWS.map(({ id, label, Icon }) => (
                <button
                  key={id}
                  className={`${styles.viewTab} ${view === id ? styles.viewTabActive : ''}`}
                  onClick={() => setView(id)}
                >
                  <Icon size={14} />
                  {label}
                </button>
              ))}
            </div>
            <span className={styles.offerCount}>
              {loading && status?.scraping
                ? 'Scraping…'
                : `${offers.length} offer${offers.length !== 1 ? 's' : ''}`}
            </span>
          </div>

          {/* Content */}
          {loading && !offers.length ? (
            <div className={styles.loadState}>
              <Loader2 size={32} className={styles.spinner} />
              <p>
                {status?.scraping
                  ? 'Scraping bank websites… this takes about 30–60 seconds.'
                  : 'Loading offers…'}
              </p>
              {status?.scraping && (
                <p className={styles.hint}>Grab a coffee ☕ — we're visiting 8 bank websites.</p>
              )}
            </div>
          ) : error ? (
            <div className={styles.errorState}>
              <p>⚠️ Could not reach the backend.</p>
              <p className={styles.hint}>
                Make sure the FastAPI server is running:<br />
                <code>cd backend && python main.py</code>
              </p>
            </div>
          ) : view === 'cards' ? (
            <CardGrid offers={offers} status={status} />
          ) : view === 'calendar' ? (
            <CalendarView offers={offers} />
          ) : (
            <BankCompare offers={offers} banks={banks} />
          )}
        </main>
      </div>
    </div>
  )
}

function CardGrid({ offers, status }) {
  if (!offers.length) {
    return (
      <div className={styles.emptyState}>
        {status?.scraping ? (
          <>
            <Loader2 size={28} className={styles.spinner} />
            <p>Scraping in progress…</p>
          </>
        ) : (
          <>
            <p>No offers match your filters.</p>
            <p className={styles.hint}>Try adjusting the bank or card type filters.</p>
          </>
        )}
      </div>
    )
  }

  // Group by supermarket
  const bySuper = {}
  for (const o of offers) {
    if (!bySuper[o.supermarket]) bySuper[o.supermarket] = []
    bySuper[o.supermarket].push(o)
  }

  return (
    <div className={styles.cardGrid}>
      {offers.map((o, i) => (
        <OfferCard
          key={o.id + i}
          offer={o}
          style={{ animationDelay: `${Math.min(i * 0.04, 0.6)}s` }}
        />
      ))}
    </div>
  )
}
