'use client'

import { motion } from 'framer-motion'
import Link from 'next/link'

export default function PrivacyPage() {
  return (
    <div className="min-h-screen flex flex-col bg-lb-darker">
      {/* Header */}
      <header className="py-4 px-6 border-b border-lb-border/50">
        <div className="flex items-center justify-between max-w-3xl mx-auto">
          <Link href="/" className="flex items-center gap-3 group">
            <img src="/logo1.png" alt="Obscuriboxd" className="h-8 w-auto" />
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
        <div className="max-w-3xl mx-auto">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
          >
            <h1 className="font-display text-3xl text-lb-white mb-2">Privacy Policy</h1>
            <p className="text-lb-text text-sm mb-8">Last updated: December 2024</p>

            <div className="space-y-4">
              <Section title="Data We Access">
                <p>When you use Obscuriboxd, we temporarily access:</p>
                <ul className="list-disc list-inside mt-2 space-y-1 text-lb-text">
                  <li>Your Letterboxd username</li>
                  <li>Your list of watched films</li>
                  <li>Your film ratings (if public)</li>
                </ul>
              </Section>

              <Section title="Data Storage">
                <p>
                  <span className="text-lb-green font-medium">We do not store your data.</span> Your information is processed in real-time 
                  and discarded when you close the page.
                </p>
              </Section>

              <Section title="Cookies">
                <p>
                  We don't use tracking cookies. Only essential cookies for site functionality may be used.
                </p>
              </Section>

              <Section title="Third Parties">
                <p>We use data from:</p>
                <ul className="list-disc list-inside mt-2 space-y-1 text-lb-text">
                  <li>
                    <a href="https://letterboxd.com/privacy/" target="_blank" rel="noopener noreferrer" className="text-lb-green hover:underline">
                      Letterboxd
                    </a> - for your film data
                  </li>
                  <li>
                    <a href="https://www.themoviedb.org/privacy-policy" target="_blank" rel="noopener noreferrer" className="text-lb-green hover:underline">
                      TMDb
                    </a> - for film metadata
                  </li>
                </ul>
              </Section>

              <Section title="Contact">
                <p>
                  Questions? Visit the <Link href="/about" className="text-lb-green hover:underline">About page</Link>.
                </p>
              </Section>

              <div className="mt-8 p-4 rounded-lg bg-lb-border/30 border border-lb-border">
                <p className="text-lb-text text-sm">
                  <strong className="text-lb-text-light">Disclaimer:</strong> Obscuriboxd is not affiliated with Letterboxd or TMDb.
                </p>
              </div>
            </div>
          </motion.div>
        </div>
      </main>

      {/* Footer */}
      <footer className="py-4 px-6 border-t border-lb-border/50">
        <div className="max-w-3xl mx-auto flex items-center justify-between text-xs text-lb-text">
          <span>Data from Letterboxd & TMDb</span>
          <div className="flex gap-4">
            <Link href="/about" className="hover:text-lb-green transition-colors">About</Link>
            <Link href="/privacy" className="text-lb-green">Privacy</Link>
          </div>
        </div>
      </footer>
    </div>
  )
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="stat-card rounded-xl p-5">
      <h2 className="font-display text-lg text-lb-white mb-3">{title}</h2>
      <div className="text-lb-text text-sm leading-relaxed">{children}</div>
    </div>
  )
}
