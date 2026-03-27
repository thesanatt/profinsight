import { API_BASE } from '../config'
import { useState, useEffect } from 'react'
import {
  RadarChart, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis,
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, Cell, Legend,
} from 'recharts'

const COLORS = ['#6366f1', '#f59e0b', '#10b981', '#ef4444']

function StatCompare({ label, values, names, format, higherIsBetter = true }) {
  const best = higherIsBetter ? Math.max(...values.filter(v => v != null)) : Math.min(...values.filter(v => v != null))
  return (
    <div className="py-2.5 border-b border-gray-50 last:border-0">
      <div className="text-xs text-gray-400 mb-1.5">{label}</div>
      <div className="flex gap-4">
        {values.map((val, i) => {
          const isBest = val === best && values.filter(v => v === best).length === 1
          return (
            <div key={i} className="flex-1">
              <div className={`text-lg font-bold ${isBest ? 'text-indigo-600' : 'text-gray-700'}`}>
                {val != null ? (format ? format(val) : val) : '—'}
                {isBest && <span className="text-xs ml-1">★</span>}
              </div>
              <div className="text-[10px] text-gray-400 truncate">{names[i]}</div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

export default function CompareMode({ school, professors, onSelect, onClose }) {
  const [selected, setSelected] = useState([])
  const [details, setDetails] = useState([])
  const [search, setSearch] = useState('')

  // Fetch full details for selected professors
  useEffect(() => {
    if (selected.length < 2) { setDetails([]); return }
    Promise.all(
      selected.map(id =>
        fetch(`${API_BASE}/api/${school}/professors/${encodeURIComponent(id)}`).then(r => r.json())
      )
    ).then(setDetails).catch(() => {})
  }, [selected, school])

  const filtered = professors.filter(p =>
    !selected.includes(p.id) &&
    (!search || p.name.toLowerCase().includes(search.toLowerCase()) || p.department?.toLowerCase().includes(search.toLowerCase()))
  ).slice(0, 15)

  const toggleSelect = (id) => {
    setSelected(prev =>
      prev.includes(id) ? prev.filter(x => x !== id) : prev.length < 4 ? [...prev, id] : prev
    )
  }

  const names = details.map(d => d.name?.split(' ')[1] || d.name) // Last names for compact display

  // Build radar data from sentiment
  const radarData = details.length >= 2 ? (() => {
    const categories = ['approachability', 'lectures', 'workload', 'exams', 'grading']
    return categories.map(cat => {
      const row = { category: cat.charAt(0).toUpperCase() + cat.slice(1) }
      details.forEach((d, i) => {
        row[`prof${i}`] = d.category_sentiment?.[cat]?.pct_positive || 0
      })
      return row
    })
  })() : []

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <div>
          <h2 className="text-xl font-bold text-gray-900">Compare professors</h2>
          <p className="text-sm text-gray-400 mt-0.5">Select 2-4 professors to compare side by side</p>
        </div>
        <button onClick={onClose} className="text-sm text-gray-400 hover:text-gray-600">Close</button>
      </div>

      {/* Selection pills */}
      <div className="flex flex-wrap gap-2 mb-4">
        {selected.map(id => {
          const prof = professors.find(p => p.id === id) || {}
          return (
            <span key={id} className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-indigo-50 text-indigo-700 rounded-lg text-sm">
              {prof.name}
              <button onClick={() => toggleSelect(id)} className="text-indigo-400 hover:text-indigo-600 ml-1">×</button>
            </span>
          )
        })}
        {selected.length < 4 && (
          <div className="relative">
            <input type="text" placeholder="Add professor..." value={search}
              onChange={e => setSearch(e.target.value)}
              className="px-3 py-1.5 bg-white border border-gray-200 rounded-lg text-sm w-48 focus:outline-none focus:ring-2 focus:ring-indigo-500/20" />
            {search && (
              <div className="absolute top-full left-0 mt-1 w-72 bg-white border border-gray-200 rounded-xl shadow-lg z-10 max-h-60 overflow-y-auto">
                {filtered.map(p => (
                  <button key={p.id} onClick={() => { toggleSelect(p.id); setSearch('') }}
                    className="w-full text-left px-3 py-2 hover:bg-gray-50 text-sm border-b border-gray-50 last:border-0">
                    <span className="font-medium text-gray-800">{p.name}</span>
                    <span className="text-gray-400 ml-2 text-xs">{p.department}</span>
                  </button>
                ))}
                {filtered.length === 0 && <div className="px-3 py-2 text-sm text-gray-400">No results</div>}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Comparison view */}
      {details.length >= 2 && (
        <div className="space-y-4">
          {/* Key stats comparison */}
          <div className="bg-white rounded-xl border border-gray-100 p-5">
            <h3 className="font-semibold text-gray-900 mb-3">Head to head</h3>
            <StatCompare label="Overall Rating" names={names}
              values={details.map(d => d.summary?.avg_rating)} format={v => v?.toFixed(1)} />
            <StatCompare label="Difficulty" names={names}
              values={details.map(d => d.summary?.avg_difficulty)} format={v => v?.toFixed(1)} higherIsBetter={false} />
            <StatCompare label="Would Take Again" names={names}
              values={details.map(d => d.summary?.would_take_again_pct)} format={v => v >= 0 ? `${v?.toFixed(0)}%` : '—'} />
            <StatCompare label="Chance of A" names={names}
              values={details.map(d => d.grade_probabilities?.['A range'])} format={v => `${v?.toFixed(0)}%`} />
            <StatCompare label="Reviews" names={names}
              values={details.map(d => d.summary?.num_ratings)} />
            <StatCompare label="Bayesian P(good)" names={names}
              values={details.map(d => d.bayesian_analysis?.rating_posteriors?.good?.mean)}
              format={v => `${(v * 100).toFixed(0)}%`} />
          </div>

          {/* Radar comparison */}
          {radarData.length > 0 && (
            <div className="bg-white rounded-xl border border-gray-100 p-5">
              <h3 className="font-semibold text-gray-900 mb-3">Sentiment by category</h3>
              <ResponsiveContainer width="100%" height={280}>
                <RadarChart data={radarData}>
                  <PolarGrid stroke="#e5e7eb" />
                  <PolarAngleAxis dataKey="category" tick={{ fontSize: 11, fill: '#6b7280' }} />
                  <PolarRadiusAxis domain={[0, 100]} tick={{ fontSize: 9, fill: '#9ca3af' }} />
                  {details.map((d, i) => (
                    <Radar key={i} name={names[i]} dataKey={`prof${i}`}
                      stroke={COLORS[i]} fill={COLORS[i]} fillOpacity={0.08} strokeWidth={2} />
                  ))}
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                </RadarChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* Verdicts side by side */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
            {details.map((d, i) => (
              <div key={d.professor_id} onClick={() => onSelect(d.professor_id)}
                className="bg-white rounded-xl border border-gray-100 p-4 hover:border-indigo-200 cursor-pointer transition-colors"
                style={{ borderTopColor: COLORS[i], borderTopWidth: 3 }}>
                <div className="font-semibold text-gray-900 text-sm">{d.name}</div>
                <div className="text-xs text-gray-400 mb-2">{d.department}</div>
                <div className="text-xs text-gray-600 leading-relaxed">{d.verdict}</div>
                <div className="text-xs text-gray-400 mt-2">Confidence: {d.confidence_level}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {details.length < 2 && selected.length < 2 && (
        <div className="text-center py-16 text-gray-400 text-sm">
          Search and select at least 2 professors to compare
        </div>
      )}
    </div>
  )
}
