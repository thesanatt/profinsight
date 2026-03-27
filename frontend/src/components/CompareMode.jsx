import { useState, useEffect } from 'react'
import { API_BASE } from '../config'
import { RadarChart, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis, ResponsiveContainer, Legend } from 'recharts'

const COLORS = ['#C9A0FF', '#FFD166', '#77DD77', '#FF6B6B']

function StatRow({ label, values, names, format, higherIsBetter = true }) {
  const valid = values.filter(v => v != null)
  const best = higherIsBetter ? Math.max(...valid) : Math.min(...valid)
  return (
    <div className="py-2.5" style={{ borderBottom: '1px solid var(--border)' }}>
      <div className="text-xs mb-1.5" style={{ color: 'var(--text-3)' }}>{label}</div>
      <div className="flex gap-4">
        {values.map((v, i) => {
          const isBest = v === best && valid.filter(x => x === best).length === 1
          return (
            <div key={i} className="flex-1">
              <div className="text-lg font-bold" style={{ color: isBest ? 'var(--accent)' : 'var(--text-2)' }}>
                {v != null ? (format ? format(v) : v) : '—'}{isBest && <span className="text-xs ml-1" style={{ color: 'var(--accent)' }}>★</span>}
              </div>
              <div className="text-[10px] truncate" style={{ color: 'var(--text-3)' }}>{names[i]}</div>
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

  useEffect(() => {
    if (selected.length < 2) { setDetails([]); return }
    Promise.all(selected.map(id =>
      fetch(`${API_BASE}/api/${school}/professors/${encodeURIComponent(id)}`).then(r => r.json())
    )).then(setDetails).catch(() => {})
  }, [selected, school])

  const filtered = professors.filter(p => !selected.includes(p.id) &&
    (!search || p.name.toLowerCase().includes(search.toLowerCase()) || p.department?.toLowerCase().includes(search.toLowerCase()))
  ).slice(0, 12)

  const toggle = id => setSelected(p => p.includes(id) ? p.filter(x => x !== id) : p.length < 4 ? [...p, id] : p)
  const names = details.map(d => d.name?.split(' ').pop() || d.name)

  const radarData = details.length >= 2 ? ['approachability','lectures','workload','exams','grading'].map(cat => {
    const row = { category: cat.charAt(0).toUpperCase() + cat.slice(1) }
    details.forEach((d, i) => { row[`p${i}`] = d.category_sentiment?.[cat]?.pct_positive || 0 })
    return row
  }) : []

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <div>
          <h2 className="text-xl font-bold" style={{ color: 'var(--text-1)' }}>Compare professors</h2>
          <p className="text-sm mt-0.5" style={{ color: 'var(--text-3)' }}>Select 2-4 professors</p>
        </div>
        <button onClick={onClose} className="text-sm" style={{ color: 'var(--text-3)' }}>Close</button>
      </div>

      <div className="flex flex-wrap gap-2 mb-4">
        {selected.map(id => {
          const p = professors.find(x => x.id === id) || {}
          return (
            <span key={id} className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm"
              style={{ background: 'var(--accent-bg)', color: 'var(--accent)', border: '1px solid var(--accent-border)' }}>
              {p.name}
              <button onClick={() => toggle(id)} className="ml-1 opacity-60 hover:opacity-100">×</button>
            </span>
          )
        })}
        {selected.length < 4 && (
          <div className="relative">
            <input type="text" placeholder="Add professor..." value={search} onChange={e => setSearch(e.target.value)}
              className="input-dark w-48 text-sm py-1.5" />
            {search && (
              <div className="absolute top-full left-0 mt-1 w-72 rounded-xl shadow-lg z-10 max-h-60 overflow-y-auto"
                style={{ background: 'var(--bg-3)', border: '1px solid var(--border)' }}>
                {filtered.map(p => (
                  <button key={p.id} onClick={() => { toggle(p.id); setSearch('') }}
                    className="w-full text-left px-3 py-2.5 text-sm transition-colors"
                    style={{ borderBottom: '1px solid var(--border)' }}
                    onMouseEnter={e => e.currentTarget.style.background = 'var(--bg-hover)'}
                    onMouseLeave={e => e.currentTarget.style.background = 'transparent'}>
                    <span style={{ color: 'var(--text-1)' }}>{p.name}</span>
                    <span className="ml-2 text-xs" style={{ color: 'var(--text-3)' }}>{p.department}</span>
                  </button>
                ))}
                {filtered.length === 0 && <div className="px-3 py-3 text-sm" style={{ color: 'var(--text-3)' }}>No results</div>}
              </div>
            )}
          </div>
        )}
      </div>

      {details.length >= 2 && (
        <div className="space-y-3">
          <div className="card p-5">
            <h3 className="font-semibold text-sm mb-3" style={{ color: 'var(--text-1)' }}>Head to head</h3>
            <StatRow label="Rating" names={names} values={details.map(d => d.summary?.avg_rating)} format={v => v?.toFixed(1)} />
            <StatRow label="Difficulty" names={names} values={details.map(d => d.summary?.avg_difficulty)} format={v => v?.toFixed(1)} higherIsBetter={false} />
            <StatRow label="Would take again" names={names} values={details.map(d => d.summary?.would_take_again_pct)} format={v => v >= 0 ? v?.toFixed(0)+'%' : '—'} />
            <StatRow label="Chance of A" names={names} values={details.map(d => d.grade_probabilities?.['A range'])} format={v => v?.toFixed(0)+'%'} />
            <StatRow label="Reviews" names={names} values={details.map(d => d.summary?.num_ratings)} />
          </div>

          {radarData.length > 0 && (
            <div className="card p-5">
              <h3 className="font-semibold text-sm mb-3" style={{ color: 'var(--text-1)' }}>Sentiment comparison</h3>
              <ResponsiveContainer width="100%" height={280}>
                <RadarChart data={radarData}>
                  <PolarGrid stroke="var(--border)" />
                  <PolarAngleAxis dataKey="category" tick={{ fontSize: 11 }} />
                  <PolarRadiusAxis domain={[0, 100]} tick={{ fontSize: 9 }} />
                  {details.map((_, i) => <Radar key={i} name={names[i]} dataKey={`p${i}`} stroke={COLORS[i]} fill={COLORS[i]} fillOpacity={0.06} strokeWidth={2} />)}
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                </RadarChart>
              </ResponsiveContainer>
            </div>
          )}

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2">
            {details.map((d, i) => (
              <div key={d.professor_id} onClick={() => onSelect(d.professor_id)} className="card-hover p-4"
                style={{ borderTop: `2px solid ${COLORS[i]}` }}>
                <div className="font-semibold text-sm" style={{ color: 'var(--text-1)' }}>{d.name}</div>
                <div className="text-xs mb-2" style={{ color: 'var(--text-3)' }}>{d.department}</div>
                <div className="text-xs leading-relaxed" style={{ color: 'var(--text-2)' }}>{d.verdict}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {details.length < 2 && selected.length < 2 && (
        <div className="text-center py-16 text-sm" style={{ color: 'var(--text-3)' }}>Search and select at least 2 professors</div>
      )}
    </div>
  )
}
