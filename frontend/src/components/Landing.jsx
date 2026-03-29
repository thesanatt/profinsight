import { useState } from 'react'

export default function Landing({ schools, onSelectSchool }) {
  const [query, setQuery] = useState('')
  const [focused, setFocused] = useState(false)
  const loading = schools.length === 0

  // Sort: UMich first, then alphabetical
  const sorted = [...schools].sort((a, b) => {
    if (a.slug === 'umich') return -1
    if (b.slug === 'umich') return 1
    return a.name.localeCompare(b.name)
  })

  const filtered = query
    ? sorted.filter(s => s.name.toLowerCase().includes(query.toLowerCase()))
    : sorted

  const showList = focused || query

  return (
    <div className="min-h-[88vh] flex flex-col">
      <div className="flex-1 flex items-center justify-center px-4">
        <div className="max-w-xl w-full text-center">
          {loading && (
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-medium mb-8"
              style={{ background: 'var(--bg-2)', color: 'var(--text-3)' }}>
              <div className="w-3 h-3 border-2 border-t-transparent rounded-full animate-spin" style={{ borderColor: 'var(--accent)', borderTopColor: 'transparent' }} />
              Loading...
            </div>
          )}

          <h1 className="text-4xl sm:text-5xl font-bold tracking-tight leading-[1.15]" style={{ color: 'var(--text-1)' }}>
            Know your professor
            <br />
            <span style={{ color: 'var(--accent)' }}>before you register</span>
          </h1>

          <p className="mt-5 text-base max-w-md mx-auto leading-relaxed" style={{ color: 'var(--text-2)' }}>
            Go beyond star ratings. See how confident we are in a professor's score,
            whether they're getting better or worse, and which one actually fits how you learn.
          </p>

          <div className="mt-10 relative max-w-sm mx-auto">
            <svg className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4" style={{ color: 'var(--text-3)' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
            <input
              type="text"
              placeholder="Search your school..."
              value={query}
              onChange={e => setQuery(e.target.value)}
              onFocus={() => setFocused(true)}
              onBlur={() => setTimeout(() => setFocused(false), 200)}
              className="input-dark w-full pl-10 py-3 text-base"
            />

            {showList && !loading && (
              <div className="absolute top-full left-0 right-0 mt-2 rounded-xl max-h-72 overflow-y-auto"
                style={{ background: 'var(--bg-1)', border: '1px solid var(--border)', boxShadow: '0 8px 32px rgba(0,0,0,0.3)' }}>
                {filtered.map(s => {
                  const isUmich = s.slug === 'umich'
                  return (
                    <button key={s.slug} onClick={() => onSelectSchool(s.slug)}
                      className="w-full flex items-center justify-between px-4 py-2.5 text-sm transition-all"
                      style={{
                        color: isUmich ? 'var(--accent)' : 'var(--text-2)',
                        borderBottom: '1px solid var(--border)',
                        background: isUmich ? 'var(--accent-bg)' : 'transparent',
                      }}
                      onMouseEnter={e => { if (!isUmich) { e.currentTarget.style.background = 'var(--bg-3)'; e.currentTarget.style.color = 'var(--text-1)' }}}
                      onMouseLeave={e => { if (!isUmich) { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.color = 'var(--text-2)' }}}>
                      <span className={isUmich ? 'font-medium' : ''}>{s.name}</span>
                      <span className="text-xs" style={{ color: 'var(--text-3)' }}>{s.professors} profs</span>
                    </button>
                  )
                })}
                {filtered.length === 0 && (
                  <div className="text-center py-6 text-sm" style={{ color: 'var(--text-3)' }}>
                    No schools match "{query}"
                  </div>
                )}
              </div>
            )}
          </div>

          {!showList && !loading && (
            <div className="mt-10 flex flex-wrap justify-center gap-2">
              {['Confidence ratings', 'Grade predictions', 'Semester optimizer', 'Professor matching', 'Trend analysis', 'Side-by-side compare'].map(f => (
                <span key={f} className="px-2.5 py-1 rounded-md text-[11px]"
                  style={{ background: 'var(--bg-2)', color: 'var(--text-3)', border: '1px solid var(--border)' }}>{f}</span>
              ))}
            </div>
          )}
        </div>
      </div>

      <div className="text-center py-5 text-xs" style={{ color: 'var(--text-3)' }}>
        Free to use
      </div>
    </div>
  )
}
