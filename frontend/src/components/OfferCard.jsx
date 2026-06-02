import { ExternalLink, Calendar, Clock } from 'lucide-react'
import styles from './OfferCard.module.css'

const BANK_COLORS = {
  sampath: '#e31837', seylan: '#1a5276', combank: '#c0392b',
  ntb: '#1a3a5c', hnb: '#004b87', boc: '#006341',
  dfcc: '#00843d', peoples: '#7b2d8b',
}

const WEEKDAYS = ['Mon','Tue','Wed','Thu','Fri','Sat','Sun']

const CARD_ICONS = {
  'Credit': '💳',
  'Debit': '🏧',
  'Credit / Debit': '💳',
}

function formatDate(iso) {
  if (!iso) return null
  const d = new Date(iso + 'T00:00:00')
  return d.toLocaleDateString('en-LK', { day: 'numeric', month: 'short', year: 'numeric' })
}

export default function OfferCard({ offer, style }) {
  const bankColor = BANK_COLORS[offer.bank_key] || '#888'
  const isCredit = offer.card_type.includes('Credit')
  const isDebit = offer.card_type.includes('Debit')

  const urgency = offer.days_remaining != null
    ? offer.days_remaining <= 3 ? 'critical'
    : offer.days_remaining <= 7 ? 'soon'
    : null
    : null

  return (
    <article className={styles.card} style={style}>
      {/* Bank stripe */}
      <div className={styles.stripe} style={{ background: bankColor }} />

      <div className={styles.body}>
        {/* Top row */}
        <div className={styles.topRow}>
          <div className={styles.bankTag} style={{ color: bankColor }}>
            {offer.bank}
          </div>
          <div className={styles.badges}>
            {isCredit && <span className={styles.badge}>Credit</span>}
            {isDebit && <span className={`${styles.badge} ${styles.badgeDebit}`}>Debit</span>}
          </div>
        </div>

        {/* Supermarket + offer */}
        <div className={styles.supermarket}>{offer.supermarket}</div>
        <div className={styles.offerText}>{offer.offer_text}</div>

        {/* Days of week */}
        {offer.days_of_week.length > 0 && (
          <div className={styles.days}>
            {WEEKDAYS.map((d, i) => (
              <span
                key={d}
                className={`${styles.day} ${offer.days_of_week.includes(i) ? styles.dayActive : ''}`}
              >
                {d}
              </span>
            ))}
          </div>
        )}

        {/* Validity */}
        <div className={styles.footer}>
          <div className={styles.validity}>
            {offer.valid_from && <span>{formatDate(offer.valid_from)}</span>}
            {offer.valid_from && offer.valid_to && <span className={styles.arrow}>→</span>}
            {offer.valid_to && <span>{formatDate(offer.valid_to)}</span>}
            {!offer.valid_from && !offer.valid_to && (
              <span className={styles.noDate}>No dates specified</span>
            )}
          </div>

          <div className={styles.footerRight}>
            {offer.days_remaining != null && (
              <span className={`${styles.daysLeft} ${urgency === 'critical' ? styles.critical : urgency === 'soon' ? styles.soon : ''}`}>
                {offer.days_remaining === 0 ? 'Ends today' : `${offer.days_remaining}d left`}
              </span>
            )}
            {offer.is_active_today && (
              <span className={styles.activeToday}>● Today</span>
            )}
            <a href={offer.source_url} target="_blank" rel="noopener noreferrer" className={styles.srcLink}>
              <ExternalLink size={11} />
            </a>
          </div>
        </div>
      </div>
    </article>
  )
}
