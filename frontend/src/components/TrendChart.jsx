import React from 'react'
import { Line } from 'react-chartjs-2'
import {
  CategoryScale,
  Chart as ChartJS,
  Legend,
  LineElement,
  LinearScale,
  PointElement,
  Tooltip,
} from 'chart.js'

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Tooltip, Legend)

export default function TrendChart({ data }) {
  const chartData = {
    labels: data.map((entry) => entry.month),
    datasets: [
      {
        label: 'Total views',
        data: data.map((entry) => entry.total_views),
        borderColor: '#111827',
        backgroundColor: 'rgba(17, 24, 39, 0.08)',
        tension: 0.35,
        yAxisID: 'y',
      },
      {
        label: 'Engagement rate %',
        data: data.map((entry) => entry.engagement_rate),
        borderColor: '#f59e0b',
        backgroundColor: 'rgba(245, 158, 11, 0.12)',
        tension: 0.35,
        yAxisID: 'y1',
      },
    ],
  }

  const options = {
    responsive: true,
    interaction: {
      mode: 'index',
      intersect: false,
    },
    scales: {
      y: {
        beginAtZero: true,
        position: 'left',
      },
      y1: {
        beginAtZero: true,
        position: 'right',
        grid: { drawOnChartArea: false },
      },
    },
  }

  return <Line data={chartData} options={options} />
}
