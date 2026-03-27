export default function Landing({ schools, onSelectSchool }) {
  const totalProfs = schools.reduce((s, x) => s + (x.professors || 0), 0)
  const totalReviews = schools.reduce((s, x) => s + (x.reviews || 0), 0)

  return (
    <div className="min-h-[85vh] flex flex-col">
      <div className="flex-1 flex items-center justify-center px-4">
        <div className="max-w-2xl text-center">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-medium mb-6"
            style={{ background: 'var(--accent-bg)', color: 'var(--accent)' }}>
            <span className="w-1.5 h-1.5 rounded-full animate-pulse" style={{ background: 'var(--accent)' }} />
            {schools.length} universities · {totalProfs.toLocaleString()} professors · {totalReviews.toLocaleString()} reviews
          </div>
          <h1 className="text-4xl sm:text-5xl font-bold tracking-tight leading-tight"
            style={{ color: 'var(--text-primary)' }}>
            Know your professor<br />
            <span style={{ color: 'var(--accent)' }}>before you register</span>
          </h1>
          <p className="mt-4 text-lg max-w-lg mx-auto leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
            Bayesian ML analysis of student reviews. Not just ratings — confidence levels,
            trend analysis, grade predictions, and personalized matching.
          </p>
          <div className="mt-8">
            <p className="text-xs uppercase tracking-wider mb-3" style={{ color: 'var(--text-tertiary)' }}>Choose your school</p>
            <div className="flex flex-wrap justify-center gap-2">
              {schools.map(s => (
                <button key={s.slug} onClick={() => onSelectSchool(s.slug)}
                  className="card-hover px-4 py-2.5 text-sm font-medium" style={{ color: 'var(--text-secondary)' }}>
                  {s.name}
                  <span className="ml-1.5 text-xs" style={{ color: 'var(--text-tertiary)' }}>{s.professors}</span>
                </button>
              ))}
            </div>
          </div>
          <div className="mt-10 flex flex-wrap justify-center gap-2">
            {['📊 Bayesian confidence', '📈 Rating trends', '🎯 Professor matching', '📝 Sentiment analysis', '🅰️ Grade predictions', '⚖️ Side-by-side compare'].map(f => (
              <span key={f} className="px-3 py-1.5 rounded-lg text-xs"
                style={{ background: 'var(--bg-tertiary)', color: 'var(--text-tertiary)' }}>{f}</span>
            ))}
          </div>
        </div>
      </div>
      <div className="text-center py-6 text-xs" style={{ color: 'var(--text-tertiary)' }}>
        No LLM APIs. No monthly costs. Just math.
        <span className="mx-2">·</span>
        <a href="https://github.com/thesanatt/profinsight" target="_blank" rel="noopener" style={{ color: 'var(--accent)' }}>GitHub</a>
      </div>
    </div>
  )
}
