import React, { useEffect, useMemo, useState } from 'react'
import CreatorsTable from './components/CreatorsTable'
import TopChart from './components/TopChart'
import TrendChart from './components/TrendChart'

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

function formatCompact(value) {
  return new Intl.NumberFormat('en-US', { notation: 'compact', maximumFractionDigits: 1 }).format(value || 0)
}

function formatPercent(value) {
  return `${Number(value || 0).toFixed(2)}%`
}

export default function App() {
  const [creators, setCreators] = useState([])
  const [overview, setOverview] = useState({ summary: {}, platform_breakdown: {}, trend: [] })
  const [top, setTop] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [metric, setMetric] = useState('total_views')

  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')
  const [minViews, setMinViews] = useState(0)
  const [minEngagement, setMinEngagement] = useState(0)

  useEffect(() => {
    const controller = new AbortController()
    const query = new URLSearchParams({ platform: 'youtube' })
    if (startDate) query.set('start_date', startDate)
    if (endDate) query.set('end_date', endDate)
    if (minViews) query.set('min_views', String(minViews))
    if (minEngagement) query.set('min_engagement', String(minEngagement))

    async function loadDashboard() {
      try {
        setLoading(true)
        setError('')
        const [creatorsResponse, overviewResponse, topResponse] = await Promise.all([
          fetch(`${API_BASE}/creators?${query.toString()}`, { signal: controller.signal }),
          fetch(`${API_BASE}/analytics/overview?${query.toString()}`, { signal: controller.signal }),
          fetch(`${API_BASE}/analytics/top?platform=youtube&metric=${metric}&limit=8`, { signal: controller.signal }),
        ])

        if (!creatorsResponse.ok || !overviewResponse.ok || !topResponse.ok) {
          throw new Error('Dashboard data could not be loaded.')
        }

        const [creatorsJson, overviewJson, topJson] = await Promise.all([
          creatorsResponse.json(),
          overviewResponse.json(),
          topResponse.json(),
        ])

        setCreators(creatorsJson)
        setOverview(overviewJson)
        setTop(topJson)
      } catch (loadError) {
        if (loadError.name !== 'AbortError') {
          setError(loadError.message)
          setCreators([])
          setOverview({ summary: {}, platform_breakdown: {}, trend: [] })
          setTop([])
        }
      } finally {
        if (!controller.signal.aborted) {
          setLoading(false)
        }
      }
    }

    loadDashboard()
    return () => controller.abort()
  }, [startDate, endDate, minViews, minEngagement, metric])

  const summaryCards = useMemo(() => {
    const summary = overview.summary || {}
    return [
      { label: 'Tracked creators', value: summary.total_creators ?? 0, hint: 'Eligible for partner outreach' },
      { label: 'Video views', value: formatCompact(summary.total_views ?? 0), hint: 'Total reachable impressions' },
      { label: 'Avg engagement', value: formatPercent(summary.avg_engagement_rate ?? 0), hint: 'Likes + comments / views' },
      { label: 'Watchlist', value: summary.at_risk_creators ?? 0, hint: 'Low-engagement creators to review' },
    ]
  }, [overview])

  const topCreator = overview.summary?.top_creator
  const platformMeta = overview.platform_breakdown || {}

  return (
    <div className="page-shell">
      <div className="page-backdrop" />
      <div className="container">
        <header className="hero">
          <div>
            <p className="eyebrow">HardScope creator analytics</p>
            <h1>See which creators are driving reach, engagement, and partnership momentum.</h1>
            <p className="hero-copy">
              Built around real YouTube performance data so a brand partnerships team can quickly spot breakout
              channels, underperformers, and recent trend shifts.
            </p>
          </div>
          <div className="hero-note">
            <span className="hero-note-label">Current source</span>
            <strong>YouTube Data API v3</strong>
            <span>Platform tracked: {platformMeta.platform || 'youtube'}</span>
            <span>Creators tagged to campaigns: {platformMeta.campaign_tagged_creators || 0}</span>
            <span>Last ingest: {platformMeta.last_ingested_at || 'Not ingested yet'}</span>
          </div>
        </header>

        <section className="filters-card">
          <div className="filters-heading">
            <div>
              <h2>Filters</h2>
              <p>Trim the dataset to the creators you would actually consider for a live campaign brief.</p>
            </div>
            {topCreator ? (
              <div className="spotlight">
                <span>Top creator right now</span>
                <strong>{topCreator.name}</strong>
                <small>
                  {formatCompact(topCreator.total_views)} views at {formatPercent(topCreator.engagement_rate)}
                </small>
              </div>
            ) : null}
          </div>

          <div className="filters-grid">
            <label>
              <span>Start date</span>
              <input type="date" value={startDate} onChange={(event) => setStartDate(event.target.value)} />
            </label>
            <label>
              <span>End date</span>
              <input type="date" value={endDate} onChange={(event) => setEndDate(event.target.value)} />
            </label>
            <label>
              <span>Minimum views</span>
              <input
                type="number"
                min="0"
                value={minViews}
                onChange={(event) => setMinViews(Number(event.target.value) || 0)}
              />
            </label>
            <label>
              <span>Minimum engagement %</span>
              <input
                type="number"
                min="0"
                step="0.1"
                value={minEngagement}
                onChange={(event) => setMinEngagement(Number(event.target.value) || 0)}
              />
            </label>
          </div>
        </section>

        <section className="stats-grid">
          {summaryCards.map((card) => (
            <article className="stat-card" key={card.label}>
              <span>{card.label}</span>
              <strong>{card.value}</strong>
              <small>{card.hint}</small>
            </article>
          ))}
        </section>

        {error ? <div className="status-banner error">{error}</div> : null}
        {loading ? <div className="status-banner">Refreshing analytics...</div> : null}

        <main className="dashboard-grid">
          <section className="panel">
            <div className="panel-heading">
              <div>
                <h3>Top performers</h3>
                <p>Compare creators by raw reach or efficiency.</p>
              </div>
              <label className="inline-control">
                <span>Metric</span>
                <select value={metric} onChange={(event) => setMetric(event.target.value)}>
                  <option value="total_views">Total views</option>
                  <option value="avg_views">Avg views</option>
                  <option value="engagement_rate">Engagement rate</option>
                </select>
              </label>
            </div>
            <TopChart data={top} metric={metric} />
          </section>

          <section className="panel">
            <div className="panel-heading">
              <div>
                <h3>Trend over time</h3>
                <p>Watch reach and engagement shift month to month.</p>
              </div>
            </div>
            <TrendChart data={overview.trend || []} />
          </section>

          <section className="panel full-width">
            <CreatorsTable creators={creators} />
          </section>
        </main>
      </div>
    </div>
  )
}
