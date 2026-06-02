import { useState, useEffect, useCallback, useRef } from 'react'
import { api } from '../lib/api'

export function useOffers() {
  const [offers, setOffers] = useState([])
  const [status, setStatus] = useState(null)
  const [banks, setBanks] = useState([])
  const [supermarkets, setSupermarkets] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  // Filters
  const [selectedBanks, setSelectedBanks] = useState([])   // [] = all
  const [cardFilter, setCardFilter] = useState('both')      // credit|debit|both
  const [smFilter, setSmFilter] = useState('')
  const [activeToday, setActiveToday] = useState(false)
  const [activeWeek, setActiveWeek] = useState(false)

  const pollRef = useRef(null)

  const fetchStatus = useCallback(async () => {
    try {
      const s = await api.status()
      setStatus(s)
      return s
    } catch { return null }
  }, [])

  const fetchOffers = useCallback(async () => {
    try {
      const [{ offers }, { banks }, { supermarkets }] = await Promise.all([
        api.offers({ banks: selectedBanks, cards: cardFilter, supermarket: smFilter, activeToday, activeWeek }),
        api.banks(),
        api.supermarkets(),
      ])
      setOffers(offers)
      setBanks(banks)
      setSupermarkets(supermarkets)
      setError(null)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [selectedBanks, cardFilter, smFilter, activeToday, activeWeek])

  // Poll while scraping
  const startPoll = useCallback(() => {
    if (pollRef.current) return
    pollRef.current = setInterval(async () => {
      const s = await fetchStatus()
      if (s && !s.scraping) {
        clearInterval(pollRef.current)
        pollRef.current = null
        fetchOffers()
      }
    }, 2500)
  }, [fetchStatus, fetchOffers])

  // Initial load
  useEffect(() => {
    fetchStatus().then(s => {
      if (s?.scraping) startPoll()
    })
    fetchOffers()
    return () => { if (pollRef.current) clearInterval(pollRef.current) }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // Re-fetch when filters change
  useEffect(() => {
    fetchOffers()
  }, [fetchOffers])

  return {
    offers, status, banks, supermarkets,
    loading, error,
    selectedBanks, setSelectedBanks,
    cardFilter, setCardFilter,
    smFilter, setSmFilter,
    activeToday, setActiveToday,
    activeWeek, setActiveWeek,
    fetchOffers,
  }
}
