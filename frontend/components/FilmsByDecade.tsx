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

      {/* Films grid */}
      {selectedDecade && (
        <motion.div
          key={selectedDecade}
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.2 }}
        >
          {selectedFilms.length > 0 ? (
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 gap-3">
              {selectedFilms.map((film, index) => {
                // Support both TMDb and Letterboxd poster URLs
                const posterUrl = film.poster_path
                  ? film.poster_path.startsWith('http')
                    ? film.poster_path  // Already a full URL (Letterboxd)
                    : `https://image.tmdb.org/t/p/w300${film.poster_path}`  // TMDb path (starts with /)
                  : null

                return (
                  <motion.div
                    key={film.title + index}
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: index * 0.05 }}
                    className="group"
                  >
                    <div className="aspect-[2/3] rounded-md overflow-hidden bg-lb-card border border-lb-border group-hover:border-lb-green/50 transition-colors relative">
                      {posterUrl ? (
                        <img
                          src={posterUrl}
                          alt={film.title}
                          className="w-full h-full object-cover"
                        />
                      ) : (
                        <div className="w-full h-full flex items-center justify-center text-lb-text/30">
                          <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M7 4v16M17 4v16M3 8h4m10 0h4M3 12h18M3 16h4m10 0h4M4 20h16a1 1 0 001-1V5a1 1 0 00-1-1H4a1 1 0 00-1 1v14a1 1 0 001 1z" />
                          </svg>
                        </div>
                      )}
                      
                      {/* Rank badge */}
                      <div className="absolute top-1.5 left-1.5 w-5 h-5 rounded-full bg-lb-orange text-lb-darker flex items-center justify-center text-xs font-bold">
                        {index + 1}
                      </div>
                      
                      {/* Hover overlay */}
                      <div className="absolute inset-0 bg-gradient-to-t from-lb-darker via-lb-darker/60 to-transparent opacity-0 group-hover:opacity-100 transition-opacity flex flex-col justify-end p-2">
                        <div className="text-xs space-y-0.5">
                          {film.director && (
                            <p className="text-lb-text-light truncate">{film.director}</p>
                          )}
                          {film.obscurity_score && (
                            <p className="text-lb-orange font-medium">{film.obscurity_score}% obscure</p>
                          )}
                        </div>
                      </div>
                    </div>
                    <h4 className="text-xs text-lb-text-light mt-2 leading-tight line-clamp-2 group-hover:text-lb-white transition-colors">
                      {film.title}
                    </h4>
                    <p className="text-xs text-lb-text">{film.year}</p>
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
