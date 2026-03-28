function profGrade(prob) {
  if (prob == null) return { letter: '?', color: 'var(--text-3)' }
  if (prob >= 0.9) return { letter: 'A+', color: 'var(--green)' }
  if (prob >= 0.8) return { letter: 'A', color: 'var(--green)' }
  if (prob >= 0.7) return { letter: 'B+', color: '#8be78b' }
  if (prob >= 0.6) return { letter: 'B', color: 'var(--yellow)' }
  if (prob >= 0.45) return { letter: 'C+', color: 'var(--yellow)' }
  if (prob >= 0.3) return { letter: 'C', color: 'var(--orange)' }
  return { letter: 'D', color: 'var(--red)' }
}

function getFlags(prof) {
  const f = []
  if (prof.would_take_again_pct != null && prof.would_take_again_pct >= 0 && prof.would_take_again_pct < 35)
    f.push('Low retake rate')
  if (prof.avg_rating != null && prof.avg_rating < 2.5)
    f.push('Low ratings')
  if (prof.avg_difficulty != null && prof.avg_difficulty >= 4.5)
    f.push('Very hard')
  if (prof.trend_summary && prof.trend_summary.toLowerCase().includes('declining'))
    f.push('Getting worse')
  return f
}

function diffLabel(d) {
  if (d == null) return ''
  if (d >= 4.5) return 'Very hard'
  if (d >= 3.5) return 'Hard'
  if (d >= 2.5) return 'Medium'
  return 'Easy'
}

export default function ProfessorList({ professors, loading, onSelect }) {
  if (loading) return (
    <div className="flex justify-center py-20">
      <div className="w-5 h-5 border-2 border-t-transparent rounded-full animate-spin" style={{ borderColor: 'var(--accent)', borderTopColor: 'transparent' }} />
    </div>
  )
  if (!professors.length) return <div className="text-center py-16 text-sm" style={{ color: 'var(--text-3)' }}>No professors found</div>

  return (
    <div className="space-y-1.5">
      {professors.map(prof => {
        const flags = getFlags(prof)
        const grade = profGrade(prof.bayesian_good_prob)
        const aPct = prof.grade_probabilities?.['A range'] || 0
        const dLabel = diffLabel(prof.avg_difficulty)
        const wta = prof.would_take_again_pct

        return (
          <div key={prof.id} onClick={() => onSelect(prof.id)} className="card-hover px-5 py-4">
            <div className="flex items-center gap-4">
              {/* Professor grade */}
              <div className="w-11 h-11 rounded-xl flex items-center justify-center text-base font-bold flex-shrink-0"
                style={{ background: `${grade.color}15`, color: grade.color, border: `1px solid ${grade.color}30` }}>
                {grade.letter}
              </div>

              {/* Name + quick info */}
              <div className="flex-1 min-w-0">
                <div className="font-semibold" style={{ color: 'var(--text-1)' }}>{prof.name}</div>
                <div className="text-xs mt-0.5" style={{ color: 'var(--text-3)' }}>{prof.department}</div>
                <div className="flex flex-wrap items-center gap-2 mt-1.5">
                  {prof.verdict && (
                    <span className="text-xs" style={{ color: 'var(--text-2)' }}>{prof.verdict.split('.')[0].split(',')[0]}</span>
                  )}
                  {flags.length > 0 && flags.map(f => (
                    <span key={f} className="badge-red text-[10px]">{f}</span>
                  ))}
                </div>
              </div>

              {/* Key stats */}
              <div className="hidden sm:flex items-center gap-5">
                <div className="text-center">
                  <div className="text-sm font-bold" style={{ color: prof.avg_rating >= 4 ? 'var(--green)' : prof.avg_rating >= 3 ? 'var(--yellow)' : 'var(--red)' }}>
                    {prof.avg_rating?.toFixed(1)}/5
                  </div>
                  <div className="text-[10px]" style={{ color: 'var(--text-3)' }}>Rating</div>
                </div>
                <div className="text-center">
                  <div className="text-sm font-semibold" style={{ color: prof.avg_difficulty >= 4 ? 'var(--orange)' : 'var(--text-2)' }}>{dLabel}</div>
                  <div className="text-[10px]" style={{ color: 'var(--text-3)' }}>Difficulty</div>
                </div>
                <div className="text-center">
                  <div className="text-sm font-semibold" style={{ color: aPct >= 60 ? 'var(--green)' : aPct >= 40 ? 'var(--yellow)' : 'var(--text-2)' }}>
                    {aPct > 0 ? `${aPct.toFixed(0)}%` : '?'}
                  </div>
                  <div className="text-[10px]" style={{ color: 'var(--text-3)' }}>Get an A</div>
                </div>
                <div className="text-center">
                  <div className="text-sm font-semibold" style={{ color: wta >= 60 ? 'var(--green)' : wta >= 40 ? 'var(--yellow)' : wta >= 0 ? 'var(--red)' : 'var(--text-3)' }}>
                    {wta >= 0 ? `${wta?.toFixed(0)}%` : '?'}
                  </div>
                  <div className="text-[10px]" style={{ color: 'var(--text-3)' }}>Would retake</div>
                </div>
                <div className="text-xs" style={{ color: 'var(--text-3)' }}>
                  {prof.num_ratings} reviews
                  {prof.confidence_level === 'Low' && <div className="text-[10px]" style={{ color: 'var(--orange)' }}>Limited data</div>}
                </div>
              </div>
            </div>
          </div>
        )
      })}
    </div>
  )
}
