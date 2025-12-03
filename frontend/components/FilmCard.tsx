'use client'

import { motion } from 'framer-motion'

type Film = {
  title: string
  year: number
  watches?: number | null
  popularity?: number | null
  director: string
  poster_path: string
}

type Props = {
  film: Film
  rank: number
  type: 'obscure' | 'mainstream'
}

function formatWatches(watches: number): string {
  if (watches >= 1_000_000) {
    return `${(watches / 1_000_000).toFixed(1)}M`
  } else if (watches >= 1_000) {
    return `${(watches / 1_000).toFixed(1)}K`
  }
  return watches.toString()
}

export default function FilmCard({ film, rank, type }: Props) {
  const posterUrl = film.poster_path
    ? `https://image.tmdb.org/t/p/w300${film.poster_path}`
    : null

  return (
    <motion.div
      className="group relative"
      whileHover={{ y: -4 }}
      transition={{ duration: 0.2 }}
    >
      {/* Rank badge */}
      <div className={`absolute -top-1.5 -left-1.5 z-10 w-6 h-6 rounded text-xs font-bold flex items-center justify-center ${
        type === 'obscure' ? 'bg-lb-green text-lb-darker' : 'bg-lb-border text-lb-text'
      }`}>
        {rank}
      </div>

      {/* Poster */}
      <div className="aspect-[2/3] rounded-md overflow-hidden bg-lb-card border border-lb-border group-hover:border-lb-green/50 transition-colors">
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
        
        {/* Hover overlay */}
        <div className="absolute inset-0 bg-gradient-to-t from-lb-darker via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity flex items-end p-2">
          <div className="text-xs">
            {film.director && (
              <p className="text-lb-text-light truncate">{film.director}</p>
            )}
            {film.watches && (
              <p className="text-lb-green">{formatWatches(film.watches)} watches</p>
            )}
          </div>
        </div>
      </div>

      {/* Title */}
      <h4 className="text-xs text-lb-text-light mt-2 leading-tight line-clamp-2 group-hover:text-lb-white transition-colors">
        {film.title}
      </h4>
      <p className="text-xs text-lb-text">{film.year || '—'}</p>
    </motion.div>
  )
}
