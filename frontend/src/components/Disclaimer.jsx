import { X } from 'lucide-react'
import styles from './Disclaimer.module.css'

export default function Disclaimer({ onClose }) {
  return (
    <div className={styles.overlay} onClick={onClose}>
      <div className={styles.modal} onClick={e => e.stopPropagation()}>
        <div className={styles.header}>
          <h2 className={styles.title}>Disclaimer</h2>
          <button className={styles.closeBtn} onClick={onClose} aria-label="Close">
            <X size={18} />
          </button>
        </div>

        <div className={styles.body}>
          <section className={styles.section}>
            <h3>Informational Purpose Only</h3>
            <p>
              DealScoutLK is an independent, non-commercial tool that aggregates
              publicly available promotional offer information from Sri Lankan bank
              websites for informational purposes only. The content displayed does
              not constitute financial advice.
            </p>
          </section>

          <section className={styles.section}>
            <h3>No Affiliation</h3>
            <p>
              DealScoutLK is not affiliated with, endorsed by, sponsored by, or in
              any way officially connected with any of the banks, supermarkets, or
              other organisations whose information appears on this site, including
              but not limited to Sampath Bank, Seylan Bank, Commercial Bank of
              Ceylon, Hatton National Bank, Bank of Ceylon, DFCC Bank, Nations
              Trust Bank, People's Bank, Keells Super, Cargills Food City, Arpico
              Super Centre, Laugfs Supermarkets, Spar, and Glomark.
            </p>
          </section>

          <section className={styles.section}>
            <h3>Trademarks &amp; Intellectual Property</h3>
            <p>
              All bank names, supermarket names, logos, brand names, and trademarks
              referenced on this site are the property of their respective owners.
              Their use here is purely for identification purposes and does not
              imply any association or endorsement.
            </p>
          </section>

          <section className={styles.section}>
            <h3>Accuracy of Information</h3>
            <p>
              Offer data is scraped automatically from publicly accessible bank
              websites and may be incomplete, out of date, or subject to change
              without notice. DealScoutLK makes no representation or warranty,
              express or implied, as to the accuracy, completeness, or currency of
              any information displayed. Always verify offers directly with the
              respective bank or supermarket before making any purchase decision.
            </p>
          </section>

          <section className={styles.section}>
            <h3>Use of Public Data</h3>
            <p>
              All information collected and displayed by DealScoutLK is sourced
              exclusively from content that is publicly available on the respective
              bank websites. No private, confidential, or proprietary data is
              accessed or stored.
            </p>
          </section>

          <section className={styles.section}>
            <h3>Limitation of Liability</h3>
            <p>
              To the fullest extent permitted by applicable law, DealScoutLK and
              its creator accept no liability for any loss, damage, or inconvenience
              arising from reliance on the information provided on this site. Use of
              this service is entirely at your own risk.
            </p>
          </section>
        </div>
      </div>
    </div>
  )
}
