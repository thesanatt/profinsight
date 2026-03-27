import { useState, useEffect, useRef } from 'react'
import { API_BASE } from '../config'

const emojiColors = {
  great: 'var(--green)', good: 'var(--accent)', mixed: 'var(--yellow)', caution: 'var(--orange)', poor: 'var(--red)',
}

export default function SemesterOptimizer({ school, onSelect, onClose }) {
  const [input, setInput] = useState('')
  const [courseTags, setCourseTags] = useState([])
  const [suggestions, setSuggestions] = useState([])
  const [preference, setPreference] = useState('balanced')
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const inputRef = useRef(null)

  useEffect(() => {
    if (input.length < 2) { setSuggestions([]); return }
    const t = setTimeout(() => {
      fetch(`${API_BASE}/api/${school}/courses?search=${encodeURIComponent(input)}`)
        .then(r => r.json()).then(d => setSuggestions((d.courses || []).slice(0, 6))).catch(() => {})
    }, 200)
    return () => clearTimeout(t)
  }, [input, school])

  const addCourse = (name) => {
    const upper = name.trim().toUpperCase()
    if (upper && !courseTags.includes(upper)) setCourseTags(prev => [...prev, upper])
    setInput(''); setSuggestions([]); inputRef.current?.focus()
  }
  const removeCourse = (name) => { setCourseTags(prev => prev.filter(c => c !== name)); setResult(null) }
  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && input.trim()) { e.preventDefault(); addCourse(input) }
    if (e.key === 'Backspace' && !input && courseTags.length > 0) removeCourse(courseTags[courseTags.length - 1])
  }

  const optimize = () => {
    if (courseTags.length === 0) return
    setLoading(true)
    fetch(`${API_BASE}/api/${school}/optimize?courses=${encodeURIComponent(courseTags.join(','))}&preference=${preference}`)
      .then(r => r.json()).then(d => { setResult(d); setLoading(false) }).catch(() => setLoading(false))
  }

  const prefOptions = [
    { key: 'easy', label: 'Easy semester', desc: 'Prioritize low difficulty and high grades' },
    { key: 'balanced', label: 'Balanced', desc: 'Best mix of quality, grades, and difficulty' },
    { key: 'challenge', label: 'Challenge me', desc: 'Prioritize teaching quality over easy grades' },
  ]

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <div>
          <h2 className="text-xl font-bold" style={{ color: 'var(--text-1)' }}>Semester optimizer</h2>
          <p className="text-sm mt-0.5" style={{ color: 'var(--text-3)' }}>Enter your courses and we'll build your ideal professor lineup</p>
        </div>
        <button onClick={onClose} className="text-sm" style={{ color: 'var(--text-3)' }}>Close</button>
      </div>

      {/* Course input */}
      <div className="card p-4 mb-3">
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
              onChange={e => setInput(e.target.value.toUpperCase())} onKeyDown={handleKeyDown}
              placeholder={courseTags.length === 0 ? "Type course codes (e.g., EECS 281)..." : "Add another..."}
              className="w-full bg-transparent px-2 py-1 text-sm outline-none" style={{ color: 'var(--text-1)' }} />
            {suggestions.length > 0 && (
              <div className="absolute top-full left-0 mt-1 w-72 rounded-xl shadow-lg z-10 max-h-48 overflow-y-auto"
                style={{ background: 'var(--bg-3)', border: '1px solid var(--border)' }}>
                {suggestions.map(s => (
                  <button key={s.name} onClick={() => addCourse(s.name)}
                    className="w-full text-left px-3 py-2 text-sm flex justify-between transition-colors"
                    style={{ borderBottom: '1px solid var(--border)' }}
                    onMouseEnter={e => e.currentTarget.style.background = 'var(--bg-hover)'}
                    onMouseLeave={e => e.currentTarget.style.background = 'transparent'}>
                    <span style={{ color: 'var(--text-1)' }}>{s.name}</span>
                    <span className="text-xs" style={{ color: 'var(--text-3)' }}>{s.professors.length} profs</span>
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>
        {courseTags.length === 0 && !input && (
          <p className="text-xs mt-2" style={{ color: 'var(--text-3)' }}>Type a course code and press Enter</p>
        )}
      </div>

      {/* Preference selector */}
      {courseTags.length > 0 && !result && (
        <div className="card p-4 mb-3">
          <div className="text-sm font-medium mb-3" style={{ color: 'var(--text-1)' }}>What kind of semester do you want?</div>
          <div className="flex gap-2">
            {prefOptions.map(p => (
              <button key={p.key} onClick={() => setPreference(p.key)}
                className="flex-1 p-3 rounded-lg text-left transition-all"
                style={preference === p.key
                  ? { background: 'var(--accent-bg)', border: '1px solid var(--accent-border)' }
                  : { background: 'var(--bg-2)', border: '1px solid var(--border)' }}>
                <div className="text-sm font-medium" style={{ color: preference === p.key ? 'var(--accent)' : 'var(--text-2)' }}>{p.label}</div>
                <div className="text-[11px] mt-0.5" style={{ color: 'var(--text-3)' }}>{p.desc}</div>
              </button>
            ))}
          </div>
          <button onClick={optimize} disabled={loading} className="btn-primary w-full mt-3 py-2.5 justify-center">
            {loading ? 'Optimizing...' : `Optimize my ${courseTags.length} courses`}
          </button>
        </div>
      )}

      {/* Results */}
      {result && (
        <div className="space-y-4">
          {/* Semester prediction card */}
          <div className="card p-5">
            <h3 className="font-semibold text-sm mb-3" style={{ color: 'var(--text-1)' }}>Your optimized semester</h3>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              <div>
                <div className="text-2xl font-bold" style={{ color: result.semester_prediction.avg_difficulty >= 3.5 ? 'var(--orange)' : 'var(--green)' }}>
                  {result.semester_prediction.avg_difficulty?.toFixed(1) || '—'}
                </div>
                <div className="text-[10px] uppercase tracking-wider" style={{ color: 'var(--text-3)' }}>Avg difficulty</div>
              </div>
              <div>
                <div className="text-2xl font-bold" style={{ color: result.semester_prediction.avg_quality >= 4 ? 'var(--green)' : 'var(--yellow)' }}>
                  {result.semester_prediction.avg_quality?.toFixed(1) || '—'}
                </div>
                <div className="text-[10px] uppercase tracking-wider" style={{ color: 'var(--text-3)' }}>Avg quality</div>
              </div>
              <div>
                <div className="text-2xl font-bold" style={{ color: result.semester_prediction.estimated_gpa >= 3.5 ? 'var(--green)' : result.semester_prediction.estimated_gpa >= 3.0 ? 'var(--yellow)' : 'var(--red)' }}>
                  {result.semester_prediction.estimated_gpa?.toFixed(2) || '—'}
                </div>
                <div className="text-[10px] uppercase tracking-wider" style={{ color: 'var(--text-3)' }}>Est. GPA</div>
              </div>
              <div>
                <div className="text-sm font-semibold mt-1" style={{ color: 'var(--text-1)' }}>{result.semester_prediction.difficulty_label}</div>
                <div className="text-[10px] uppercase tracking-wider" style={{ color: 'var(--text-3)' }}>Outlook</div>
              </div>
            </div>

            {/* Warnings */}
            {result.warnings?.length > 0 && (
              <div className="mt-3 space-y-1">
                {result.warnings.map((w, i) => (
                  <div key={i} className="text-xs px-2.5 py-1.5 rounded-md" style={{ background: 'var(--yellow-bg)', color: 'var(--yellow)' }}>
                    ⚠ {w}
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Recommended professors per course */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <h3 className="font-semibold text-sm" style={{ color: 'var(--text-1)' }}>Recommended lineup</h3>
              <button onClick={() => { setResult(null) }} className="text-xs" style={{ color: 'var(--accent)' }}>Adjust preferences</button>
            </div>
            <div className="space-y-2">
              {result.courses.map(course => {
                const rec = result.recommended[course]
                const alts = result.alternatives[course] || []
                if (!rec) return (
                  <div key={course} className="card px-5 py-3">
                    <span className="text-sm font-bold" style={{ color: 'var(--accent)' }}>{course}</span>
                    <span className="text-xs ml-3" style={{ color: 'var(--text-3)' }}>No professor data found</span>
                  </div>
                )
                const vc = emojiColors[rec.verdict_emoji] || 'var(--text-3)'
                const rColor = (rec.course_rating || rec.avg_rating) >= 4 ? 'var(--green)' : (rec.course_rating || rec.avg_rating) >= 3 ? 'var(--yellow)' : 'var(--red)'
                return (
                  <div key={course} className="card p-4">
                    <div className="flex items-center gap-2 mb-2">
                      <span className="text-sm font-bold" style={{ color: 'var(--accent)' }}>{course}</span>
                      <span className="text-[10px] px-1.5 py-0.5 rounded" style={{ background: 'var(--green-bg)', color: 'var(--green)' }}>Recommended</span>
                    </div>
                    <div onClick={() => onSelect(rec.id)} className="flex items-center gap-4 cursor-pointer rounded-lg p-2 -mx-2 transition-colors"
                      style={{ }}
                      onMouseEnter={e => e.currentTarget.style.background = 'var(--bg-hover)'}
                      onMouseLeave={e => e.currentTarget.style.background = 'transparent'}>
                      <div className="flex-1">
                        <div className="font-semibold" style={{ color: 'var(--text-1)' }}>{rec.name}</div>
                        {rec.verdict && (
                          <div className="flex items-center gap-1.5 mt-0.5">
                            <div className="w-1.5 h-1.5 rounded-full" style={{ background: vc }} />
                            <span className="text-xs" style={{ color: vc }}>{rec.verdict.split('.')[0]}</span>
                          </div>
                        )}
                      </div>
                      <div className="flex items-center gap-4">
                        <div className="text-center">
                          <div className="text-base font-bold" style={{ color: rColor }}>{rec.course_rating || rec.avg_rating?.toFixed(1)}</div>
                          <div className="text-[10px]" style={{ color: 'var(--text-3)' }}>Rating</div>
                        </div>
                        <div className="text-center">
                          <div className="text-base font-bold" style={{ color: 'var(--text-2)' }}>{rec.avg_difficulty?.toFixed(1)}</div>
                          <div className="text-[10px]" style={{ color: 'var(--text-3)' }}>Difficulty</div>
                        </div>
                        <div className="text-xs text-right" style={{ color: 'var(--text-3)' }}>
                          {rec.grade_probabilities?.['A range'] > 0 && (
                            <div style={{ color: rec.grade_probabilities['A range'] >= 60 ? 'var(--green)' : 'var(--text-2)' }}>
                              {rec.grade_probabilities['A range'].toFixed(0)}% A
                            </div>
                          )}
                          <div>{rec.course_reviews} reviews</div>
                        </div>
                      </div>
                    </div>
                    {/* Alternatives */}
                    {alts.length > 0 && (
                      <div className="mt-2 pt-2" style={{ borderTop: '1px solid var(--border)' }}>
                        <div className="text-[10px] uppercase tracking-wider mb-1.5" style={{ color: 'var(--text-3)' }}>Alternatives</div>
                        <div className="flex flex-wrap gap-2">
                          {alts.map(alt => (
                            <button key={alt.id} onClick={() => onSelect(alt.id)}
                              className="text-xs px-2.5 py-1 rounded-lg transition-colors"
                              style={{ background: 'var(--bg-3)', color: 'var(--text-2)', border: '1px solid var(--border)' }}
                              onMouseEnter={e => { e.currentTarget.style.borderColor = 'var(--border-hover)'; e.currentTarget.style.color = 'var(--text-1)' }}
                              onMouseLeave={e => { e.currentTarget.style.borderColor = 'var(--border)'; e.currentTarget.style.color = 'var(--text-2)' }}>
                              {alt.name} · {alt.avg_rating?.toFixed(1)}
                            </button>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          </div>
        </div>
      )}

      {!result && courseTags.length === 0 && (
        <div className="text-center py-12">
          <div className="text-3xl mb-3">🎯</div>
          <div className="text-sm" style={{ color: 'var(--text-3)' }}>Add your courses and we'll find the best professor for each one and predict your semester outcome</div>
        </div>
      )}
    </div>
  )
}
