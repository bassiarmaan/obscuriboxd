'use client'

import { motion } from 'framer-motion'
import { useState, useEffect } from 'react'

type Film = {
  title: string
  year: number
  watches?: number | null
  popularity?: number | null
  director: string
  poster_path: string
  obscurity_score?: number
}

type Props = {
  filmsByDecade: Record<string, Film[]>
  decadeBreakdown: Record<string, number>
}

export default function FilmsByDecade({ filmsByDecade, decadeBreakdown }: Props) {
  // Get all decades that have films, sorted (most recent first)
  const decades = Object.keys(decadeBreakdown)
    .sort((a, b) => {
      const decadeA = parseInt(a.replace('s', ''))
      const decadeB = parseInt(b.replace('s', ''))
      return decadeB - decadeA
    })

  const [selectedDecade, setSelectedDecade] = useState<string | null>(null)

  // Set default selected decade when decades are available
  useEffect(() => {
    if (decades.length > 0 && !selectedDecade) {
      setSelectedDecade(decades[0])
    }
  }, [decades, selectedDecade])

  // Get films for selected decade
  const selectedFilms = selectedDecade ? (filmsByDecade[selectedDecade] || []) : []

  if (decades.length === 0) {
    return null
  }

  return (
    <div className="space-y-4">
      {/* Decade tabs */}
      <div className="flex flex-wrap gap-2">
        {decades.map((decade) => {
          const isSelected = selectedDecade === decade
          return (
            <button
              key={decade}
              onClick={() => setSelectedDecade(decade)}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                isSelected
                  ? 'bg-lb-green text-lb-darker'
                  : 'bg-lb-border/50 text-lb-text hover:bg-lb-border hover:text-lb-white'
              }`}
            >
              {decade}
              <span className={`ml-2 ${isSelected ? 'opacity-80' : 'opacity-50'}`}>
                ({decadeBreakdown[decade] || 0})
              </span>
            </button>
          )
        })}
      </div>

      {/* Films list */}
      {selectedDecade && (
        <motion.div
          key={selectedDecade}
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.2 }}
        >
          {selectedFilms.length > 0 ? (
            <div className="space-y-2">
              {selectedFilms.map((film, index) => {
                const posterUrl = film.poster_path
                  ? `https://image.tmdb.org/t/p/w92${film.poster_path}`
                  : null
                
                // Format watch count
                const formatWatches = (watches: number | null | undefined) => {
                  if (!watches) return 'Unknown'
                  if (watches >= 1_000_000) return `${(watches / 1_000_000).toFixed(1)}M`
                  if (watches >= 1_000) return `${(watches / 1_000).toFixed(0)}K`
                  return watches.toString()
                }

                return (
                  <motion.div
                    key={film.title + index}
                    initial={{ opacity: 0, x: -10 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: index * 0.05 }}
                    className="group flex items-center gap-3 p-2 rounded-lg bg-lb-card/50 border border-lb-border hover:border-lb-green/50 hover:bg-lb-card transition-all"
                  >
                    {/* Rank */}
                    <div className="flex-shrink-0 w-6 h-6 rounded-full bg-lb-orange/20 text-lb-orange flex items-center justify-center text-xs font-bold">
                      {index + 1}
                    </div>
                    
                    {/* Poster */}
                    <div className="flex-shrink-0 w-10 h-14 rounded overflow-hidden bg-lb-darker">
                      {posterUrl ? (
                        <img
                          src={posterUrl}
                          alt={film.title}
                          className="w-full h-full object-cover"
                        />
                      ) : (
                        <div className="w-full h-full flex items-center justify-center text-lb-text/30">
                          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M7 4v16M17 4v16M3 8h4m10 0h4M3 12h18M3 16h4m10 0h4M4 20h16a1 1 0 001-1V5a1 1 0 00-1-1H4a1 1 0 00-1 1v14a1 1 0 001 1z" />
                          </svg>
                        </div>
                      )}
                    </div>
                    
                    {/* Info */}
                    <div className="flex-grow min-w-0">
                      <h4 className="text-sm text-lb-white font-medium truncate group-hover:text-lb-green transition-colors">
                        {film.title}
                      </h4>
                      <p className="text-xs text-lb-text">
                        {film.year} {film.director && `• ${film.director}`}
                      </p>
                    </div>
                    
                    {/* Stats */}
                    <div className="flex-shrink-0 text-right">
                      <div className="text-xs text-lb-orange font-medium">
                        {formatWatches(film.watches)} watches
                      </div>
                      {film.obscurity_score && (
                        <div className="text-[10px] text-lb-text">
                          {film.obscurity_score}% obscure
                        </div>
                      )}
                    </div>
                  </motion.div>
                )
              })}
            </div>
          ) : (
            <div className="text-center py-8 text-lb-text">
              <p>No films available for {selectedDecade}</p>
            </div>
          )}
        </motion.div>
      )}
    </div>
  )
}
