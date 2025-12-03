'use client'

import { useState } from 'react'
import { motion } from 'framer-motion'

type Props = {
  onSubmit: (username: string) => void
  disabled?: boolean
}

export default function UsernameInput({ onSubmit, disabled }: Props) {
  const [username, setUsername] = useState('')
  const [isFocused, setIsFocused] = useState(false)

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (username.trim()) {
      onSubmit(username.trim())
    }
  }

  return (
    <form onSubmit={handleSubmit} className="relative">
      <div className="relative">
        {/* Main container */}
        <div className={`flex items-center bg-lb-card rounded-lg border transition-all duration-200 ${
          isFocused ? 'border-lb-green shadow-glow-green' : 'border-lb-border'
        }`}>
          {/* Letterboxd-style prefix */}
          <div className="pl-4 pr-3 py-3 flex items-center gap-2 border-r border-lb-border">
            <div className="flex gap-0.5">
              <div className="w-1.5 h-3 rounded-sm bg-lb-orange" />
              <div className="w-1.5 h-3 rounded-sm bg-lb-green" />
              <div className="w-1.5 h-3 rounded-sm bg-lb-blue" />
            </div>
            <span className="text-lb-text text-sm hidden sm:block">letterboxd.com/</span>
          </div>
          
          {/* Input field */}
          <input
            type="text"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            onFocus={() => setIsFocused(true)}
            onBlur={() => setIsFocused(false)}
            placeholder="username"
            disabled={disabled}
            className="flex-1 px-4 py-3 bg-transparent text-lb-white placeholder:text-lb-text/50 focus:outline-none disabled:opacity-50 font-body"
            autoComplete="off"
            spellCheck="false"
          />
          
          {/* Submit button */}
          <div className="pr-2">
            <motion.button
              type="submit"
              disabled={disabled || !username.trim()}
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
              className="px-5 py-2 bg-lb-green text-lb-darker font-semibold text-sm rounded-md disabled:opacity-40 disabled:cursor-not-allowed hover:bg-[#00FF5E] transition-colors"
            >
              GO
            </motion.button>
          </div>
        </div>
      </div>
      
      {/* Helper text */}
      <p className="mt-3 text-lb-text/60 text-xs text-center">
        Your profile must be public
      </p>
    </form>
  )
}
