import { useState } from 'react'

export default function Landing({ schools, onSelectSchool }) {
  const [query, setQuery] = useState('')
  const loading = schools.length === 0
  const totalProfs = schools.reduce((s, x) => s + (x.professors || 0), 0)
  const totalReviews = schools.reduce((s, x) => s + (x.reviews || 0), 0)

  const filtered = query
    ? schools.filter(s => s.name.toLowerCase().includes(query.toLowerCase()))
    : schools

  return (
    <div className="min-h-[88vh] flex flex-col">
      <div className="flex-1 flex items-center justify-center px-4">
        <div className="max-w-xl w-full text-center">
          {loading ? (
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-medium mb-8"
              style={{ background: 'var(--bg-2)', color: 'var(--text-3)' }}>
              <div className="w-3 h-3 border-2 border-t-transparent rounded-full animate-spin" style={{ borderColor: 'var(--accent)', borderTopColor: 'transparent' }} />
              Loading schools...
            </div>
          ) : (
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-medium mb-8"
              style={{ background: 'var(--accent-bg)', color: 'var(--accent)' }}>
              <span className="w-1.5 h-1.5 rounded-full animate-pulse" style={{ background: 'var(--green)' }} />
              {schools.length} universities · {totalProfs.toLocaleString()} professors · {totalReviews.toLocaleString()} reviews
            </div>
          )}

          <h1 className="text-4xl sm:text-5xl font-bold tracking-tight leading-[1.15]" style={{ color: 'var(--text-1)' }}>
            Know your professor
            <br />
            <span style={{ color: 'var(--accent)' }}>before you register</span>
          </h1>

          <p className="mt-5 text-base max-w-md mx-auto leading-relaxed" style={{ color: 'var(--text-2)' }}>
            Bayesian ML analysis of student reviews. Confidence levels, trend analysis, grade predictions, and personalized matching.
          </p>

          {/* School search */}
          <div className="mt-10 relative max-w-sm mx-auto">
            <svg className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4" style={{ color: 'var(--text-3)' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
            <input
              type="text"
              placeholder="Search your school..."
              value={query}
              onChange={e => setQuery(e.target.value)}
              className="input-dark w-full pl-10 py-3 text-base"
              autoFocus
            />
          </div>

          {/* School list */}
          <div className="mt-4 max-w-sm mx-auto text-left max-h-64 overflow-y-auto">
            {filtered.map(s => (
              <button key={s.slug} onClick={() => onSelectSchool(s.slug)}
                className="w-full flex items-center justify-between px-4 py-2.5 rounded-lg text-sm transition-all"
                style={{ color: 'var(--text-2)' }}
                onMouseEnter={e => { e.currentTarget.style.background = 'var(--bg-3)'; e.currentTarget.style.color = 'var(--text-1)' }}
                onMouseLeave={e => { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.color = 'var(--text-2)' }}>
                <span>{s.name}</span>
                <span className="text-xs" style={{ color: 'var(--text-3)' }}>{s.professors} profs</span>
              </button>
            ))}
            {filtered.length === 0 && (
              <div className="text-center py-6 text-sm" style={{ color: 'var(--text-3)' }}>
                No schools match "{query}"
              </div>
            )}
          </div>

          {/* Feature pills */}
          <div className="mt-10 flex flex-wrap justify-center gap-2">
            {['Bayesian confidence', 'Rating trends', 'Professor matching', 'Sentiment analysis', 'Grade predictions', 'Compare mode'].map(f => (
              <span key={f} className="px-2.5 py-1 rounded-md text-[11px]"
                style={{ background: 'var(--bg-2)', color: 'var(--text-3)', border: '1px solid var(--border)' }}>{f}</span>
            ))}
          </div>
        </div>
      </div>

      <div className="text-center py-5 text-xs" style={{ color: 'var(--text-3)' }}>
        No LLM APIs. No monthly costs. Just math.
        <span className="mx-2">·</span>
        <a href="https://github.com/thesanatt/profinsight" target="_blank" rel="noopener" style={{ color: 'var(--accent)' }}>GitHub</a>
      </div>
    </div>
  )
}
