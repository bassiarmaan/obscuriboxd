'use client'

import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import UsernameInput from '@/components/UsernameInput'
import Results from '@/components/Results'
import LoadingState from '@/components/LoadingState'

export type Film = {
  title: string
  year: number
  watches?: number | null
  popularity?: number | null
  director: string
  poster_path: string
}

export type AnalysisResult = {
  username: string
  obscurity_score: number
  total_films: number
  average_rating: number | null
  top_genres: Record<string, number>
  decade_breakdown: Record<string, number>
  country_breakdown: Record<string, number>
  most_obscure_films: Film[]
  most_mainstream_films: Film[]
  director_counts: Record<string, number>
  rating_distribution: Record<string, number>
  mood_analysis: Record<string, number>
  films_by_decade: Record<string, Film[]>
}

export default function Home() {
  const [isLoading, setIsLoading] = useState(false)
  const [results, setResults] = useState<AnalysisResult | null>(null)
  const [error, setError] = useState<string | null>(null)

  const handleAnalyze = async (username: string) => {
    setIsLoading(true)
    setError(null)
    setResults(null)

    try {
      const response = await fetch('http://localhost:8000/analyze', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ username }),
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || 'Failed to analyze user')
      }

      const data = await response.json()
      setResults(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Something went wrong')
    } finally {
      setIsLoading(false)
    }
  }

  const handleReset = () => {
    setResults(null)
    setError(null)
  }

  return (
    <div className="min-h-screen flex flex-col bg-lb-darker">
      {/* Header */}
      <header className="py-4 px-6 border-b border-lb-border/50">
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
          className="flex items-center justify-between max-w-6xl mx-auto"
        >
          <button 
            onClick={handleReset}
            className="flex items-center gap-3 group focus-ring rounded-lg"
          >
            {/* Letterboxd-style logo dots */}
            <div className="flex gap-0.5">
              <div className="w-2 h-5 rounded-sm bg-lb-orange" />
              <div className="w-2 h-5 rounded-sm bg-lb-green" />
              <div className="w-2 h-5 rounded-sm bg-lb-blue" />
            </div>
            <span className="font-display text-xl font-bold text-lb-white group-hover:text-lb-green transition-colors">
              obscuriboxd
            </span>
          </button>
          
          {results && (
            <motion.button
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              onClick={handleReset}
              className="text-sm text-lb-text hover:text-lb-green transition-colors"
            >
              ← New Search
            </motion.button>
          )}
        </motion.div>
      </header>

      {/* Main Content */}
      <div className="flex-1 flex flex-col items-center justify-center px-6 py-12">
        <AnimatePresence mode="wait">
          {!results && !isLoading && (
            <motion.div
              key="input"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0, y: -20 }}
              transition={{ duration: 0.4 }}
              className="w-full max-w-xl text-center"
            >
              {/* Title */}
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.1, duration: 0.5 }}
                className="mb-8"
              >
                <h1 className="font-display text-4xl md:text-5xl font-bold text-lb-white mb-4">
                  How <span className="text-lb-green">obscure</span> is your film taste?
                </h1>
                <p className="text-lb-text text-lg">
                  Enter your Letterboxd username to find out.
                </p>
              </motion.div>

              {/* Input */}
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.2, duration: 0.5 }}
              >
                <UsernameInput onSubmit={handleAnalyze} disabled={isLoading} />
              </motion.div>

              {/* Error message */}
              <AnimatePresence>
                {error && (
                  <motion.div
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0 }}
                    className="mt-6 p-4 rounded-lg bg-red-500/10 border border-red-500/30 text-red-400 text-sm"
                  >
                    {error}
                  </motion.div>
                )}
              </AnimatePresence>

              {/* Features */}
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: 0.4, duration: 0.5 }}
                className="mt-12 flex flex-wrap justify-center gap-6 text-sm text-lb-text"
              >
                <div className="flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-lb-orange" />
                  Obscurity Score
                </div>
                <div className="flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-lb-green" />
                  Genre Analysis
                </div>
                <div className="flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-lb-blue" />
                  Film Breakdown
                </div>
              </motion.div>
            </motion.div>
          )}

          {isLoading && (
            <motion.div
              key="loading"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.3 }}
              className="w-full"
            >
              <LoadingState />
            </motion.div>
          )}

          {results && !isLoading && (
            <motion.div
              key="results"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.4 }}
              className="w-full max-w-6xl"
            >
              <Results data={results} />
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* Footer */}
      <footer className="py-4 px-6 border-t border-lb-border/50">
        <div className="max-w-6xl mx-auto flex flex-col md:flex-row items-center justify-between gap-3 text-xs text-lb-text">
          <span>Data from Letterboxd & TMDb</span>
          <div className="flex items-center gap-4">
            <a href="/about" className="hover:text-lb-green transition-colors">
              About
            </a>
            <a href="/privacy" className="hover:text-lb-green transition-colors">
              Privacy
            </a>
          </div>
        </div>
      </footer>
    </div>
  )
}
