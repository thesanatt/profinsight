const verdictConfig = {
  great:   { bg: 'bg-emerald-50', border: 'border-emerald-200', text: 'text-emerald-700', dot: 'bg-emerald-500' },
  good:    { bg: 'bg-blue-50', border: 'border-blue-200', text: 'text-blue-700', dot: 'bg-blue-500' },
  mixed:   { bg: 'bg-amber-50', border: 'border-amber-200', text: 'text-amber-700', dot: 'bg-amber-500' },
  caution: { bg: 'bg-orange-50', border: 'border-orange-200', text: 'text-orange-700', dot: 'bg-orange-500' },
  poor:    { bg: 'bg-red-50', border: 'border-red-200', text: 'text-red-700', dot: 'bg-red-500' },
}

function RatingPill({ value, label }) {
  if (value == null) return null
  const color =
    value >= 4.0 ? 'text-emerald-600 bg-emerald-50' :
    value >= 3.0 ? 'text-amber-600 bg-amber-50' :
    'text-red-500 bg-red-50'
  return (
    <div className="text-center">
      <div className={`text-lg font-bold ${color} rounded-lg px-2 py-0.5`}>{value.toFixed(1)}</div>
      <div className="text-[10px] text-gray-400 mt-0.5">{label}</div>
    </div>
  )
}

function GradeOdds({ probs }) {
  if (!probs || !probs['A range']) return null
  const a = probs['A range'] || 0
  return (
    <div className="flex items-center gap-1.5">
      <div className="flex-1 h-1.5 bg-gray-100 rounded-full overflow-hidden flex">
        {a > 0 && <div className="h-full bg-emerald-400 rounded-l-full" style={{ width: `${a}%` }} />}
        {(probs['B range'] || 0) > 0 && <div className="h-full bg-amber-400" style={{ width: `${probs['B range']}%` }} />}
        {(probs['C range'] || 0) > 0 && <div className="h-full bg-orange-400" style={{ width: `${probs['C range']}%` }} />}
        {(probs['D/F'] || 0) > 0 && <div className="h-full bg-red-400 rounded-r-full" style={{ width: `${probs['D/F']}%` }} />}
      </div>
      <span className="text-xs text-gray-500 w-12 text-right">{a.toFixed(0)}% A</span>
    </div>
  )
}

function ConfidenceDots({ level }) {
  const levels = { 'Very high': 4, 'High': 3, 'Moderate': 2, 'Low': 1 }
  const n = levels[level] || 0
  return (
    <div className="flex gap-0.5" title={`Confidence: ${level}`}>
      {[1,2,3,4].map(i => (
        <div key={i} className={`w-1.5 h-1.5 rounded-full ${i <= n ? 'bg-indigo-500' : 'bg-gray-200'}`} />
      ))}
    </div>
  )
}

export default function ProfessorList({ professors, loading, onSelect }) {
  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="w-5 h-5 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
      </div>
    )
  }

  if (!professors.length) {
    return <div className="text-center py-16 text-gray-400 text-sm">No professors found</div>
  }

  return (
    <div className="space-y-2">
      {professors.map(prof => {
        const vc = verdictConfig[prof.verdict_emoji] || verdictConfig.mixed
        return (
          <div key={prof.id} onClick={() => onSelect(prof.id)}
            className="bg-white rounded-xl border border-gray-100 hover:border-gray-200 hover:shadow-sm transition-all cursor-pointer px-5 py-4">
            <div className="flex items-center gap-4">
              {/* Left: Name + verdict */}
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="font-semibold text-gray-900">{prof.name}</span>
                  <ConfidenceDots level={prof.confidence_level} />
                </div>
                <div className="text-xs text-gray-400 mt-0.5">{prof.department}</div>
                {prof.verdict && (
                  <div className={`inline-flex items-center gap-1.5 mt-1.5 px-2 py-0.5 rounded-md text-xs ${vc.bg} ${vc.text}`}>
                    <div className={`w-1.5 h-1.5 rounded-full ${vc.dot}`} />
                    {prof.verdict.split('.')[0]}
                  </div>
                )}
              </div>

              {/* Middle: Ratings */}
              <div className="flex items-center gap-3">
                <RatingPill value={prof.avg_rating} label="Quality" />
                <RatingPill value={prof.avg_difficulty} label="Difficulty" />
              </div>

              {/* Right: Grade odds + take again */}
              <div className="hidden sm:flex flex-col items-end gap-1.5 w-40">
                <GradeOdds probs={prof.grade_probabilities} />
                <div className="flex items-center gap-3 text-xs">
                  <span className="text-gray-400">{prof.num_ratings} reviews</span>
                  {prof.would_take_again_pct != null && prof.would_take_again_pct >= 0 && (
                    <span className={`font-medium ${prof.would_take_again_pct >= 60 ? 'text-emerald-600' : prof.would_take_again_pct >= 40 ? 'text-amber-600' : 'text-red-500'}`}>
                      {prof.would_take_again_pct.toFixed(0)}% again
                    </span>
                  )}
                </div>
              </div>
            </div>
          </div>
        )
      })}
    </div>
  )
}
