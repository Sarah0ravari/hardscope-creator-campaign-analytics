import React from 'react'
import { Bar } from 'react-chartjs-2'
import {
  BarElement,
  CategoryScale,
  Chart as ChartJS,
  Legend,
  LinearScale,
  Tooltip,
} from 'chart.js'

ChartJS.register(CategoryScale, LinearScale, BarElement, Tooltip, Legend)

const metricMeta = {
  total_views: { label: 'Total views', color: '#ff6b57' },
  avg_views: { label: 'Average views', color: '#0f766e' },
  engagement_rate: { label: 'Engagement rate %', color: '#1d4ed8' },
}

export default function TopChart({ data, metric }) {
  const selectedMetric = metricMeta[metric] || metricMeta.total_views
  const chartData = {
    labels: data.map((entry) => entry.name),
    datasets: [
      {
        label: selectedMetric.label,
        data: data.map((entry) => entry[metric] || 0),
        backgroundColor: selectedMetric.color,
        borderRadius: 10,
      },
    ],
  }

  const options = {
    responsive: true,
    plugins: {
      legend: { display: false },
    },
    scales: {
      x: { grid: { display: false } },
      y: { beginAtZero: true },
    },
  }

  return <Bar data={chartData} options={options} />
}
