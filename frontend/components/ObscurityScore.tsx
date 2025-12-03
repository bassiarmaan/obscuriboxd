'use client'

import { motion } from 'framer-motion'
import { useEffect, useState } from 'react'

type Props = {
  score: number
  username: string
}

function getScoreLabel(score: number): { label: string; description: string } {
  if (score >= 90) {
    return {
      label: 'Cinema Archaeologist',
      description: "You dig up films most people have never heard of.",
    }
  }
  if (score >= 75) {
    return {
      label: 'Arthouse Devotee',
      description: 'Your taste ventures far beyond the mainstream.',
    }
  }
  if (score >= 60) {
    return {
      label: 'Cinephile Explorer',
      description: "You balance popular films with deeper cuts.",
    }
  }
  if (score >= 45) {
    return {
      label: 'Eclectic Viewer',
      description: 'A healthy mix of popular and lesser-known films.',
    }
  }
  if (score >= 30) {
    return {
      label: 'Crowd Favorite',
      description: 'You enjoy what most people enjoy.',
    }
  }
  return {
    label: 'Blockbuster Fan',
    description: "You know what you like—and it's usually popular.",
  }
}

export default function ObscurityScore({ score, username }: Props) {
  const [displayScore, setDisplayScore] = useState(0)
  const { label, description } = getScoreLabel(score)

  useEffect(() => {
    const duration = 1500
    const steps = 60
    const stepValue = score / steps
    let current = 0

    const interval = setInterval(() => {
      current += stepValue
      if (current >= score) {
        setDisplayScore(score)
        clearInterval(interval)
      } else {
        setDisplayScore(Math.round(current))
      }
    }, duration / steps)

    return () => clearInterval(interval)
  }, [score])

  return (
    <motion.div 
      className="stat-card rounded-xl p-6 md:p-8"
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
    >
      <div className="flex flex-col md:flex-row items-center gap-8">
        {/* Score Circle */}
        <div className="relative flex-shrink-0">
          <svg width="160" height="160" className="transform -rotate-90">
            {/* Background circle */}
            <circle
              cx="80"
              cy="80"
              r="70"
              fill="none"
              stroke="#2C3440"
              strokeWidth="8"
            />
            {/* Progress circle */}
            <motion.circle
              cx="80"
              cy="80"
              r="70"
              fill="none"
              stroke="url(#scoreGradient)"
              strokeWidth="8"
              strokeLinecap="round"
              strokeDasharray={440}
              initial={{ strokeDashoffset: 440 }}
              animate={{ strokeDashoffset: 440 - (440 * displayScore) / 100 }}
              transition={{ duration: 1.5, ease: 'easeOut' }}
            />
            <defs>
              <linearGradient id="scoreGradient" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" stopColor="#00E054" />
                <stop offset="100%" stopColor="#40BCF4" />
              </linearGradient>
            </defs>
          </svg>
          
          {/* Score number */}
          <div className="absolute inset-0 flex flex-col items-center justify-center">
            <span className="text-5xl font-bold text-lb-white font-display">
              {displayScore}
            </span>
            <span className="text-lb-text text-xs uppercase tracking-wider mt-1">
              obscurity
            </span>
          </div>
        </div>

        {/* Score Details */}
        <div className="flex-1 text-center md:text-left">
          <p className="text-lb-text text-sm mb-2">
            <span className="text-lb-green">@{username}</span>
          </p>
          
          <h2 className="font-display text-3xl md:text-4xl text-lb-white mb-3">
            {label}
          </h2>
          
          <p className="text-lb-text text-lg mb-6">
            {description}
          </p>

          {/* Score bar */}
          <div>
            <div className="flex justify-between text-xs text-lb-text mb-2">
              <span>Mainstream</span>
              <span>Obscure</span>
            </div>
            <div className="h-2 bg-lb-border rounded-full overflow-hidden">
              <motion.div
                initial={{ width: 0 }}
                animate={{ width: `${score}%` }}
                transition={{ duration: 1.2, ease: 'easeOut' }}
                className="h-full rounded-full bg-gradient-to-r from-lb-orange via-lb-green to-lb-blue"
              />
            </div>
          </div>
        </div>
      </div>
    </motion.div>
  )
}
