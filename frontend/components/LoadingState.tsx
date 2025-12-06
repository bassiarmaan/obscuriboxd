'use client'

import { motion, AnimatePresence } from 'framer-motion'
import { useEffect, useState, useRef } from 'react'

const messages = [
  'Connecting to Letterboxd...',
  'Scanning your film diary...',
  'Analyzing your taste...',
  'Crunching the numbers...',
  'Almost there...',
]

type Props = {
  isComplete?: boolean
}

export default function LoadingState({ isComplete = false }: Props) {
  const [messageIndex, setMessageIndex] = useState(0)
  const [progress, setProgress] = useState(0)
  const startTime = useRef(Date.now())
  const progressRef = useRef(0)

  useEffect(() => {
    // Realistic progress simulation based on typical processing times
    // Phase 1 (0-30%): Scraping Letterboxd - slower start
    // Phase 2 (30-70%): TMDb enrichment - faster middle
    // Phase 3 (70-95%): Calculations - slower end
    // Phase 4 (95-100%): Final processing - only when complete
    
    const updateProgress = () => {
      if (isComplete) {
        // When complete, quickly animate to 100%
        if (progressRef.current < 100) {
          progressRef.current = Math.min(100, progressRef.current + 2)
          setProgress(progressRef.current)
        }
        return
      }

      const elapsed = Date.now() - startTime.current
      const elapsedSeconds = elapsed / 1000

      // Realistic progress curve based on time
      let targetProgress = 0
      
      if (elapsedSeconds < 5) {
        // First 5 seconds: 0-25% (scraping phase)
        targetProgress = (elapsedSeconds / 5) * 25
      } else if (elapsedSeconds < 15) {
        // Next 10 seconds: 25-65% (TMDb enrichment phase)
        targetProgress = 25 + ((elapsedSeconds - 5) / 10) * 40
      } else if (elapsedSeconds < 30) {
        // Next 15 seconds: 65-90% (calculation phase)
        targetProgress = 65 + ((elapsedSeconds - 15) / 15) * 25
      } else {
        // After 30 seconds: 90-95% (slow crawl)
        targetProgress = Math.min(95, 90 + ((elapsedSeconds - 30) / 10) * 5)
      }

      // Smooth progress updates
      if (targetProgress > progressRef.current) {
        const increment = Math.min(1, (targetProgress - progressRef.current) * 0.3)
        progressRef.current = Math.min(targetProgress, progressRef.current + increment)
        setProgress(Math.round(progressRef.current))
      }
    }

    const progressInterval = setInterval(updateProgress, 200) // Update more frequently for smoother progress

    // Update messages based on progress
    const messageInterval = setInterval(() => {
      if (progressRef.current < 25) {
        setMessageIndex(0)
      } else if (progressRef.current < 50) {
        setMessageIndex(1)
      } else if (progressRef.current < 75) {
        setMessageIndex(2)
      } else if (progressRef.current < 95) {
        setMessageIndex(3)
      } else {
        setMessageIndex(4)
      }
    }, 1000)

    return () => {
      clearInterval(progressInterval)
      clearInterval(messageInterval)
    }
  }, [isComplete])

  return (
    <div className="flex flex-col items-center justify-center py-20 px-4">
      {/* Film Reel Animation */}
      <div className="relative w-48 h-48 mb-10">
        {/* Outer reel */}
        <motion.div
          className="absolute inset-0 rounded-full border-4 border-lb-border"
          animate={{ rotate: 360 }}
          transition={{ duration: 3, repeat: Infinity, ease: 'linear' }}
        >
          {/* Sprocket holes */}
          {[...Array(8)].map((_, i) => (
            <div
              key={i}
              className="absolute w-4 h-4 bg-lb-darker rounded-full border-2 border-lb-border"
              style={{
                top: '50%',
                left: '50%',
                transform: `rotate(${i * 45}deg) translateY(-88px) translate(-50%, -50%)`,
              }}
            />
          ))}
        </motion.div>

        {/* Inner reel spinning opposite */}
        <motion.div
          className="absolute inset-8 rounded-full border-4 border-lb-border"
          animate={{ rotate: -360 }}
          transition={{ duration: 2, repeat: Infinity, ease: 'linear' }}
        >
          {[...Array(6)].map((_, i) => (
            <div
              key={i}
              className="absolute w-3 h-3 bg-lb-darker rounded-full border-2 border-lb-border"
              style={{
                top: '50%',
                left: '50%',
                transform: `rotate(${i * 60}deg) translateY(-56px) translate(-50%, -50%)`,
              }}
            />
          ))}
        </motion.div>

        {/* Center hub */}
        <div className="absolute inset-0 flex items-center justify-center">
          <motion.div
            className="w-20 h-20 rounded-full bg-lb-card border-4 border-lb-border flex items-center justify-center"
            animate={{ rotate: 360 }}
            transition={{ duration: 4, repeat: Infinity, ease: 'linear' }}
          >
            <div className="w-8 h-8 rounded-full bg-lb-darker border-2 border-lb-border" />
          </motion.div>
        </div>

        {/* Film strip feeding through */}
        <div className="absolute -right-4 top-1/2 -translate-y-1/2 overflow-hidden h-12 w-32">
          <motion.div
            className="flex gap-1"
            animate={{ x: [0, -80] }}
            transition={{ duration: 0.8, repeat: Infinity, ease: 'linear' }}
          >
            {[...Array(12)].map((_, i) => (
              <div key={i} className="flex-shrink-0 w-8 h-12 bg-lb-card border border-lb-border rounded-sm relative">
                <div className="absolute top-1 left-1 w-1.5 h-1.5 rounded-full bg-lb-border" />
                <div className="absolute bottom-1 left-1 w-1.5 h-1.5 rounded-full bg-lb-border" />
                <div className="absolute top-1 right-1 w-1.5 h-1.5 rounded-full bg-lb-border" />
                <div className="absolute bottom-1 right-1 w-1.5 h-1.5 rounded-full bg-lb-border" />
              </div>
            ))}
          </motion.div>
        </div>

        {/* Glowing progress ring */}
        <svg className="absolute inset-0 w-full h-full -rotate-90">
          <circle
            cx="96"
            cy="96"
            r="92"
            fill="none"
            stroke="#2C3440"
            strokeWidth="2"
          />
          <motion.circle
            cx="96"
            cy="96"
            r="92"
            fill="none"
            stroke="url(#progressGradient)"
            strokeWidth="3"
            strokeLinecap="round"
            strokeDasharray={578}
            initial={{ strokeDashoffset: 578 }}
            animate={{ strokeDashoffset: 578 - (578 * progress) / 100 }}
            transition={{ duration: 0.5 }}
            style={{ filter: 'drop-shadow(0 0 6px rgba(0, 224, 84, 0.5))' }}
          />
          <defs>
            <linearGradient id="progressGradient" x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" stopColor="#FF8000" />
              <stop offset="50%" stopColor="#00E054" />
              <stop offset="100%" stopColor="#40BCF4" />
            </linearGradient>
          </defs>
        </svg>
      </div>

      {/* Progress percentage - fixed: no key prop causing duplicates */}
      <div className="text-4xl font-bold text-lb-white font-mono mb-4">
        {progress}%
      </div>

      {/* Message */}
      <AnimatePresence mode="wait">
        <motion.p
          key={messageIndex}
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -10 }}
          className="text-lb-text text-center"
        >
          {messages[messageIndex]}
        </motion.p>
      </AnimatePresence>

      {/* Film countdown style dots */}
      <div className="flex gap-3 mt-8">
        {messages.map((_, i) => (
          <motion.div
            key={i}
            className={`w-2 h-2 rounded-full ${i <= messageIndex ? 'bg-lb-green' : 'bg-lb-border'}`}
            animate={i === messageIndex ? { scale: [1, 1.3, 1] } : {}}
            transition={{ duration: 0.5, repeat: i === messageIndex ? Infinity : 0 }}
          />
        ))}
      </div>
    </div>
  )
}
