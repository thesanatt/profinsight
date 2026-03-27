export default function Landing({ schools, onSelectSchool }) {
  const totalProfs = schools.reduce((s, x) => s + (x.professors || 0), 0)
  const totalReviews = schools.reduce((s, x) => s + (x.reviews || 0), 0)

  return (
    <div className="min-h-[85vh] flex flex-col">
      {/* Hero */}
      <div className="flex-1 flex items-center justify-center px-4">
        <div className="max-w-2xl text-center">
          <div className="inline-flex items-center gap-2 px-3 py-1 bg-indigo-50 text-indigo-600 rounded-full text-xs font-medium mb-6">
            <span className="w-1.5 h-1.5 bg-indigo-500 rounded-full animate-pulse" />
            {schools.length} universities · {totalProfs.toLocaleString()} professors · {totalReviews.toLocaleString()} reviews analyzed
          </div>

          <h1 className="text-4xl sm:text-5xl font-bold text-gray-900 tracking-tight leading-tight">
            Know your professor<br />
            <span className="text-indigo-600">before you register</span>
          </h1>

          <p className="mt-4 text-lg text-gray-500 max-w-lg mx-auto leading-relaxed">
            Bayesian ML analysis of student reviews. Not just ratings — confidence levels, 
            trend analysis, grade predictions, and personalized professor matching.
          </p>

          {/* School buttons */}
          <div className="mt-8">
            <p className="text-xs text-gray-400 uppercase tracking-wider mb-3">Choose your school</p>
            <div className="flex flex-wrap justify-center gap-2">
              {schools.map(s => (
                <button key={s.slug} onClick={() => onSelectSchool(s.slug)}
                  className="px-4 py-2.5 bg-white border border-gray-200 rounded-xl text-sm font-medium text-gray-700 hover:border-indigo-300 hover:text-indigo-600 hover:shadow-sm transition-all">
                  {s.name}
                  <span className="text-gray-400 ml-1.5 text-xs">{s.professors}</span>
                </button>
              ))}
            </div>
          </div>

          {/* Feature pills */}
          <div className="mt-10 flex flex-wrap justify-center gap-3">
            {[
              { icon: '📊', text: 'Bayesian confidence ratings' },
              { icon: '📈', text: 'Rating trends over time' },
              { icon: '🎯', text: 'Personalized professor matching' },
              { icon: '📝', text: 'AI-free sentiment analysis' },
              { icon: '🅰️', text: 'Grade probability estimates' },
              { icon: '⚖️', text: 'Side-by-side comparison' },
            ].map(f => (
              <span key={f.text} className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-gray-50 rounded-lg text-xs text-gray-600">
                <span>{f.icon}</span> {f.text}
              </span>
            ))}
          </div>
        </div>
      </div>

      {/* Footer */}
      <div className="text-center py-6 text-xs text-gray-400">
        Built with Beta-Binomial posteriors, Naive Bayes classification, and Gaussian Process Regression.
        <br />
        No LLM APIs. No monthly costs. Just math.
        <span className="mx-2">·</span>
        <a href="https://github.com/thesanatt/profinsight" target="_blank" rel="noopener"
          className="text-indigo-500 hover:text-indigo-700">GitHub</a>
      </div>
    </div>
  )
}
