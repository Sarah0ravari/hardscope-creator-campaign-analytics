import React from 'react'

function formatCompact(value) {
  return new Intl.NumberFormat('en-US', { notation: 'compact', maximumFractionDigits: 1 }).format(value || 0)
}

function formatPercent(value) {
  return `${Number(value || 0).toFixed(2)}%`
}

export default function CreatorsTable({ creators }) {
  const [sortBy, setSortBy] = React.useState('total_views')
  const [direction, setDirection] = React.useState('desc')

  const sortedCreators = [...creators].sort((left, right) => {
    const leftValue = left[sortBy]
    const rightValue = right[sortBy]

    if (typeof leftValue === 'string' || typeof rightValue === 'string') {
      const sorted = String(leftValue || '').localeCompare(String(rightValue || ''))
      return direction === 'desc' ? sorted * -1 : sorted
    }

    const sorted = Number(leftValue || 0) - Number(rightValue || 0)
    return direction === 'desc' ? sorted * -1 : sorted
  })

  function toggleSort(nextSortBy) {
    if (sortBy === nextSortBy) {
      setDirection(direction === 'desc' ? 'asc' : 'desc')
      return
    }
    setSortBy(nextSortBy)
    setDirection('desc')
  }

  return (
    <div>
      <div className="panel-heading">
        <div>
          <h3>Creator watchlist</h3>
          <p>Sort by scale, efficiency, or freshness to decide who deserves the next brief.</p>
        </div>
      </div>

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th onClick={() => toggleSort('name')}>Creator</th>
              <th onClick={() => toggleSort('campaign_label')}>Campaign</th>
              <th onClick={() => toggleSort('videos')}>Videos</th>
              <th onClick={() => toggleSort('total_views')}>Total views</th>
              <th onClick={() => toggleSort('avg_views')}>Avg views</th>
              <th onClick={() => toggleSort('engagement_rate')}>Engagement</th>
              <th onClick={() => toggleSort('latest_publish_date')}>Latest upload</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {sortedCreators.length ? (
              sortedCreators.map((creator) => (
                <tr key={creator.id}>
                  <td>
                    <div className="creator-cell">
                      <strong>{creator.name}</strong>
                      <span>{creator.channel_id}</span>
                    </div>
                  </td>
                  <td>{creator.campaign_label || 'Unassigned'}</td>
                  <td>{creator.videos}</td>
                  <td>{formatCompact(creator.total_views)}</td>
                  <td>{formatCompact(creator.avg_views)}</td>
                  <td>{formatPercent(creator.engagement_rate)}</td>
                  <td>{creator.latest_publish_date ? creator.latest_publish_date.slice(0, 10) : 'No uploads'}</td>
                  <td>
                    <span className={`badge ${creator.alert_status === 'watch' ? 'badge-watch' : 'badge-healthy'}`}>
                      {creator.alert_status === 'watch' ? 'Review' : 'Healthy'}
                    </span>
                  </td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan="8" className="empty-state">
                  No creators matched the current filter set.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
