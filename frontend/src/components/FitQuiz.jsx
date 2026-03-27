import { API_BASE } from '../config'
import { useState } from 'react'

const verdictConfig = {
  great: { dot: 'bg-emerald-500', text: 'text-emerald-700' },
  good: { dot: 'bg-blue-500', text: 'text-blue-700' },
  mixed: { dot: 'bg-amber-500', text: 'text-amber-700' },
  caution: { dot: 'bg-orange-500', text: 'text-orange-700' },
  poor: { dot: 'bg-red-500', text: 'text-red-700' },
}

const questions = [
  { key: 'difficulty', label: 'How do you feel about difficulty?', low: 'Keep it easy', high: 'Challenge me' },
  { key: 'grading', label: 'How important is lenient grading?', low: 'I need easy As', high: "Fair grading is fine" },
  { key: 'lectures', label: 'How much do lecture quality matter?', low: "I'll self-study", high: 'Lectures are everything' },
  { key: 'approachability', label: 'How important is professor approachability?', low: 'Not important', high: 'Must be accessible' },
  { key: 'workload', label: 'How do you feel about workload?', low: 'Keep it light', high: 'Heavy is fine' },
]

function FitScoreRing({ score }) {
  const r = 28
  const circ = 2 * Math.PI * r
  const offset = circ - (score / 100) * circ
  const color = score >= 75 ? '#10b981' : score >= 55 ? '#f59e0b' : '#ef4444'
  return (
    <div className="relative w-16 h-16 flex-shrink-0">
      <svg className="w-16 h-16 -rotate-90" viewBox="0 0 64 64">
        <circle cx="32" cy="32" r={r} fill="none" stroke="#f3f4f6" strokeWidth="4" />
        <circle cx="32" cy="32" r={r} fill="none" stroke={color} strokeWidth="4"
          strokeLinecap="round" strokeDasharray={circ} strokeDashoffset={offset} />
      </svg>
      <div className="absolute inset-0 flex items-center justify-center">
        <span className="text-sm font-bold" style={{ color }}>{score.toFixed(0)}</span>
      </div>
    </div>
  )
}

export default function FitQuiz({ school, departments, onSelect, onClose }) {
  const [prefs, setPrefs] = useState({ difficulty: 3, grading: 3, lectures: 3, approachability: 3, workload: 3 })
  const [dept, setDept] = useState('')
  const [results, setResults] = useState(null)
  const [loading, setLoading] = useState(false)
  const [step, setStep] = useState('quiz') // 'quiz' | 'results'

  const updatePref = (key, val) => setPrefs(p => ({ ...p, [key]: val }))

  const submit = () => {
    setLoading(true)
    const params = new URLSearchParams({
      difficulty: prefs.difficulty,
      grading: prefs.grading,
      lectures: prefs.lectures,
      approachability: prefs.approachability,
      workload: prefs.workload,
      limit: '30',
    })
    if (dept) params.set('department', dept)

    fetch(`${API_BASE}/api/${school}/fit?${params}`)
      .then(r => r.json())
      .then(data => { setResults(data); setStep('results'); setLoading(false) })
      .catch(() => setLoading(false))
  }

  if (step === 'results' && results) {
    return (
      <div>
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-xl font-bold text-gray-900">Your best matches</h2>
            <p className="text-sm text-gray-400 mt-0.5">
              Based on your learning preferences · {results.count} professors ranked
            </p>
          </div>
          <div className="flex gap-2">
            <button onClick={() => setStep('quiz')}
              className="text-sm text-indigo-600 hover:text-indigo-800 font-medium">
              Adjust preferences
            </button>
            <button onClick={onClose}
              className="text-sm text-gray-400 hover:text-gray-600 ml-3">
              Close
            </button>
          </div>
        </div>

        <div className="space-y-2">
          {results.results.map((prof, i) => {
            const vc = verdictConfig[prof.verdict_emoji] || verdictConfig.mixed
            return (
              <div key={prof.id} onClick={() => onSelect(prof.id)}
                className="bg-white rounded-xl border border-gray-100 hover:border-gray-200 hover:shadow-sm transition-all cursor-pointer px-5 py-4">
                <div className="flex items-center gap-4">
                  {/* Rank + fit score ring */}
                  <div className="flex items-center gap-3">
                    <span className="text-lg font-bold text-gray-300 w-6 text-right">#{i + 1}</span>
                    <FitScoreRing score={prof.fit_score} />
                  </div>

                  {/* Name + reasons */}
                  <div className="flex-1 min-w-0">
                    <div className="font-semibold text-gray-900">{prof.name}</div>
                    <div className="text-xs text-gray-400">{prof.department}</div>
                    {prof.fit_reasons?.length > 0 && (
                      <div className="flex flex-wrap gap-1.5 mt-1.5">
                        {prof.fit_reasons.map((r, j) => (
                          <span key={j} className="text-[11px] px-2 py-0.5 rounded-md bg-indigo-50 text-indigo-600">
                            {r}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>

                  {/* Stats */}
                  <div className="hidden sm:flex items-center gap-4 text-sm">
                    <div className="text-center">
                      <div className={`font-bold ${prof.avg_rating >= 4 ? 'text-emerald-600' : prof.avg_rating >= 3 ? 'text-amber-600' : 'text-red-500'}`}>
                        {prof.avg_rating?.toFixed(1)}
                      </div>
                      <div className="text-[10px] text-gray-400">Quality</div>
                    </div>
                    <div className="text-center">
                      <div className="font-bold text-gray-700">{prof.avg_difficulty?.toFixed(1)}</div>
                      <div className="text-[10px] text-gray-400">Difficulty</div>
                    </div>
                    <div className="text-center">
                      <div className="text-xs text-gray-400">{prof.num_ratings} reviews</div>
                      {prof.would_take_again_pct >= 0 && (
                        <div className={`text-xs font-medium ${prof.would_take_again_pct >= 60 ? 'text-emerald-600' : 'text-amber-600'}`}>
                          {prof.would_take_again_pct?.toFixed(0)}% again
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      </div>
    )
  }

  return (
    <div className="max-w-2xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-xl font-bold text-gray-900">Find your perfect professor</h2>
          <p className="text-sm text-gray-400 mt-0.5">Tell us how you learn best and we'll match you</p>
        </div>
        <button onClick={onClose} className="text-sm text-gray-400 hover:text-gray-600">Close</button>
      </div>

      <div className="space-y-5">
        {questions.map(q => (
          <div key={q.key} className="bg-white rounded-xl border border-gray-100 px-5 py-4">
            <div className="text-sm font-medium text-gray-800 mb-3">{q.label}</div>
            <div className="flex items-center gap-3">
              <span className="text-xs text-gray-400 w-24 text-right">{q.low}</span>
              <div className="flex-1 flex items-center gap-1">
                {[1, 2, 3, 4, 5].map(val => (
                  <button key={val} onClick={() => updatePref(q.key, val)}
                    className={`flex-1 h-9 rounded-lg text-sm font-medium transition-all ${
                      prefs[q.key] === val
                        ? 'bg-indigo-600 text-white shadow-sm'
                        : 'bg-gray-100 text-gray-500 hover:bg-gray-200'
                    }`}>
                    {val}
                  </button>
                ))}
              </div>
              <span className="text-xs text-gray-400 w-24">{q.high}</span>
            </div>
          </div>
        ))}

        {/* Department filter */}
        <div className="bg-white rounded-xl border border-gray-100 px-5 py-4">
          <div className="text-sm font-medium text-gray-800 mb-2">Filter by department (optional)</div>
          <select value={dept} onChange={e => setDept(e.target.value)}
            className="w-full px-3 py-2 bg-gray-50 border border-gray-200 rounded-lg text-sm">
            <option value="">All departments</option>
            {departments.map(d => <option key={d.name} value={d.name}>{d.name}</option>)}
          </select>
        </div>
      </div>

      <button onClick={submit} disabled={loading}
        className="w-full mt-6 py-3 bg-indigo-600 text-white rounded-xl font-semibold hover:bg-indigo-700 transition-colors disabled:opacity-50">
        {loading ? 'Finding matches...' : 'Find my matches'}
      </button>
    </div>
  )
}
