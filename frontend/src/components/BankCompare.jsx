import styles from './BankCompare.module.css'

const BANK_COLORS = {
  sampath: '#e31837', seylan: '#1a5276', combank: '#c0392b',
  ntb: '#1a3a5c', hnb: '#004b87', boc: '#006341',
  dfcc: '#00843d', peoples: '#7b2d8b',
}

const SUPERMARKETS_ORDER = [
  'Keells', 'Cargills Food City', 'Arpico', 'Laugfs',
  'Spar', 'Softlogic Glomark', 'Nawaloka', 'Supermarket',
]

export default function BankCompare({ offers, banks }) {
  if (!offers.length) return (
    <div className={styles.empty}>No offers to compare yet.</div>
  )

  // Build matrix: supermarket → bank → [offers]
  const sms = [...new Set(offers.map(o => o.supermarket))].sort((a, b) => {
    const ai = SUPERMARKETS_ORDER.indexOf(a)
    const bi = SUPERMARKETS_ORDER.indexOf(b)
    return (ai === -1 ? 999 : ai) - (bi === -1 ? 999 : bi)
  })

  const activeBankKeys = [...new Set(offers.map(o => o.bank_key))]
  const activeBanks = banks.filter(b => activeBankKeys.includes(b.key))

  const matrix = {}
  for (const sm of sms) {
    matrix[sm] = {}
    for (const b of activeBanks) {
      matrix[sm][b.key] = offers.filter(
        o => o.supermarket === sm && o.bank_key === b.key
      )
    }
  }

  return (
    <div className={styles.wrapper}>
      <div className={styles.scrollWrap}>
        <table className={styles.table}>
          <thead>
            <tr>
              <th className={styles.cornerCell}>Supermarket</th>
              {activeBanks.map(b => (
                <th key={b.key} className={styles.bankHeader}>
                  <span
                    className={styles.bankDot}
                    style={{ background: BANK_COLORS[b.key] || '#888' }}
                  />
                  {b.name}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {sms.map(sm => (
              <tr key={sm} className={styles.row}>
                <td className={styles.smCell}>{sm}</td>
                {activeBanks.map(b => {
                  const cell = matrix[sm][b.key]
                  const bankColor = BANK_COLORS[b.key] || '#888'
                  return (
                    <td key={b.key} className={styles.cell}>
                      {cell && cell.length > 0 ? (
                        <div className={styles.cellOffers}>
                          {cell.map(o => (
                            <a
                              key={o.id}
                              href={o.source_url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className={styles.cellOffer}
                              style={{ borderColor: bankColor + '40' }}
                            >
                              <span
                                className={styles.offerText}
                                style={{ color: bankColor }}
                              >
                                {o.offer_text}
                              </span>
                              <span className={`${styles.cardBadge} ${o.card_type === 'Debit' ? styles.debit : ''}`}>
                                {o.card_type}
                              </span>
                              {o.is_active_today && (
                                <span className={styles.todayDot} title="Active today">●</span>
                              )}
                            </a>
                          ))}
                        </div>
                      ) : (
                        <span className={styles.none}>—</span>
                      )}
                    </td>
                  )
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
