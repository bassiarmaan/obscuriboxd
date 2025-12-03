'use client'

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from 'recharts'

type Props = {
  data: Record<string, number>
}

const COLORS = ['#FF8000', '#00E054', '#40BCF4', '#FF8000', '#00E054', '#40BCF4', '#FF8000', '#00E054']

export default function DecadeChart({ data }: Props) {
  const chartData = Object.entries(data)
    .sort(([a], [b]) => {
      const decadeA = parseInt(a.replace('s', ''))
      const decadeB = parseInt(b.replace('s', ''))
      return decadeA - decadeB
    })
    .map(([name, value]) => ({ name, value }))

  if (chartData.length === 0) {
    return (
      <div className="h-56 flex items-center justify-center text-lb-text">
        No decade data
      </div>
    )
  }

  return (
    <div className="h-56">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={chartData} margin={{ top: 10, right: 20, left: 0, bottom: 0 }}>
          <XAxis
            dataKey="name"
            axisLine={false}
            tickLine={false}
            tick={{ fill: '#99AABB', fontSize: 11 }}
          />
          <YAxis
            axisLine={false}
            tickLine={false}
            tick={{ fill: '#99AABB', fontSize: 11 }}
          />
          <Tooltip
            content={({ active, payload }) => {
              if (active && payload && payload.length) {
                const item = payload[0].payload
                return (
                  <div className="bg-lb-card border border-lb-border rounded-lg px-3 py-2 shadow-lg">
                    <p className="text-lb-white text-sm font-medium">{item.name}</p>
                    <p className="text-lb-green text-sm">{item.value} films</p>
                  </div>
                )
              }
              return null
            }}
          />
          <Bar dataKey="value" radius={[4, 4, 0, 0]}>
            {chartData.map((_, index) => (
              <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} fillOpacity={0.8} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
