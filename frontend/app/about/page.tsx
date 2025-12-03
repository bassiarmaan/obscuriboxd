'use client'

import { motion } from 'framer-motion'
import Link from 'next/link'

const faqs = [
  {
    question: 'How is the obscurity score calculated?',
    answer: 'Your score is based on the popularity of films you\'ve watched on Letterboxd. Films with fewer watches contribute more to your score.',
  },
  {
    question: 'Why do I need a public profile?',
    answer: 'We need to access your watched films list. You can temporarily make it public for the analysis.',
  },
  {
    question: 'Is my data stored?',
    answer: 'No. The analysis is performed in real-time and discarded after you close the page.',
  },
  {
    question: 'Can I share my results?',
    answer: 'Yes! Take a screenshot to share your obscurity score with friends.',
  },
]

const team = [
  {
    name: 'Armaan Bassi',
    role: 'Developer',
    image: '/team/armaan.jpg',
    links: {
      email: 'armalbassi@gmail.com',
      x: 'https://x.com/armbot7',
      letterboxd: 'https://letterboxd.com/armbot/',
    },
  },
  {
    name: 'Daniel Lee',
    role: 'Designer & Creative Marketing',
    image: '/team/daniel.jpg',
    links: {
      email: 'daniel.lee.4564@gmail.com',
      x: 'https://x.com/Korean_BF',
      letterboxd: 'https://letterboxd.com/dan_lee/',
    },
  },
]

export default function AboutPage() {
  return (
    <div className="min-h-screen flex flex-col bg-lb-darker">
      {/* Header */}
      <header className="py-4 px-6 border-b border-lb-border/50">
        <div className="flex items-center justify-between max-w-3xl mx-auto">
          <Link href="/" className="flex items-center gap-3 group">
            <div className="flex gap-0.5">
              <div className="w-2 h-5 rounded-sm bg-lb-orange" />
              <div className="w-2 h-5 rounded-sm bg-lb-green" />
              <div className="w-2 h-5 rounded-sm bg-lb-blue" />
            </div>
            <span className="font-display text-xl font-bold text-lb-white group-hover:text-lb-green transition-colors">
              obscuriboxd
            </span>
          </Link>
          <Link href="/" className="text-sm text-lb-text hover:text-lb-green transition-colors">
            ← Back
          </Link>
        </div>
      </header>

      {/* Main */}
      <main className="flex-1 px-6 py-10">
        <div className="max-w-3xl mx-auto space-y-10">
          {/* About */}
          <motion.section
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
          >
            <h1 className="font-display text-3xl text-lb-white mb-4">
              About
            </h1>
            <div className="stat-card rounded-xl p-6 text-lb-text leading-relaxed space-y-3">
              <p>
                Obscuriboxd analyzes your Letterboxd profile to reveal how obscure your film taste is.
              </p>
              <p>
                Enter your username to get an obscurity score, genre breakdown, and discover patterns in your viewing habits.
              </p>
            </div>
          </motion.section>

          {/* Team */}
          <motion.section
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
          >
            <h2 className="font-display text-2xl text-lb-white mb-4">Team</h2>
            <div className="grid gap-4">
              {team.map((member) => (
                <div key={member.name} className="stat-card rounded-xl p-6">
                  <div className="flex items-center gap-4">
                    <div className="w-16 h-16 rounded-lg overflow-hidden border border-lb-border bg-lb-card flex items-center justify-center">
                      {member.image ? (
                        <img 
                          src={member.image} 
                          alt={member.name}
                          className="w-full h-full object-cover"
                          onError={(e) => {
                            e.currentTarget.style.display = 'none'
                            e.currentTarget.nextElementSibling?.classList.remove('hidden')
                          }}
                        />
                      ) : null}
                      <span className="text-lb-text text-2xl hidden">{member.name[0]}</span>
                    </div>
                    <div>
                      <h3 className="font-display text-lg text-lb-white">{member.name}</h3>
                      <p className="text-lb-green text-sm mb-2">{member.role}</p>
                      <div className="flex gap-2 flex-wrap">
                        {member.links.email && (
                          <a
                            href={`mailto:${member.links.email}`}
                            className="flex items-center gap-1.5 px-2.5 py-1 rounded bg-lb-border/50 text-lb-text hover:text-lb-green hover:bg-lb-border transition-colors text-xs"
                          >
                            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                            </svg>
                            Email
                          </a>
                        )}
                        {member.links.x && (
                          <a
                            href={member.links.x}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="flex items-center gap-1.5 px-2.5 py-1 rounded bg-lb-border/50 text-lb-text hover:text-lb-green hover:bg-lb-border transition-colors text-xs"
                          >
                            <svg className="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 24 24">
                              <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z" />
                            </svg>
                            X
                          </a>
                        )}
                        {member.links.letterboxd && (
                          <a
                            href={member.links.letterboxd}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="flex items-center gap-1.5 px-2.5 py-1 rounded bg-lb-border/50 text-lb-text hover:text-lb-green hover:bg-lb-border transition-colors text-xs"
                          >
                            <div className="flex gap-0.5">
                              <div className="w-1 h-2 rounded-sm bg-lb-orange" />
                              <div className="w-1 h-2 rounded-sm bg-lb-green" />
                              <div className="w-1 h-2 rounded-sm bg-lb-blue" />
                            </div>
                            Letterboxd
                          </a>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </motion.section>

          {/* FAQ */}
          <motion.section
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
          >
            <h2 className="font-display text-2xl text-lb-white mb-4">FAQ</h2>
            <div className="space-y-3">
              {faqs.map((faq, index) => (
                <div key={index} className="stat-card rounded-xl p-5">
                  <h3 className="text-lb-white font-medium mb-2">{faq.question}</h3>
                  <p className="text-lb-text text-sm">{faq.answer}</p>
                </div>
              ))}
            </div>
          </motion.section>
        </div>
      </main>

      {/* Footer */}
      <footer className="py-4 px-6 border-t border-lb-border/50">
        <div className="max-w-3xl mx-auto flex items-center justify-between text-xs text-lb-text">
          <span>Data from Letterboxd & TMDb</span>
          <div className="flex gap-4">
            <Link href="/about" className="text-lb-green">About</Link>
            <Link href="/privacy" className="hover:text-lb-green transition-colors">Privacy</Link>
          </div>
        </div>
      </footer>
    </div>
  )
}
