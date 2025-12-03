'use client'

import { motion } from 'framer-motion'

type Props = {
  data: Record<string, number>
}

const MOOD_CONFIG: Record<string, { color: string }> = {
  'Dark & Intense': { color: '#FF8000' },
  'Fun & Light': { color: '#00E054' },
  'Emotional & Deep': { color: '#40BCF4' },
  'Adventurous': { color: '#FF8000' },
  'Thought-Provoking': { color: '#00E054' },
}

export default function MoodChart({ data }: Props) {
  const sortedMoods = Object.entries(data).sort(([, a], [, b]) => b - a)
  const maxValue = Math.max(...Object.values(data), 1)

  if (sortedMoods.length === 0) {
    return (
      <div className="h-32 flex items-center justify-center text-lb-text">
        No mood data
      </div>
    )
  }

  return (
    <div className="space-y-3">
      {sortedMoods.map(([mood, value], index) => {
        const config = MOOD_CONFIG[mood] || { color: '#00E054' }
        const percentage = (value / maxValue) * 100
        
        return (
          <div key={mood}>
            <div className="flex items-center justify-between mb-1">
              <span className="text-lb-text-light text-sm">{mood}</span>
              <span className="text-lb-text text-sm font-mono">{value.toFixed(1)}%</span>
            </div>
            <div className="h-2 bg-lb-border rounded-full overflow-hidden">
              <motion.div
                initial={{ width: 0 }}
                animate={{ width: `${percentage}%` }}
                transition={{ delay: index * 0.1, duration: 0.6 }}
                className="h-full rounded-full"
                style={{ backgroundColor: config.color }}
              />
            </div>
          </div>
        )
      })}
    </div>
  )
}
