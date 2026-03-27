import { API_BASE } from './config'
import { useState, useEffect } from 'react'
import ProfessorList from './components/ProfessorList'
import ProfessorDetail from './components/ProfessorDetail'
import FitQuiz from './components/FitQuiz'
import CompareMode from './components/CompareMode'

export default function App() {
  const [schools, setSchools] = useState([])
  const [school, setSchool] = useState('')
  const [professors, setProfessors] = useState([])
  const [departments, setDepartments] = useState([])
  const [stats, setStats] = useState(null)
  const [selectedProf, setSelectedProf] = useState(null)
  const [profDetail, setProfDetail] = useState(null)
  const [search, setSearch] = useState('')
  const [deptFilter, setDeptFilter] = useState('')
  const [sortBy, setSortBy] = useState('rating')
  const [loading, setLoading] = useState(true)
  const [mode, setMode] = useState('browse') // 'browse' | 'quiz' | 'compare' | 'detail'

  useEffect(() => {
    fetch(`${API_BASE}/api/schools`).then(r => r.json()).then(data => {
      setSchools(data.schools || [])
      if (data.schools?.length) setSchool(data.schools[0].slug)
    }).catch(() => {})
  }, [])

  useEffect(() => {
    if (!school) return
    setLoading(true)
    const params = new URLSearchParams({ sort_by: sortBy, limit: '300' })
    if (search) params.set('search', search)
    if (deptFilter) params.set('department', deptFilter)
    fetch(`${API_BASE}/api/${school}/professors?${params}`).then(r => r.json())
      .then(data => { setProfessors(data.professors || []); setLoading(false) })
      .catch(() => setLoading(false))
  }, [school, search, deptFilter, sortBy])

  useEffect(() => {
    if (!school) return
    fetch(`${API_BASE}/api/${school}/departments`).then(r => r.json())
      .then(data => setDepartments(data.departments || [])).catch(() => {})
    fetch(`${API_BASE}/api/${school}/stats`).then(r => r.json()).then(setStats).catch(() => {})
  }, [school])

  useEffect(() => {
    if (!selectedProf || !school) { setProfDetail(null); return }
    setMode('detail')
    fetch(`${API_BASE}/api/${school}/professors/${encodeURIComponent(selectedProf)}`)
      .then(r => r.json()).then(setProfDetail).catch(() => {})
  }, [selectedProf, school])

  const goBack = () => { setSelectedProf(null); setProfDetail(null); setMode('browse') }
  const cur = schools.find(s => s.slug === school)

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-100 sticky top-0 z-50">
        <div className="max-w-6xl mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3 cursor-pointer" onClick={goBack}>
            <div className="w-8 h-8 rounded-lg bg-indigo-600 flex items-center justify-center">
              <span className="text-white font-bold text-xs">PI</span>
            </div>
            <div>
              <h1 className="text-base font-bold text-gray-900 leading-tight">ProfInsight</h1>
              <p className="text-[10px] text-gray-400">Know your professor before you register</p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            {schools.length > 1 && (
              <select value={school} onChange={e => { setSchool(e.target.value); goBack(); setDeptFilter('') }}
                className="text-sm bg-gray-50 border border-gray-200 rounded-lg px-3 py-1.5">
                {schools.map(s => <option key={s.slug} value={s.slug}>{s.name}</option>)}
              </select>
            )}
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
            <button onClick={goBack}
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
            onSelect={id => setSelectedProf(id)} onClose={() => setMode('browse')} />
        ) : mode === 'compare' ? (
          <CompareMode school={school} professors={professors}
            onSelect={id => setSelectedProf(id)} onClose={() => setMode('browse')} />
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
              <button onClick={() => setMode('quiz')}
                className="px-4 py-2 bg-indigo-600 text-white rounded-xl text-sm font-medium hover:bg-indigo-700 transition-colors flex items-center gap-2">
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                </svg>
                Find my match
              </button>
              <button onClick={() => setMode('compare')}
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

            <ProfessorList professors={professors} loading={loading} onSelect={id => setSelectedProf(id)} />
          </div>
        )}
      </main>
    </div>
  )
}
