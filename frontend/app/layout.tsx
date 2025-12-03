import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'Obscuriboxd | How Obscure Is Your Film Taste?',
  description: 'Discover how unique your Letterboxd film taste really is. Get your obscurity score and detailed insights into your viewing habits.',
  keywords: ['Letterboxd', 'film', 'movies', 'obscure', 'taste', 'analysis'],
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body className="gradient-bg">
        {/* Film grain overlay */}
        <div className="film-grain" aria-hidden="true" />
        
        {/* Cinematic vignette */}
        <div className="vignette" aria-hidden="true" />
        
        {/* Main content */}
        <main className="relative z-10">
          {children}
        </main>
      </body>
    </html>
  )
}



