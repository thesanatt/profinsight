import { useState, useEffect, useRef } from 'react'
import { API_BASE } from '../config'

const emojiColors = {
  great: 'var(--green)', good: 'var(--accent)', mixed: 'var(--yellow)', caution: 'var(--orange)', poor: 'var(--red)',
}

export default function ScheduleHelper({ school, onSelect, onClose }) {
  const [input, setInput] = useState('')
  const [courseTags, setCourseTags] = useState([])
  const [suggestions, setSuggestions] = useState([])
  const [results, setResults] = useState(null)
  const [loading, setLoading] = useState(false)
  const inputRef = useRef(null)

  useEffect(() => {
    if (input.length < 2) { setSuggestions([]); return }
    const t = setTimeout(() => {
      fetch(`${API_BASE}/api/${school}/courses?search=${encodeURIComponent(input)}`)
        .then(r => r.json())
        .then(d => setSuggestions((d.courses || []).slice(0, 8)))
        .catch(() => {})
    }, 200)
    return () => clearTimeout(t)
  }, [input, school])

  const addCourse = (name) => {
    const upper = name.trim().toUpperCase()
    if (upper && !courseTags.includes(upper)) setCourseTags(prev => [...prev, upper])
    setInput('')
    setSuggestions([])
    inputRef.current?.focus()
  }

  const removeCourse = (name) => { setCourseTags(prev => prev.filter(c => c !== name)); setResults(null) }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && input.trim()) { e.preventDefault(); addCourse(input) }
    if (e.key === 'Backspace' && !input && courseTags.length > 0) removeCourse(courseTags[courseTags.length - 1])
  }

  const search = () => {
    if (courseTags.length === 0) return
    setLoading(true)
    fetch(`${API_BASE}/api/${school}/schedule?courses=${encodeURIComponent(courseTags.join(','))}`)
      .then(r => r.json())
      .then(d => { setResults(d); setLoading(false) })
      .catch(() => setLoading(false))
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <div>
          <h2 className="text-xl font-bold" style={{ color: 'var(--text-1)' }}>Schedule helper</h2>
          <p className="text-sm mt-0.5" style={{ color: 'var(--text-3)' }}>Enter courses you're considering — we'll find the best professor for each</p>
        </div>
        <button onClick={onClose} className="text-sm" style={{ color: 'var(--text-3)' }}>Close</button>
      </div>

      <div className="card p-4 mb-4">
        <div className="flex flex-wrap gap-1.5 items-center">
          {courseTags.map(c => (
            <span key={c} className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-sm font-medium"
              style={{ background: 'var(--accent-bg)', color: 'var(--accent)', border: '1px solid var(--accent-border)' }}>
              {c}
              <button onClick={() => removeCourse(c)} className="ml-0.5 opacity-60 hover:opacity-100">×</button>
            </span>
          ))}
          <div className="relative flex-1 min-w-[200px]">
            <input ref={inputRef} type="text" value={input}
              onChange={e => setInput(e.target.value.toUpperCase())}
              onKeyDown={handleKeyDown}
              placeholder={courseTags.length === 0 ? "Type a course code (e.g., EECS 281)..." : "Add another..."}
              className="w-full bg-transparent px-2 py-1 text-sm outline-none"
              style={{ color: 'var(--text-1)' }} />
            {suggestions.length > 0 && (
              <div className="absolute top-full left-0 mt-1 w-80 rounded-xl shadow-lg z-10 max-h-48 overflow-y-auto"
                style={{ background: 'var(--bg-3)', border: '1px solid var(--border)' }}>
                {suggestions.map(s => (
                  <button key={s.name} onClick={() => addCourse(s.name)}
                    className="w-full text-left px-3 py-2 text-sm flex items-center justify-between transition-colors"
                    style={{ borderBottom: '1px solid var(--border)' }}
                    onMouseEnter={e => e.currentTarget.style.background = 'var(--bg-hover)'}
                    onMouseLeave={e => e.currentTarget.style.background = 'transparent'}>
                    <span style={{ color: 'var(--text-1)' }}>{s.name}</span>
                    <span className="text-xs" style={{ color: 'var(--text-3)' }}>{s.professors.length} prof{s.professors.length !== 1 ? 's' : ''}</span>
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>
        {courseTags.length > 0 && (
          <button onClick={search} disabled={loading} className="btn-primary mt-3">
            {loading ? 'Searching...' : `Find professors for ${courseTags.length} course${courseTags.length !== 1 ? 's' : ''}`}
          </button>
        )}
      </div>

      {results && (
        <div className="space-y-6">
          {results.courses.map(course => {
            const profs = results.results[course] || []
            return (
              <div key={course}>
                <div className="flex items-center gap-3 mb-2">
                  <h3 className="text-base font-bold" style={{ color: 'var(--accent)' }}>{course}</h3>
                  <span className="text-xs" style={{ color: 'var(--text-3)' }}>{profs.length} professor{profs.length !== 1 ? 's' : ''}</span>
                </div>
                {profs.length === 0 ? (
                  <div className="card px-5 py-4 text-sm" style={{ color: 'var(--text-3)' }}>
                    No professors found for this course. Try a different format (e.g., EECS281 vs EECS 281).
                  </div>
                ) : (
                  <div className="space-y-1.5">
                    {profs.map((p, i) => {
                      const vc = emojiColors[p.verdict_emoji] || 'var(--text-3)'
                      const cr = p.course_specific?.avg_rating
                      const rColor = (cr || p.avg_rating) >= 4 ? 'var(--green)' : (cr || p.avg_rating) >= 3 ? 'var(--yellow)' : 'var(--red)'
                      const topGrade = Object.keys(p.course_specific?.grades || {})[0]
                      const aRange = p.grade_probabilities?.['A range'] || 0
                      return (
                        <div key={p.id} onClick={() => onSelect(p.id)} className="card-hover px-5 py-3.5">
                          <div className="flex items-center gap-4">
                            <span className="text-base font-bold w-5 text-right" style={{ color: i === 0 ? 'var(--accent)' : 'var(--text-3)' }}>
                              {i === 0 ? '★' : `${i + 1}`}
                            </span>
                            <div className="flex-1 min-w-0">
                              <div className="flex items-center gap-2">
                                <span className="font-semibold" style={{ color: 'var(--text-1)' }}>{p.name}</span>
                                {i === 0 && <span className="text-[10px] px-1.5 py-0.5 rounded" style={{ background: 'var(--accent-bg)', color: 'var(--accent)' }}>Best pick</span>}
                              </div>
                              {p.verdict && (
                                <div className="flex items-center gap-1.5 mt-1">
                                  <div className="w-1.5 h-1.5 rounded-full" style={{ background: vc }} />
                                  <span className="text-xs" style={{ color: vc }}>{p.verdict.split('.')[0]}</span>
                                </div>
                              )}
                            </div>
                            <div className="hidden sm:flex items-center gap-4">
                              {cr && (
                                <div className="text-center">
                                  <div className="text-base font-bold" style={{ color: rColor }}>{cr}</div>
                                  <div className="text-[10px]" style={{ color: 'var(--text-3)' }}>This course</div>
                                </div>
                              )}
                              <div className="text-center">
                                <div className="text-base font-bold" style={{ color: 'var(--text-2)' }}>{p.avg_difficulty?.toFixed(1)}</div>
                                <div className="text-[10px]" style={{ color: 'var(--text-3)' }}>Difficulty</div>
                              </div>
                              <div className="text-right text-xs" style={{ color: 'var(--text-3)' }}>
                                <div>{p.course_specific?.num_reviews} reviews</div>
                                {topGrade && <div>Common: <span style={{ color: 'var(--text-2)' }}>{topGrade}</span></div>}
                                {aRange > 0 && <div style={{ color: aRange >= 60 ? 'var(--green)' : 'var(--text-2)' }}>{aRange.toFixed(0)}% A</div>}
                              </div>
                            </div>
                          </div>
                        </div>
                      )
                    })}
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}

      {!results && courseTags.length === 0 && (
        <div className="text-center py-12">
          <div className="text-3xl mb-3">📚</div>
          <div className="text-sm" style={{ color: 'var(--text-3)' }}>Add courses and we'll show the best professor for each</div>
        </div>
      )}
    </div>
  )
}
