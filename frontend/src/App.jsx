import { useState, useEffect, useCallback } from 'react'
import { API_BASE } from './config'
import Landing from './components/Landing'
import ProfessorList from './components/ProfessorList'
import ProfessorDetail from './components/ProfessorDetail'
import FitQuiz from './components/FitQuiz'
import CompareMode from './components/CompareMode'
import ScheduleHelper from './components/ScheduleHelper'

function useHash() {
  const [hash, setHash] = useState(window.location.hash.slice(1))
  useEffect(() => { const h = () => setHash(window.location.hash.slice(1)); window.addEventListener('hashchange', h); return () => window.removeEventListener('hashchange', h) }, [])
  return { path: hash, nav: useCallback(p => { window.location.hash = p }, []) }
}

function parseRoute(p) {
  const s = p.split('/').filter(Boolean)
  if (s[0] === 'school' && s[1]) {
    if (s[2] === 'prof' && s[3]) return { school: s[1], profId: decodeURIComponent(s[3]) }
    if (s[2] === 'quiz') return { school: s[1], mode: 'quiz' }
    if (s[2] === 'compare') return { school: s[1], mode: 'compare' }
    if (s[2] === 'schedule') return { school: s[1], mode: 'schedule' }
    return { school: s[1] }
  }
  return {}
}

export default function App() {
  const { path, nav } = useHash()
  const route = parseRoute(path)
  const [schools, setSchools] = useState([])
  const [professors, setProfessors] = useState([])
  const [departments, setDepartments] = useState([])
  const [stats, setStats] = useState(null)
  const [profDetail, setProfDetail] = useState(null)
  const [search, setSearch] = useState('')
  const [deptFilter, setDeptFilter] = useState('')
  const [sortBy, setSortBy] = useState('rating')
  const [loading, setLoading] = useState(true)

  const school = route.school || ''
  const mode = route.profId ? 'detail' : (route.mode || 'browse')

  useEffect(() => { fetch(`${API_BASE}/api/schools`).then(r => r.json()).then(d => setSchools(d.schools || [])).catch(() => {}) }, [])

  useEffect(() => {
    if (!school) return
    setLoading(true)
    const p = new URLSearchParams({ sort_by: sortBy, limit: '300' })
    if (search) p.set('search', search)
    if (deptFilter) p.set('department', deptFilter)
    fetch(`${API_BASE}/api/${school}/professors?${p}`).then(r => r.json())
      .then(d => { setProfessors(d.professors || []); setLoading(false) }).catch(() => setLoading(false))
  }, [school, search, deptFilter, sortBy])

  useEffect(() => {
    if (!school) return
    fetch(`${API_BASE}/api/${school}/departments`).then(r => r.json()).then(d => setDepartments(d.departments || [])).catch(() => {})
    fetch(`${API_BASE}/api/${school}/stats`).then(r => r.json()).then(setStats).catch(() => {})
  }, [school])

  useEffect(() => {
    if (!route.profId || !school) { setProfDetail(null); return }
    fetch(`${API_BASE}/api/${school}/professors/${encodeURIComponent(route.profId)}`).then(r => r.json()).then(setProfDetail).catch(() => {})
  }, [route.profId, school])

  const cur = schools.find(s => s.slug === school)

  // Landing
  if (!school) return (
    <div style={{ background: 'var(--bg-0)', minHeight: '100vh' }}>
      <header style={{ background: 'var(--bg-1)', borderBottom: '1px solid var(--border)' }}>
        <div className="max-w-6xl mx-auto px-4 py-3 flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg flex items-center justify-center" style={{ background: 'var(--accent-dim)' }}>
            <span className="text-white font-bold text-xs">PI</span>
          </div>
          <span className="font-semibold" style={{ color: 'var(--text-1)' }}>ProfInsight</span>
        </div>
      </header>
      <Landing schools={schools} onSelectSchool={s => nav(`/school/${s}`)} />
    </div>
  )

  // Main app
  return (
    <div style={{ background: 'var(--bg-0)', minHeight: '100vh' }}>
      <header className="sticky top-0 z-50" style={{ background: 'var(--bg-1)', borderBottom: '1px solid var(--border)' }}>
        <div className="max-w-6xl mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3 cursor-pointer" onClick={() => nav('')}>
            <div className="w-8 h-8 rounded-lg flex items-center justify-center" style={{ background: 'var(--accent-dim)' }}>
              <span className="text-white font-bold text-xs">PI</span>
            </div>
            <div>
              <h1 className="text-sm font-bold leading-tight" style={{ color: 'var(--text-1)' }}>ProfInsight</h1>
              <p className="text-[10px]" style={{ color: 'var(--text-3)' }}>Know your professor before you register</p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <select value={school} onChange={e => nav(`/school/${e.target.value}`)} className="select-dark text-sm py-1.5 max-w-[200px] sm:max-w-none truncate">
              {schools.map(s => <option key={s.slug} value={s.slug}>{s.name}</option>)}
            </select>
            {cur && <span className="hidden sm:inline text-xs" style={{ color: 'var(--text-3)' }}>{cur.professors} profs · {cur.reviews?.toLocaleString()} reviews</span>}
          </div>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-4 py-5">
        {mode === 'detail' && profDetail ? (
          <div>
            <button onClick={() => nav(`/school/${school}`)} className="flex items-center gap-1.5 text-sm mb-4 transition-colors" style={{ color: 'var(--text-3)' }}
              onMouseEnter={e => e.currentTarget.style.color = 'var(--text-1)'} onMouseLeave={e => e.currentTarget.style.color = 'var(--text-3)'}>
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" /></svg>
              Back
            </button>
            <ProfessorDetail professor={profDetail} />
          </div>
        ) : mode === 'quiz' ? (
          <FitQuiz school={school} departments={departments} onSelect={id => nav(`/school/${school}/prof/${id}`)} onClose={() => nav(`/school/${school}`)} />
        ) : mode === 'compare' ? (
          <CompareMode school={school} professors={professors} onSelect={id => nav(`/school/${school}/prof/${id}`)} onClose={() => nav(`/school/${school}`)} />
        ) : mode === 'schedule' ? (
          <ScheduleHelper school={school} onSelect={id => nav(`/school/${school}/prof/${id}`)} onClose={() => nav(`/school/${school}`)} />
        ) : (
          <div>
            {stats && (
              <div className="mb-5">
                <h2 className="text-xl font-bold" style={{ color: 'var(--text-1)' }}>Find the right professor</h2>
                <p className="text-sm mt-1" style={{ color: 'var(--text-3)' }}>
                  {stats.total_reviews?.toLocaleString()} reviews across {stats.departments} departments at {stats.school}
                </p>
              </div>
            )}
            <div className="flex flex-wrap gap-2 mb-4">
              <button onClick={() => nav(`/school/${school}/quiz`)} className="btn-primary">
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" /></svg>
                Find my match
              </button>
              <button onClick={() => nav(`/school/${school}/compare`)} className="btn-secondary">
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" /></svg>
                Compare
              </button>
              <button onClick={() => nav(`/school/${school}/schedule`)} className="btn-secondary">
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" /></svg>
                Schedule
              </button>
            </div>
            <div className="flex flex-col sm:flex-row gap-2 mb-4">
              <div className="relative flex-1">
                <svg className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4" style={{ color: 'var(--text-3)' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                </svg>
                <input type="text" placeholder="Search by name or department..." value={search} onChange={e => setSearch(e.target.value)} className="input-dark w-full pl-10" />
              </div>
              <select value={deptFilter} onChange={e => setDeptFilter(e.target.value)} className="select-dark">
                <option value="">All departments</option>
                {departments.map(d => <option key={d.name} value={d.name}>{d.name} ({d.professor_count})</option>)}
              </select>
              <select value={sortBy} onChange={e => setSortBy(e.target.value)} className="select-dark">
                <option value="rating">Highest rated</option>
                <option value="difficulty">Most difficult</option>
                <option value="num_ratings">Most reviewed</option>
                <option value="name">A to Z</option>
              </select>
            </div>
            <ProfessorList professors={professors} loading={loading} onSelect={id => nav(`/school/${school}/prof/${id}`)} />
          </div>
        )}
      </main>
    </div>
  )
}
