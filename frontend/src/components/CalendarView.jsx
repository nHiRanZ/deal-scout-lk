import { useState } from 'react'
import { ChevronLeft, ChevronRight } from 'lucide-react'
import OfferCard from './OfferCard'
import styles from './CalendarView.module.css'

const WEEKDAYS = ['Mon','Tue','Wed','Thu','Fri','Sat','Sun']
const MONTHS = ['January','February','March','April','May','June',
                'July','August','September','October','November','December']

function getOffersForDate(offers, d) {
  return offers.filter(o => {
    const from = o.valid_from ? new Date(o.valid_from + 'T00:00:00') : null
    const to   = o.valid_to   ? new Date(o.valid_to   + 'T00:00:00') : null
    const inRange = (!from || d >= from) && (!to || d <= to)
    if (!inRange) return false
    if (o.days_of_week.length === 0) return true
    // JS getDay: 0=Sun, 1=Mon... convert to Mon=0
    const jsDay = d.getDay()
    const isoDay = jsDay === 0 ? 6 : jsDay - 1
    return o.days_of_week.includes(isoDay)
  })
}

export default function CalendarView({ offers }) {
  const today = new Date()
  today.setHours(0, 0, 0, 0)

  const [year, setYear] = useState(today.getFullYear())
  const [month, setMonth] = useState(today.getMonth())
  const [selectedDate, setSelectedDate] = useState(today)

  function prevMonth() {
    if (month === 0) { setMonth(11); setYear(y => y - 1) }
    else setMonth(m => m - 1)
  }
  function nextMonth() {
    if (month === 11) { setMonth(0); setYear(y => y + 1) }
    else setMonth(m => m + 1)
  }

  // Build calendar grid (Mon-start)
  const firstDay = new Date(year, month, 1)
  const lastDay  = new Date(year, month + 1, 0)

  // Day of week for first cell (Mon=0)
  let startDow = firstDay.getDay() - 1
  if (startDow < 0) startDow = 6

  const cells = []
  for (let i = 0; i < startDow; i++) cells.push(null)
  for (let d = 1; d <= lastDay.getDate(); d++) {
    cells.push(new Date(year, month, d))
  }

  const selectedOffers = selectedDate ? getOffersForDate(offers, selectedDate) : []

  return (
    <div className={styles.container}>
      <div className={styles.calWrap}>
        {/* Nav */}
        <div className={styles.nav}>
          <button className={styles.navBtn} onClick={prevMonth}><ChevronLeft size={16}/></button>
          <span className={styles.monthLabel}>{MONTHS[month]} {year}</span>
          <button className={styles.navBtn} onClick={nextMonth}><ChevronRight size={16}/></button>
        </div>

        {/* Weekday headers */}
        <div className={styles.grid}>
          {WEEKDAYS.map(d => (
            <div key={d} className={styles.weekday}>{d}</div>
          ))}

          {cells.map((d, i) => {
            if (!d) return <div key={`e-${i}`} />

            const dayOffers = getOffersForDate(offers, d)
            const isToday = d.getTime() === today.getTime()
            const isSelected = selectedDate && d.getTime() === selectedDate.getTime()
            const hasOffers = dayOffers.length > 0

            return (
              <button
                key={d.toISOString()}
                className={`${styles.cell}
                  ${isToday ? styles.today : ''}
                  ${isSelected ? styles.selected : ''}
                  ${hasOffers ? styles.hasOffers : styles.empty}
                `}
                onClick={() => setSelectedDate(d)}
              >
                <span className={styles.dayNum}>{d.getDate()}</span>
                {hasOffers && (
                  <span className={styles.dot}>
                    {dayOffers.length > 9 ? '9+' : dayOffers.length}
                  </span>
                )}
              </button>
            )
          })}
        </div>
      </div>

      {/* Offer list for selected date */}
      <div className={styles.offerPanel}>
        <div className={styles.panelHeader}>
          {selectedDate && (
            <h3 className={styles.panelTitle}>
              {selectedDate.toLocaleDateString('en-LK', { weekday: 'long', day: 'numeric', month: 'long' })}
              <span className={styles.panelCount}>{selectedOffers.length} offer{selectedOffers.length !== 1 ? 's' : ''}</span>
            </h3>
          )}
        </div>
        <div className={styles.panelList}>
          {selectedOffers.length === 0 ? (
            <div className={styles.panelEmpty}>No offers on this day.</div>
          ) : (
            selectedOffers.map((o, i) => (
              <OfferCard key={o.id + i} offer={o} style={{ animationDelay: `${i * 0.04}s` }} />
            ))
          )}
        </div>
      </div>
    </div>
  )
}
