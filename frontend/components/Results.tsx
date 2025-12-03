'use client'

import { motion } from 'framer-motion'
import { AnalysisResult } from '@/app/page'
import ObscurityScore from './ObscurityScore'
import GenreChart from './charts/GenreChart'
import DecadeChart from './charts/DecadeChart'
import MoodChart from './charts/MoodChart'
import FilmCard from './FilmCard'
import FilmsByDecade from './FilmsByDecade'

type Props = {
  data: AnalysisResult
}

const container = {
  hidden: { opacity: 0 },
  show: {
    opacity: 1,
    transition: {
      staggerChildren: 0.08,
    },
  },
}

const item = {
  hidden: { opacity: 0, y: 20 },
  show: { opacity: 1, y: 0, transition: { duration: 0.4 } },
}

export default function Results({ data }: Props) {
  const topDirectors = Object.entries(data.director_counts).slice(0, 5)
  const topCountries = Object.entries(data.country_breakdown).slice(0, 5)

  return (
    <motion.div
      variants={container}
      initial="hidden"
      animate="show"
      className="space-y-6"
    >
      {/* Obscurity Score */}
      <motion.div variants={item}>
        <ObscurityScore score={data.obscurity_score} username={data.username} />
      </motion.div>

      {/* Quick Stats */}
      <motion.div variants={item} className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <StatCard label="Films" value={data.total_films.toLocaleString()} color="orange" />
        <StatCard label="Avg Rating" value={data.average_rating ? `${data.average_rating.toFixed(1)}★` : '—'} color="green" />
        <StatCard label="Top Genre" value={Object.keys(data.top_genres)[0] || '—'} color="blue" />
        <StatCard label="Countries" value={Object.keys(data.country_breakdown).length.toString()} color="orange" />
      </motion.div>

      {/* Charts */}
      <div className="grid md:grid-cols-2 gap-4">
        <motion.div variants={item} className="stat-card rounded-xl p-5">
          <h3 className="font-display text-lg text-lb-white mb-4">Genres</h3>
          <GenreChart data={data.top_genres} />
        </motion.div>

        <motion.div variants={item} className="stat-card rounded-xl p-5">
          <h3 className="font-display text-lg text-lb-white mb-4">Decades</h3>
          <DecadeChart data={data.decade_breakdown} />
        </motion.div>
      </div>

      {/* Films by Decade */}
      {data.films_by_decade && Object.keys(data.films_by_decade).length > 0 && (
        <motion.div variants={item} className="stat-card rounded-xl p-5">
          <h3 className="font-display text-lg text-lb-white mb-1">Films by Decade</h3>
          <p className="text-lb-text text-sm mb-4">Your top films from each era</p>
          <FilmsByDecade 
            filmsByDecade={data.films_by_decade} 
            decadeBreakdown={data.decade_breakdown}
          />
        </motion.div>
      )}

      {/* Mood */}
      <motion.div variants={item} className="stat-card rounded-xl p-5">
        <h3 className="font-display text-lg text-lb-white mb-4">Mood Profile</h3>
        <MoodChart data={data.mood_analysis} />
      </motion.div>

      {/* Most Obscure */}
      {data.most_obscure_films.length > 0 && (
        <motion.div variants={item} className="stat-card rounded-xl p-5">
          <h3 className="font-display text-lg text-lb-white mb-1">Most Obscure</h3>
          <p className="text-lb-text text-sm mb-4">Your hidden gems</p>
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 gap-3">
            {data.most_obscure_films.map((film, index) => (
              <FilmCard key={film.title + index} film={film} rank={index + 1} type="obscure" />
            ))}
          </div>
        </motion.div>
      )}

      {/* Most Mainstream */}
      {data.most_mainstream_films.length > 0 && (
        <motion.div variants={item} className="stat-card rounded-xl p-5">
          <h3 className="font-display text-lg text-lb-white mb-1">Most Popular</h3>
          <p className="text-lb-text text-sm mb-4">Your crowd-pleasers</p>
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 gap-3">
            {data.most_mainstream_films.map((film, index) => (
              <FilmCard key={film.title + index} film={film} rank={index + 1} type="mainstream" />
            ))}
          </div>
        </motion.div>
      )}

      {/* Directors & Countries */}
      <div className="grid md:grid-cols-2 gap-4">
        {topDirectors.length > 0 && (
          <motion.div variants={item} className="stat-card rounded-xl p-5">
            <h3 className="font-display text-lg text-lb-white mb-4">Top Directors</h3>
            <div className="space-y-2">
              {topDirectors.map(([name, count], index) => (
                <div key={name} className="flex items-center gap-3">
                  <span className={`w-6 h-6 rounded text-xs font-bold flex items-center justify-center ${
                    index === 0 ? 'bg-lb-green text-lb-darker' : 'bg-lb-border text-lb-text'
                  }`}>
                    {index + 1}
                  </span>
                  <span className="flex-1 text-lb-text-light text-sm truncate">{name}</span>
                  <span className="text-lb-text text-xs">{count}</span>
                </div>
              ))}
            </div>
          </motion.div>
        )}

        {topCountries.length > 0 && (
          <motion.div variants={item} className="stat-card rounded-xl p-5">
            <h3 className="font-display text-lg text-lb-white mb-4">Countries</h3>
            <div className="space-y-2">
              {topCountries.map(([country, count], index) => (
                <div key={country} className="flex items-center gap-3">
                  <span className={`w-6 h-6 rounded text-xs font-bold flex items-center justify-center ${
                    index === 0 ? 'bg-lb-green text-lb-darker' : 'bg-lb-border text-lb-text'
                  }`}>
                    {index + 1}
                  </span>
                  <span className="flex-1 text-lb-text-light text-sm truncate">{country}</span>
                  <span className="text-lb-text text-xs">{count}</span>
                </div>
              ))}
            </div>
          </motion.div>
        )}
      </div>
    </motion.div>
  )
}

function StatCard({ label, value, color }: { label: string; value: string; color: 'orange' | 'green' | 'blue' }) {
  const colors = {
    orange: 'border-lb-orange/30 hover:border-lb-orange/60',
    green: 'border-lb-green/30 hover:border-lb-green/60',
    blue: 'border-lb-blue/30 hover:border-lb-blue/60',
  }
  const dotColors = {
    orange: 'bg-lb-orange',
    green: 'bg-lb-green',
    blue: 'bg-lb-blue',
  }

  return (
    <div className={`stat-card rounded-lg p-4 border ${colors[color]} transition-colors`}>
      <div className="flex items-center gap-2 mb-1">
        <span className={`w-2 h-2 rounded-full ${dotColors[color]}`} />
        <span className="text-lb-text text-xs uppercase tracking-wider">{label}</span>
      </div>
      <p className="text-xl font-display text-lb-white truncate">{value}</p>
    </div>
  )
}
