import { useState, useEffect, useCallback } from 'react'
import { API_BASE } from './config'
import Landing from './components/Landing'
import ProfessorList from './components/ProfessorList'
import ProfessorDetail from './components/ProfessorDetail'
import FitQuiz from './components/FitQuiz'
import CompareMode from './components/CompareMode'

function useHashRouter() {
  const [hash, setHash] = useState(window.location.hash.slice(1))
  useEffect(() => {
    const handler = () => setHash(window.location.hash.slice(1))
    window.addEventListener('hashchange', handler)
    return () => window.removeEventListener('hashchange', handler)
  }, [])
  const navigate = useCallback((path) => { window.location.hash = path }, [])
  return { path: hash, navigate }
}

function parseRoute(path) {
  // #/school/mit → { school: 'mit' }
  // #/school/mit/prof/VGVhY2... → { school: 'mit', profId: 'VGVhY2...' }
  // #/school/mit/quiz → { school: 'mit', mode: 'quiz' }
  // #/school/mit/compare → { school: 'mit', mode: 'compare' }
  const parts = path.split('/').filter(Boolean)
  if (parts[0] === 'school' && parts[1]) {
    const school = parts[1]
    if (parts[2] === 'prof' && parts[3]) return { school, profId: decodeURIComponent(parts[3]) }
    if (parts[2] === 'quiz') return { school, mode: 'quiz' }
    if (parts[2] === 'compare') return { school, mode: 'compare' }
    return { school }
  }
  return {}
}

export default function App() {
  const { path, navigate } = useHashRouter()
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

  // Fetch schools
  useEffect(() => {
    fetch(`${API_BASE}/api/schools`).then(r => r.json())
      .then(d => setSchools(d.schools || [])).catch(() => {})
  }, [])

  // Fetch professors
  useEffect(() => {
    if (!school) return
    setLoading(true)
    const params = new URLSearchParams({ sort_by: sortBy, limit: '300' })
    if (search) params.set('search', search)
    if (deptFilter) params.set('department', deptFilter)
    fetch(`${API_BASE}/api/${school}/professors?${params}`).then(r => r.json())
      .then(d => { setProfessors(d.professors || []); setLoading(false) })
      .catch(() => setLoading(false))
  }, [school, search, deptFilter, sortBy])

  // Fetch departments + stats
  useEffect(() => {
    if (!school) return
    fetch(`${API_BASE}/api/${school}/departments`).then(r => r.json())
      .then(d => setDepartments(d.departments || [])).catch(() => {})
    fetch(`${API_BASE}/api/${school}/stats`).then(r => r.json()).then(setStats).catch(() => {})
  }, [school])

  // Fetch professor detail
  useEffect(() => {
    if (!route.profId || !school) { setProfDetail(null); return }
    fetch(`${API_BASE}/api/${school}/professors/${encodeURIComponent(route.profId)}`)
      .then(r => r.json()).then(setProfDetail).catch(() => {})
  }, [route.profId, school])

  const cur = schools.find(s => s.slug === school)

  // Landing page
  if (!school) {
    return (
      <div className="min-h-screen bg-gray-50">
        <header className="bg-white border-b border-gray-100">
          <div className="max-w-6xl mx-auto px-4 py-3 flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-indigo-600 flex items-center justify-center">
              <span className="text-white font-bold text-xs">PI</span>
            </div>
            <div>
              <h1 className="text-base font-bold text-gray-900 leading-tight">ProfInsight</h1>
              <p className="text-[10px] text-gray-400">Bayesian professor analysis</p>
            </div>
          </div>
        </header>
        <Landing schools={schools} onSelectSchool={slug => navigate(`/school/${slug}`)} />
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-100 sticky top-0 z-50">
        <div className="max-w-6xl mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3 cursor-pointer" onClick={() => navigate('')}>
            <div className="w-8 h-8 rounded-lg bg-indigo-600 flex items-center justify-center">
              <span className="text-white font-bold text-xs">PI</span>
            </div>
            <div>
              <h1 className="text-base font-bold text-gray-900 leading-tight">ProfInsight</h1>
              <p className="text-[10px] text-gray-400">Know your professor before you register</p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <select value={school} onChange={e => navigate(`/school/${e.target.value}`)}
              className="text-sm bg-gray-50 border border-gray-200 rounded-lg px-3 py-1.5">
              {schools.map(s => <option key={s.slug} value={s.slug}>{s.name}</option>)}
            </select>
            {cur && (
              <span className="hidden sm:inline text-xs text-gray-400">
                {cur.professors} professors &middot; {cur.reviews?.toLocaleString()} reviews
              </span>
            )}
          </div>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-4 py-5">
        {mode === 'detail' && profDetail ? (
          <div>
            <button onClick={() => navigate(`/school/${school}`)}
              className="flex items-center gap-1.5 text-sm text-gray-400 hover:text-gray-700 mb-4">
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
              </svg>
              Back
            </button>
            <ProfessorDetail professor={profDetail} />
          </div>
        ) : mode === 'quiz' ? (
          <FitQuiz school={school} departments={departments}
            onSelect={id => navigate(`/school/${school}/prof/${id}`)}
            onClose={() => navigate(`/school/${school}`)} />
        ) : mode === 'compare' ? (
          <CompareMode school={school} professors={professors}
            onSelect={id => navigate(`/school/${school}/prof/${id}`)}
            onClose={() => navigate(`/school/${school}`)} />
        ) : (
          <div>
            {stats && (
              <div className="mb-5">
                <h2 className="text-2xl font-bold text-gray-900">Find the right professor</h2>
                <p className="text-sm text-gray-400 mt-1">
                  {stats.total_reviews?.toLocaleString()} reviews analyzed across {stats.departments} departments at {stats.school}
                </p>
              </div>
            )}
            <div className="flex gap-2 mb-4">
              <button onClick={() => navigate(`/school/${school}/quiz`)}
                className="px-4 py-2 bg-indigo-600 text-white rounded-xl text-sm font-medium hover:bg-indigo-700 transition-colors flex items-center gap-2">
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                </svg>
                Find my match
              </button>
              <button onClick={() => navigate(`/school/${school}/compare`)}
                className="px-4 py-2 bg-white border border-gray-200 text-gray-700 rounded-xl text-sm font-medium hover:bg-gray-50 transition-colors flex items-center gap-2">
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                </svg>
                Compare
              </button>
            </div>
            <div className="flex flex-col sm:flex-row gap-2.5 mb-5">
              <div className="relative flex-1">
                <svg className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                </svg>
                <input type="text" placeholder="Search by name or department..."
                  value={search} onChange={e => setSearch(e.target.value)}
                  className="w-full pl-10 pr-4 py-2.5 bg-white border border-gray-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-400" />
              </div>
              <select value={deptFilter} onChange={e => setDeptFilter(e.target.value)}
                className="px-3 py-2.5 bg-white border border-gray-200 rounded-xl text-sm cursor-pointer">
                <option value="">All departments</option>
                {departments.map(d => <option key={d.name} value={d.name}>{d.name} ({d.professor_count})</option>)}
              </select>
              <select value={sortBy} onChange={e => setSortBy(e.target.value)}
                className="px-3 py-2.5 bg-white border border-gray-200 rounded-xl text-sm cursor-pointer">
                <option value="rating">Highest rated</option>
                <option value="difficulty">Most difficult</option>
                <option value="num_ratings">Most reviewed</option>
                <option value="name">A to Z</option>
              </select>
            </div>
            <ProfessorList professors={professors} loading={loading}
              onSelect={id => navigate(`/school/${school}/prof/${id}`)} />
          </div>
        )}
      </main>
    </div>
  )
}
