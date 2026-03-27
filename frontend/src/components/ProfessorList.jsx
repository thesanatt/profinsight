function getRedFlags(prof) {
  const flags = []
  if (prof.would_take_again_pct != null && prof.would_take_again_pct >= 0 && prof.would_take_again_pct < 35)
    flags.push('Low retake rate')
  if (prof.avg_rating != null && prof.avg_rating < 2.5)
    flags.push('Very low ratings')
  if (prof.avg_difficulty != null && prof.avg_difficulty >= 4.5)
    flags.push('Extremely difficult')
  if (prof.verdict_emoji === 'poor')
    flags.push('Poor reviews')
  if (prof.trend_summary && prof.trend_summary.toLowerCase().includes('declining'))
    flags.push('Trending down')
  return flags
}

function GradeBar({ probs }) {
  if (!probs) return null
  const a = probs['A range'] || 0, b = probs['B range'] || 0, c = probs['C range'] || 0
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1.5 rounded-full overflow-hidden flex" style={{ background: 'var(--bg-3)' }}>
        {a > 0 && <div className="h-full" style={{ width: `${a}%`, background: 'var(--green)' }} />}
        {b > 0 && <div className="h-full" style={{ width: `${b}%`, background: 'var(--yellow)' }} />}
        {c > 0 && <div className="h-full" style={{ width: `${c}%`, background: 'var(--orange)' }} />}
      </div>
      <span className="text-xs w-12 text-right" style={{ color: 'var(--text-3)' }}>{a > 0 ? `${a.toFixed(0)}% A` : ''}</span>
    </div>
  )
}

const emojiColors = {
  great: 'var(--green)', good: 'var(--accent)', mixed: 'var(--yellow)', caution: 'var(--orange)', poor: 'var(--red)',
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
        const flags = getRedFlags(prof)
        const vc = emojiColors[prof.verdict_emoji] || 'var(--text-3)'
        const rColor = prof.avg_rating >= 4 ? 'var(--green)' : prof.avg_rating >= 3 ? 'var(--yellow)' : 'var(--red)'
        return (
          <div key={prof.id} onClick={() => onSelect(prof.id)} className="card-hover px-5 py-3.5">
            <div className="flex items-center gap-4">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="font-semibold" style={{ color: 'var(--text-1)' }}>{prof.name}</span>
                  {prof.confidence_level && (
                    <div className="flex gap-0.5">
                      {[1,2,3,4].map(i => (
                        <div key={i} className="w-1.5 h-1.5 rounded-full"
                          style={{ background: i <= {'Very high':4,'High':3,'Moderate':2,'Low':1}[prof.confidence_level] ? 'var(--accent)' : 'var(--border)' }} />
                      ))}
                    </div>
                  )}
                </div>
                <div className="text-xs mt-0.5" style={{ color: 'var(--text-3)' }}>{prof.department}</div>
                {prof.verdict && (
                  <div className="flex items-center gap-1.5 mt-1.5">
                    <div className="w-1.5 h-1.5 rounded-full" style={{ background: vc }} />
                    <span className="text-xs" style={{ color: vc }}>{prof.verdict.split('.')[0]}</span>
                  </div>
                )}
                {flags.length > 0 && (
                  <div className="flex gap-1.5 mt-1">
                    {flags.map(f => <span key={f} className="badge-red text-[10px]">{f}</span>)}
                  </div>
                )}
              </div>
              <div className="flex items-center gap-4">
                <div className="text-center">
                  <div className="text-lg font-bold" style={{ color: rColor }}>{prof.avg_rating?.toFixed(1)}</div>
                  <div className="text-[10px]" style={{ color: 'var(--text-3)' }}>Quality</div>
                </div>
                <div className="text-center">
                  <div className="text-lg font-bold" style={{ color: 'var(--text-2)' }}>{prof.avg_difficulty?.toFixed(1)}</div>
                  <div className="text-[10px]" style={{ color: 'var(--text-3)' }}>Difficulty</div>
                </div>
              </div>
              <div className="hidden sm:flex flex-col items-end gap-1 w-36">
                <GradeBar probs={prof.grade_probabilities} />
                <div className="flex items-center gap-3 text-xs" style={{ color: 'var(--text-3)' }}>
                  <span>{prof.num_ratings} reviews</span>
                  {prof.would_take_again_pct >= 0 && (
                    <span style={{ color: prof.would_take_again_pct >= 60 ? 'var(--green)' : prof.would_take_again_pct >= 40 ? 'var(--yellow)' : 'var(--red)' }}>
                      {prof.would_take_again_pct?.toFixed(0)}% again
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
