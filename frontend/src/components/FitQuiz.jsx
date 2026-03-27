import { useState } from 'react'
import { API_BASE } from '../config'

const questions = [
  { key: 'difficulty', label: 'How do you feel about difficulty?', low: 'Keep it easy', high: 'Challenge me' },
  { key: 'grading', label: 'How important is lenient grading?', low: 'I need easy As', high: "Fair grading is fine" },
  { key: 'lectures', label: 'How much do lecture quality matter?', low: "I'll self-study", high: 'Lectures are everything' },
  { key: 'approachability', label: 'How important is professor approachability?', low: 'Not important', high: 'Very important' },
  { key: 'workload', label: 'How do you feel about workload?', low: 'Keep it light', high: 'Heavy is fine' },
]

function FitRing({ score }) {
  const r = 26, circ = 2 * Math.PI * r, off = circ - (score / 100) * circ
  const c = score >= 75 ? 'var(--green)' : score >= 55 ? 'var(--yellow)' : 'var(--red)'
  return (
    <div className="relative w-14 h-14 flex-shrink-0">
      <svg className="w-14 h-14 -rotate-90" viewBox="0 0 60 60">
        <circle cx="30" cy="30" r={r} fill="none" stroke="var(--border)" strokeWidth="3.5" />
        <circle cx="30" cy="30" r={r} fill="none" stroke={c} strokeWidth="3.5" strokeLinecap="round" strokeDasharray={circ} strokeDashoffset={off} />
      </svg>
      <div className="absolute inset-0 flex items-center justify-center text-sm font-bold" style={{ color: c }}>{score.toFixed(0)}</div>
    </div>
  )
}

export default function FitQuiz({ school, departments, onSelect, onClose }) {
  const [prefs, setPrefs] = useState({ difficulty: 3, grading: 3, lectures: 3, approachability: 3, workload: 3 })
  const [dept, setDept] = useState('')
  const [results, setResults] = useState(null)
  const [loading, setLoading] = useState(false)
  const [step, setStep] = useState('quiz')

  const submit = () => {
    setLoading(true)
    const params = new URLSearchParams({ ...prefs, limit: '30' })
    if (dept) params.set('department', dept)
    fetch(`${API_BASE}/api/${school}/fit?${params}`)
      .then(r => r.json()).then(d => { setResults(d); setStep('results'); setLoading(false) }).catch(() => setLoading(false))
  }

  if (step === 'results' && results) {
    return (
      <div>
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-xl font-bold" style={{ color: 'var(--text-1)' }}>Your best matches</h2>
            <p className="text-sm mt-0.5" style={{ color: 'var(--text-3)' }}>{results.count} professors ranked by fit</p>
          </div>
          <div className="flex gap-3">
            <button onClick={() => setStep('quiz')} className="text-sm font-medium" style={{ color: 'var(--accent)' }}>Adjust</button>
            <button onClick={onClose} className="text-sm" style={{ color: 'var(--text-3)' }}>Close</button>
          </div>
        </div>
        <div className="space-y-1.5">
          {results.results.map((p, i) => (
            <div key={p.id} onClick={() => onSelect(p.id)} className="card-hover px-5 py-3.5">
              <div className="flex items-center gap-4">
                <span className="text-lg font-bold w-6 text-right" style={{ color: 'var(--text-3)' }}>#{i+1}</span>
                <FitRing score={p.fit_score} />
                <div className="flex-1 min-w-0">
                  <div className="font-semibold" style={{ color: 'var(--text-1)' }}>{p.name}</div>
                  <div className="text-xs" style={{ color: 'var(--text-3)' }}>{p.department}</div>
                  {p.fit_reasons?.length > 0 && (
                    <div className="flex flex-wrap gap-1.5 mt-1.5">
                      {p.fit_reasons.map((r, j) => (
                        <span key={j} className="text-[11px] px-2 py-0.5 rounded-md" style={{ background: 'var(--accent-bg)', color: 'var(--accent)', border: '1px solid var(--accent-border)' }}>{r}</span>
                      ))}
                    </div>
                  )}
                </div>
                <div className="hidden sm:flex items-center gap-4 text-sm">
                  <div className="text-center">
                    <div className="font-bold" style={{ color: p.avg_rating >= 4 ? 'var(--green)' : p.avg_rating >= 3 ? 'var(--yellow)' : 'var(--red)' }}>{p.avg_rating?.toFixed(1)}</div>
                    <div className="text-[10px]" style={{ color: 'var(--text-3)' }}>Quality</div>
                  </div>
                  <div className="text-center">
                    <div className="font-bold" style={{ color: 'var(--text-2)' }}>{p.avg_difficulty?.toFixed(1)}</div>
                    <div className="text-[10px]" style={{ color: 'var(--text-3)' }}>Difficulty</div>
                  </div>
                  <div className="text-xs" style={{ color: 'var(--text-3)' }}>{p.num_ratings} reviews</div>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    )
  }

  return (
    <div className="max-w-2xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-xl font-bold" style={{ color: 'var(--text-1)' }}>Find your perfect professor</h2>
          <p className="text-sm mt-0.5" style={{ color: 'var(--text-3)' }}>Tell us how you learn and we'll match you</p>
        </div>
        <button onClick={onClose} className="text-sm" style={{ color: 'var(--text-3)' }}>Close</button>
      </div>
      <div className="space-y-3">
        {questions.map(q => (
          <div key={q.key} className="card px-5 py-4">
            <div className="text-sm font-medium mb-3" style={{ color: 'var(--text-1)' }}>{q.label}</div>
            <div className="flex items-center gap-3">
              <span className="text-xs w-24 text-right" style={{ color: 'var(--text-3)' }}>{q.low}</span>
              <div className="flex-1 flex gap-1.5">
                {[1,2,3,4,5].map(v => (
                  <button key={v} onClick={() => setPrefs(p => ({...p, [q.key]: v}))}
                    className="flex-1 h-9 rounded-lg text-sm font-medium transition-all"
                    style={prefs[q.key] === v
                      ? { background: 'var(--accent-dim)', color: 'white' }
                      : { background: 'var(--bg-3)', color: 'var(--text-3)' }}>
                    {v}
                  </button>
                ))}
              </div>
              <span className="text-xs w-24" style={{ color: 'var(--text-3)' }}>{q.high}</span>
            </div>
          </div>
        ))}
        <div className="card px-5 py-4">
          <div className="text-sm font-medium mb-2" style={{ color: 'var(--text-1)' }}>Department (optional)</div>
          <select value={dept} onChange={e => setDept(e.target.value)} className="select-dark w-full">
            <option value="">All departments</option>
            {departments.map(d => <option key={d.name} value={d.name}>{d.name}</option>)}
          </select>
        </div>
      </div>
      <button onClick={submit} disabled={loading} className="btn-primary w-full mt-5 py-3 justify-center text-sm">
        {loading ? 'Finding matches...' : 'Find my matches'}
      </button>
    </div>
  )
}
