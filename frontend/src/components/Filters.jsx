import { CreditCard, Landmark, ShoppingCart, Clock, CalendarCheck } from 'lucide-react'
import styles from './Filters.module.css'

const BANK_COLORS = {
  sampath: '#e31837', seylan: '#1a5276', combank: '#c0392b',
  ntb: '#1a3a5c', hnb: '#004b87', boc: '#006341',
  dfcc: '#00843d', peoples: '#7b2d8b',
}

const CARD_OPTIONS = [
  { value: 'both',   label: 'All Cards' },
  { value: 'credit', label: 'Credit' },
  { value: 'debit',  label: 'Debit' },
]

export default function Filters({
  banks, supermarkets,
  selectedBanks, setSelectedBanks,
  cardFilter, setCardFilter,
  smFilter, setSmFilter,
  activeToday, setActiveToday,
  activeWeek, setActiveWeek,
}) {
  function toggleBank(key) {
    setSelectedBanks(prev =>
      prev.includes(key) ? prev.filter(k => k !== key) : [...prev, key]
    )
  }

  function clearBanks() { setSelectedBanks([]) }

  return (
    <aside className={styles.sidebar}>
      {/* Quick filters */}
      <section className={styles.section}>
        <h3 className={styles.sectionTitle}>
          <Clock size={13} />
          Timing
        </h3>
        <label className={styles.toggle}>
          <input
            type="checkbox"
            checked={activeToday}
            onChange={e => setActiveToday(e.target.checked)}
          />
          <span className={styles.toggleTrack}>
            <span className={styles.toggleThumb} />
          </span>
          Active today
        </label>
        <label className={styles.toggle}>
          <input
            type="checkbox"
            checked={activeWeek}
            onChange={e => setActiveWeek(e.target.checked)}
          />
          <span className={styles.toggleTrack}>
            <span className={styles.toggleThumb} />
          </span>
          Active this week
        </label>
      </section>

      {/* Card type */}
      <section className={styles.section}>
        <h3 className={styles.sectionTitle}>
          <CreditCard size={13} />
          Card Type
        </h3>
        <div className={styles.cardBtns}>
          {CARD_OPTIONS.map(opt => (
            <button
              key={opt.value}
              className={`${styles.cardBtn} ${cardFilter === opt.value ? styles.cardBtnActive : ''}`}
              onClick={() => setCardFilter(opt.value)}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </section>

      {/* Banks */}
      <section className={styles.section}>
        <div className={styles.sectionHeader}>
          <h3 className={styles.sectionTitle}>
            <Landmark size={13} />
            Banks
          </h3>
          {selectedBanks.length > 0 && (
            <button className={styles.clearBtn} onClick={clearBanks}>Clear</button>
          )}
        </div>
        <div className={styles.bankList}>
          {banks.map(b => {
            const active = selectedBanks.includes(b.key)
            const color = BANK_COLORS[b.key] || '#888'
            return (
              <button
                key={b.key}
                className={`${styles.bankBtn} ${active ? styles.bankBtnActive : ''}`}
                onClick={() => toggleBank(b.key)}
                style={active ? { '--bank-color': color } : {}}
              >
                <span
                  className={styles.bankDot}
                  style={{ background: color }}
                />
                {b.name}
              </button>
            )
          })}
        </div>
      </section>

      {/* Supermarkets */}
      {supermarkets.length > 0 && (
        <section className={styles.section}>
          <h3 className={styles.sectionTitle}>
            <ShoppingCart size={13} />
            Supermarket
          </h3>
          <div className={styles.smList}>
            <button
              className={`${styles.smChip} ${smFilter === '' ? styles.smChipActive : ''}`}
              onClick={() => setSmFilter('')}
            >
              All
            </button>
            {supermarkets.map(sm => (
              <button
                key={sm.name}
                className={`${styles.smChip} ${smFilter === sm.name ? styles.smChipActive : ''}`}
                onClick={() => setSmFilter(smFilter === sm.name ? '' : sm.name)}
              >
                {sm.name}
                <span className={styles.smCount}>{sm.count}</span>
              </button>
            ))}
          </div>
        </section>
      )}
    </aside>
  )
}
