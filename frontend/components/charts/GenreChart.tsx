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

const COLORS = ['#00E054', '#40BCF4', '#FF8000', '#00E054', '#40BCF4', '#FF8000', '#00E054', '#40BCF4']

export default function GenreChart({ data }: Props) {
  const chartData = Object.entries(data)
    .slice(0, 8)
    .map(([name, value]) => ({
      name: name.length > 12 ? name.slice(0, 12) + '…' : name,
      fullName: name,
      value,
    }))

  if (chartData.length === 0) {
    return (
      <div className="h-56 flex items-center justify-center text-lb-text">
        No genre data
      </div>
    )
  }

  return (
    <div className="h-56">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart
          data={chartData}
          layout="vertical"
          margin={{ top: 0, right: 20, left: 0, bottom: 0 }}
        >
          <XAxis
            type="number"
            axisLine={false}
            tickLine={false}
            tick={{ fill: '#99AABB', fontSize: 11 }}
          />
          <YAxis
            type="category"
            dataKey="name"
            axisLine={false}
            tickLine={false}
            tick={{ fill: '#D8E0E8', fontSize: 12 }}
            width={90}
          />
          <Tooltip
            content={({ active, payload }) => {
              if (active && payload && payload.length) {
                const item = payload[0].payload
                return (
                  <div className="bg-lb-card border border-lb-border rounded-lg px-3 py-2 shadow-lg">
                    <p className="text-lb-white text-sm font-medium">{item.fullName}</p>
                    <p className="text-lb-green text-sm">{item.value} films</p>
                  </div>
                )
              }
              return null
            }}
          />
          <Bar dataKey="value" radius={[0, 4, 4, 0]}>
            {chartData.map((_, index) => (
              <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} fillOpacity={0.8} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
