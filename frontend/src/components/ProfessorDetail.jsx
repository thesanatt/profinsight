import { useState, useEffect } from 'react'
import {
  AreaChart, Area, BarChart, Bar, XAxis, YAxis, Tooltip,
  ResponsiveContainer, CartesianGrid, Cell, ReferenceLine,
} from 'recharts'
import { API_BASE } from '../config'

// Helpers

function sentimentLabel(pct) {
  if (pct >= 80) return { text: 'Great', color: 'var(--green)' }
  if (pct >= 60) return { text: 'Good', color: '#8be78b' }
  if (pct >= 45) return { text: 'Mixed', color: 'var(--yellow)' }
  if (pct >= 30) return { text: 'Weak', color: 'var(--orange)' }
  return { text: 'Below average', color: 'var(--red)' }
}

function diffLabel(d) {
  if (d >= 4.5) return 'Very challenging'
  if (d >= 3.5) return 'Challenging'
  if (d >= 2.5) return 'Moderate'
  if (d >= 1.5) return 'Light'
  return 'Very light'
}

function getRedFlags(p) {
  const f = [], s = p.summary || {}
  if (s.would_take_again_pct != null && s.would_take_again_pct >= 0 && s.would_take_again_pct < 35) f.push(s.would_take_again_pct.toFixed(0) + '% of students would retake')
  if (s.avg_rating && s.avg_rating < 2.5) f.push('Below average overall rating')
  if (s.avg_difficulty && s.avg_difficulty >= 4.5) f.push('High difficulty level')
  const lec = p.category_sentiment?.lectures
  if (lec && lec.pct_positive < 30) f.push('Lecture quality rated below average')
  if (p.trend_summary?.toLowerCase().includes('declining')) f.push('Ratings have been trending down recently')
  return f
}

// Verdict Banner

function VerdictBanner({ verdict, emoji, confidence, detail, trend, flags }) {
  const colors = { great: 'var(--green)', good: 'var(--accent)', mixed: 'var(--yellow)', caution: 'var(--orange)', poor: 'var(--red)' }
  const bgs = { great: 'var(--green-bg)', good: 'var(--accent-bg)', mixed: 'var(--yellow-bg)', caution: 'var(--orange-bg)', poor: 'var(--red-bg)' }
  const c = colors[emoji] || 'var(--text-2)'
  return (
    <div className="rounded-xl p-4" style={{ background: bgs[emoji] || 'var(--bg-2)', border: `1px solid ${c}33` }}>
      <div className="font-semibold text-sm" style={{ color: c }}>{verdict}</div>
      <div className="flex flex-wrap gap-x-4 gap-y-1 mt-1.5 text-xs" style={{ color: 'var(--text-3)' }}>
        <span>Confidence: <strong style={{ color: 'var(--text-2)' }}>{confidence}</strong> · {detail}</span>
        {trend && trend !== 'Not enough data' && <span>Trend: <strong style={{ color: 'var(--text-2)' }}>{trend}</strong></span>}
      </div>
      {flags.length > 0 && (
        <div className="flex flex-wrap gap-1.5 mt-2.5">
          {flags.map(f => <span key={f} className="badge-red">⚠ {f}</span>)}
        </div>
      )}
    </div>
  )
}

// The Bottom Line (replaces Quick Stats)

function BottomLine({ summary, gradeProbs }) {
  const r = summary?.avg_rating
  const d = summary?.avg_difficulty
  const wta = summary?.would_take_again_pct
  const a = gradeProbs?.['A range'] || 0

  const items = [
    {
      label: 'Quality',
      value: r >= 4 ? 'High' : r >= 3 ? 'Average' : 'Low',
      detail: `${r?.toFixed(1)}/5`,
      color: r >= 4 ? 'var(--green)' : r >= 3 ? 'var(--yellow)' : 'var(--red)',
    },
    {
      label: 'Difficulty',
      value: diffLabel(d || 3),
      detail: `${d?.toFixed(1)}/5`,
      color: d >= 4 ? 'var(--orange)' : 'var(--text-2)',
    },
    {
      label: 'Your grade',
      value: a >= 70 ? 'Likely an A' : a >= 50 ? 'Probably a B+' : a >= 30 ? 'Could go either way' : 'Tough grading',
      detail: a > 0 ? `${a.toFixed(0)}% get an A` : '',
      color: a >= 60 ? 'var(--green)' : a >= 40 ? 'var(--yellow)' : 'var(--text-2)',
    },
    {
      label: 'Would retake',
      value: wta >= 70 ? 'Most would' : wta >= 50 ? 'About half' : wta >= 0 ? 'Most wouldn\'t' : 'Unknown',
      detail: wta >= 0 ? `${wta?.toFixed(0)}%` : '',
      color: wta >= 60 ? 'var(--green)' : wta >= 40 ? 'var(--yellow)' : wta >= 0 ? 'var(--red)' : 'var(--text-3)',
    },
  ]

  return (
    <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
      {items.map(i => (
        <div key={i.label} className="card px-4 py-3">
          <div className="text-sm font-semibold" style={{ color: i.color }}>{i.value}</div>
          {i.detail && <div className="text-[11px] mt-0.5" style={{ color: 'var(--text-3)' }}>{i.detail}</div>}
          <div className="text-[10px] uppercase tracking-wider mt-1" style={{ color: 'var(--text-3)' }}>{i.label}</div>
        </div>
      ))}
    </div>
  )
}

// What's This Prof Like (replaces What To Expect)

function ProfVibe({ sentiment }) {
  if (!sentiment || !Object.keys(sentiment).length) return null
  const cats = Object.entries(sentiment).sort((a, b) => b[1].n_reviews - a[1].n_reviews)
  const labels = { grading: 'Grading', lectures: 'Lectures', workload: 'Workload', approachability: 'Approachability', exams: 'Exams' }

  return (
    <div className="card p-5">
      <h3 className="font-semibold text-sm mb-3" style={{ color: 'var(--text-1)' }}>What's this professor like?</h3>
      <div className="space-y-2.5">
        {cats.map(([cat, info]) => {
          const s = sentimentLabel(info.pct_positive)
          return (
            <div key={cat} className="flex items-center justify-between">
              <span className="text-sm" style={{ color: 'var(--text-2)' }}>{labels[cat] || cat}</span>
              <div className="flex items-center gap-2">
                <span className="text-sm font-semibold" style={{ color: s.color }}>{s.text}</span>
                <div className="w-20 h-1.5 rounded-full overflow-hidden" style={{ background: 'var(--bg-3)' }}>
                  <div className="h-full rounded-full" style={{ width: `${info.pct_positive}%`, background: s.color }} />
                </div>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

// Review Highlights

function ReviewHighlights({ reviews }) {
  if (!reviews?.length) return null
  return (
    <div className="card p-5">
      <h3 className="font-semibold text-sm mb-1" style={{ color: 'var(--text-1)' }}>What students say</h3>
      <p className="text-[10px] mb-3" style={{ color: 'var(--text-3)' }}>From RateMyProfessors reviews</p>
      <div className="space-y-3">
        {reviews.slice(0, 3).map((r, i) => (
          <div key={i} className="pl-3" style={{ borderLeft: '2px solid var(--border)' }}>
            <p className="text-sm leading-relaxed" style={{ color: 'var(--text-2)' }}>{r.comment?.slice(0, 280)}{r.comment?.length > 280 ? '...' : ''}</p>
            <div className="flex gap-3 mt-1.5 text-xs" style={{ color: 'var(--text-3)' }}>
              {r.class_name && <span style={{ color: 'var(--accent)' }}>{r.class_name}</span>}
              {r.grade && <span>Grade: {r.grade}</span>}
              {r.date && <span>{r.date}</span>}
              <a href="https://www.ratemyprofessors.com" target="_blank" rel="noopener noreferrer" style={{ color: 'var(--text-3)' }}>via RateMyProfessors</a>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

// Rating Over Time

function TrendChart({ gp }) {
  if (!gp || gp.insufficient_data) return null
  const data = gp.pred_dates.map((d, i) => ({ date: d, mean: gp.pred_mean[i], ci_range: [gp.pred_ci_lower[i], gp.pred_ci_upper[i]] }))

  // Plain language trend description
  const means = gp.pred_mean || []
  const first = means[0], last = means[means.length - 1]
  const diff = last - first
  let trendText = 'Ratings have been fairly stable'
  if (diff > 0.5) trendText = 'Ratings have improved noticeably over time'
  else if (diff > 0.2) trendText = 'Ratings have been trending up slightly'
  else if (diff < -0.5) trendText = 'Ratings have shifted down over time'
  else if (diff < -0.2) trendText = 'Ratings have been trending down slightly'

  return (
    <div className="card p-5">
      <h3 className="font-semibold text-sm mb-1" style={{ color: 'var(--text-1)' }}>How are they trending?</h3>
      <p className="text-xs mb-3" style={{ color: 'var(--text-3)' }}>{trendText} ({gp.n_data_points} reviews, {gp.date_range})</p>
      <ResponsiveContainer width="100%" height={180}>
        <AreaChart data={data} margin={{ top: 5, right: 5, left: -10, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="date" tick={{ fontSize: 10 }} axisLine={false} tickLine={false} />
          <YAxis domain={[1, 5]} ticks={[1, 2, 3, 4, 5]} tick={{ fontSize: 10 }} axisLine={false} tickLine={false} />
          <Tooltip formatter={(v, name) => (name === 'ci_range' ? [`${v[0]} to ${v[1]}`, '95% band'] : [v, 'Rating'])} />
          <ReferenceLine y={3.5} stroke="var(--border)" strokeDasharray="4 4" />
          <Area dataKey="ci_range" stroke="none" fill="var(--accent)" fillOpacity={0.06} type="monotone" />
          <Area dataKey="mean" stroke="var(--accent)" strokeWidth={2} fill="none" type="monotone" dot={false} />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  )
}

// Grades

function GradeChart({ grades }) {
  if (!grades || !Object.keys(grades).length) return null
  const order = ['A+','A','A-','B+','B','B-','C+','C','C-','D+','D','D-','F']
  const data = order.filter(g => grades[g]).map(g => ({ grade: g, count: grades[g] }))
  const gc = { 'A+':'#059669',A:'#10b981','A-':'#34d399','B+':'#eab308',B:'#facc15','B-':'#fde047','C+':'#f97316',C:'#fb923c','C-':'#fdba74','D+':'#ef4444',D:'#f87171','D-':'#fca5a5',F:'#dc2626' }
  const total = data.reduce((s, d) => s + d.count, 0)
  const mostCommon = data.reduce((best, d) => (d.count > (best?.count || 0) ? d : best), null)?.grade || '?'

  return (
    <div className="card p-5">
      <h3 className="font-semibold text-sm mb-1" style={{ color: 'var(--text-1)' }}>What grades do students get?</h3>
      <p className="text-xs mb-3" style={{ color: 'var(--text-3)' }}>Most common grade: {mostCommon} (from {total} self-reported grades)</p>
      <ResponsiveContainer width="100%" height={150}>
        <BarChart data={data} margin={{ top: 5, right: 5, left: -20, bottom: 0 }}>
          <XAxis dataKey="grade" tick={{ fontSize: 11 }} axisLine={false} tickLine={false} />
          <YAxis tick={{ fontSize: 10 }} axisLine={false} tickLine={false} />
          <Tooltip />
          <Bar dataKey="count" radius={[4, 4, 0, 0]}>{data.map(e => <Cell key={e.grade} fill={gc[e.grade] || '#6b7280'} />)}</Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}

// Course Breakdown

function CourseBreakdown({ classes }) {
  if (!classes?.length) return null
  return (
    <div className="card p-5">
      <h3 className="font-semibold text-sm mb-3" style={{ color: 'var(--text-1)' }}>How do they do in each course?</h3>
      <div className="space-y-0">
        {classes.slice(0, 8).map((c, i) => {
          const rc = c.avg_rating >= 4 ? 'var(--green)' : c.avg_rating >= 3 ? 'var(--yellow)' : 'var(--red)'
          return (
            <div key={c.class_name} className="flex items-center justify-between py-2" style={{ borderBottom: i < Math.min(classes.length, 8) - 1 ? '1px solid var(--border)' : 'none' }}>
              <div>
                <span className="text-sm font-medium" style={{ color: 'var(--text-1)' }}>{c.class_name}</span>
                <span className="text-xs ml-2" style={{ color: 'var(--text-3)' }}>{c.num_reviews} reviews</span>
              </div>
              {c.avg_rating && <span className="text-sm font-semibold" style={{ color: rc }}>{c.avg_rating}/5</span>}
            </div>
          )
        })}
      </div>
    </div>
  )
}

// Personal grade forecast — the headline decision-support feature. Student
// enters their GPA; we hit the forecast endpoint and show the posterior
// (most-likely grade + credible band + plain sentence). Without a GPA the
// card shows the base rate from the prof's historical distribution.
function ForecastCard({ profId, school, baseForecast }) {
  const [gpa, setGpa] = useState('')
  const [forecast, setForecast] = useState(baseForecast ? { forecast: baseForecast, explanation: null } : null)
  const [loading, setLoading] = useState(false)

  // Resolve school slug: prefer prop, fallback to URL hash pattern /school/<slug>/...
  const schoolSlug = school || (window.location.hash.match(/\/school\/([^/]+)/) || [])[1]

  const fetchForecast = (gpaValue) => {
    if (!schoolSlug || !profId) return
    setLoading(true)
    const q = gpaValue !== '' && gpaValue != null ? `?gpa=${gpaValue}` : ''
    fetch(`${API_BASE}/api/${schoolSlug}/forecast/${encodeURIComponent(profId)}${q}`)
      .then(r => r.ok ? r.json() : null)
      .then(d => { if (d) setForecast(d); setLoading(false) })
      .catch(() => setLoading(false))
  }

  const onGpaChange = (v) => {
    setGpa(v)
    if (v === '') {
      fetchForecast(null)
      return
    }
    const n = parseFloat(v)
    if (!isNaN(n) && n >= 0 && n <= 4) fetchForecast(n)
  }

  // Initial fetch if we didn't have a base forecast embedded in the prof JSON.
  useEffect(() => {
    if (!baseForecast && profId && schoolSlug) fetchForecast(null)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [profId, schoolSlug])

  if (!forecast?.forecast) return null
  const f = forecast.forecast
  const explanation = forecast.explanation

  // Posterior bars
  const bars = Object.entries(f.posterior_pct || {}).sort((a, b) => b[1] - a[1])
  const maxPct = Math.max(...bars.map(([, v]) => v), 1)

  return (
    <div className="card p-5">
      <div className="flex items-start justify-between mb-3 flex-wrap gap-3">
        <div>
          <h3 className="font-semibold text-sm" style={{ color: 'var(--text-1)' }}>What grade would you likely get?</h3>
          <p className="text-[11px]" style={{ color: 'var(--text-3)' }}>
            Uses this professor's past grade distribution and your GPA. Not a guarantee.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs" style={{ color: 'var(--text-3)' }}>Your GPA:</span>
          <input
            type="number"
            min="0" max="4" step="0.01"
            placeholder="e.g. 3.5"
            value={gpa}
            onChange={e => onGpaChange(e.target.value)}
            className="input-dark w-24 text-sm py-1.5"
          />
        </div>
      </div>

      <div className="flex items-baseline gap-3 flex-wrap">
        <div className="flex items-baseline gap-1">
          <span className="text-3xl font-bold" style={{ color: 'var(--text-1)', fontFamily: 'Iowan Old Style, Palatino Linotype, Georgia, serif' }}>
            {f.expected_gpa?.toFixed(2)}
          </span>
          <span className="text-xs" style={{ color: 'var(--text-3)' }}>expected GPA</span>
        </div>
        <div className="text-xs" style={{ color: 'var(--text-3)' }}>
          usually {f.ci_lower?.toFixed(2)}–{f.ci_upper?.toFixed(2)}
        </div>
        {loading && <span className="text-[11px]" style={{ color: 'var(--text-3)' }}>updating…</span>}
      </div>

      {explanation && (
        <p className="text-xs mt-2 leading-relaxed" style={{ color: 'var(--text-2)' }}>{explanation}</p>
      )}

      <div className="mt-4 space-y-1.5">
        {bars.map(([g, pct]) => (
          <div key={g}>
            <div className="flex justify-between text-[11px] mb-0.5">
              <span style={{ color: 'var(--text-2)' }}>{g}</span>
              <span style={{ color: 'var(--text-3)' }}>{pct}%</span>
            </div>
            <div className="h-1.5 rounded-full overflow-hidden" style={{ background: 'var(--bg-3)' }}>
              <div className="h-full rounded-full" style={{
                width: `${(pct / maxPct) * 100}%`,
                background: g === 'A range' ? 'var(--green)' : g === 'B range' ? 'var(--yellow)' : g === 'C range' ? 'var(--orange)' : 'var(--red)',
              }} />
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

// Small note that surfaces when the recency-weighted read disagrees with the
// all-time read. e.g. "Heads up: recent reviews are noticeably worse than older ones."
function RecencyNote({ recency }) {
  const good = recency?.good_rating_recent
  const wta = recency?.take_again_recent
  const notes = [good?.note, wta?.note].filter(Boolean)
  if (!notes.length) return null
  // Deduplicate — both signals often agree.
  const unique = [...new Set(notes)]
  return (
    <div className="card p-4 flex items-start gap-3" style={{ borderLeft: '3px solid var(--orange)' }}>
      <span style={{ color: 'var(--orange)' }} className="text-lg leading-none">↯</span>
      <div>
        <div className="font-semibold text-sm" style={{ color: 'var(--text-1)' }}>Pay attention to the trend</div>
        {unique.map((n, i) => (
          <p key={i} className="text-xs mt-0.5" style={{ color: 'var(--text-2)' }}>{n}</p>
        ))}
      </div>
    </div>
  )
}

// Honest-quality strip: shows the grade-inflation-adjusted rating alongside
// the raw rating, so a prof with a 4.9 raw score who only gives A's doesn't
// fool the user. Quiet when the delta is small.
function HonestQuality({ quality }) {
  if (!quality || quality.n_reviews_used < 5) return null
  const delta = quality.grade_inflation_effect
  if (Math.abs(delta) < 0.1) return null  // no meaningful correction

  const adjustedLabel = delta > 0
    ? 'adjusted for grade inflation'
    : 'adjusted for this prof\'s tough grading'
  const emoji = delta > 0.3 ? '⚠' : '·'
  const tone = delta > 0.3 ? 'var(--orange)' : 'var(--text-2)'

  return (
    <div className="card p-4 flex items-center gap-4 flex-wrap">
      <div>
        <div className="text-[10px] uppercase tracking-wider" style={{ color: 'var(--text-3)' }}>Honest rating</div>
        <div className="text-2xl font-bold" style={{ color: 'var(--text-1)', fontFamily: 'Iowan Old Style, Palatino Linotype, Georgia, serif' }}>
          {quality.adjusted_rating.toFixed(2)}<span className="text-sm font-normal" style={{ color: 'var(--text-3)' }}>/5</span>
        </div>
      </div>
      <div style={{ color: 'var(--text-3)', flex: 1, minWidth: 0 }}>
        <div className="text-xs leading-relaxed" style={{ color: tone }}>
          <span className="mr-1">{emoji}</span>
          Raw rating <strong style={{ color: 'var(--text-2)' }}>{quality.raw_mean.toFixed(2)}</strong>, {adjustedLabel} by <strong style={{ color: 'var(--text-2)' }}>{Math.abs(delta).toFixed(2)}</strong>.
        </div>
        <div className="text-[11px] mt-1" style={{ color: 'var(--text-3)' }}>
          Higher grades tend to produce higher reviews. This number asks: how would an average-grade student rate them?
        </div>
      </div>
    </div>
  )
}

// Concrete "what class is actually like" checklist extracted from review text.
// Each row: label, polarity color, confidence tag. Hidden when no attributes
// were detected — which is a feature, not a bug: students know to check
// elsewhere rather than us making stuff up.
function AttributesCard({ attributes }) {
  if (!attributes?.length) return null
  const colorFor = (polarity) =>
    polarity === 'good' ? 'var(--green)' :
    polarity === 'neutral' ? 'var(--text-2)' :
    polarity === 'bad' ? 'var(--red)' : 'var(--text-2)'
  const confLabel = {
    likely: 'Likely',
    probably: 'Probably',
    maybe: 'Mentioned',
    unsupported: 'Rare',
  }
  return (
    <div className="card p-5">
      <h3 className="font-semibold text-sm mb-1" style={{ color: 'var(--text-1)' }}>What this class is actually like</h3>
      <p className="text-[11px] mb-3" style={{ color: 'var(--text-3)' }}>Pulled from what students wrote in reviews.</p>
      <div className="space-y-2">
        {attributes.slice(0, 8).map(a => (
          <div key={a.name} className="flex items-center justify-between">
            <span className="text-sm" style={{ color: colorFor(a.polarity) }}>{a.label}</span>
            <span className="text-[11px]" style={{ color: 'var(--text-3)' }}>
              {confLabel[a.confidence] || a.confidence} · <span style={{ opacity: 0.7 }}>{a.hits}/{a.n_reviews}</span>
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}

// "Teaching this term" badge. Renders when the backend attached schedule
// data to the professor payload (currently UMD only; other schools fall back
// gracefully). This is the "binding agent" that turns the page from a history
// lookup into a registration-time decision tool.
function TeachingNow({ teaching }) {
  if (!teaching || !teaching.courses?.length) return null
  const courses = teaching.courses
  return (
    <div className="card p-4 flex items-start gap-3" style={{ borderLeft: '3px solid var(--green)' }}>
      <span style={{ color: 'var(--green)' }} className="text-lg leading-none">●</span>
      <div className="flex-1">
        <div className="font-semibold text-sm" style={{ color: 'var(--text-1)' }}>
          Teaching {teaching.term_label || 'this term'}
        </div>
        <div className="flex flex-wrap gap-1.5 mt-1.5">
          {courses.map(c => (
            <span key={c} className="text-[11px] px-2 py-0.5 rounded-md"
              style={{ background: 'var(--green-bg)', color: 'var(--green)', border: '1.5px solid rgba(154, 178, 92, 0.3)' }}>
              {c}
            </span>
          ))}
        </div>
      </div>
    </div>
  )
}

// Share button

function ShareBtn() {
  const [copied, setCopied] = useState(false)
  const copy = () => { navigator.clipboard.writeText(window.location.href); setCopied(true); setTimeout(() => setCopied(false), 2000) }
  return <button onClick={copy} className="btn-secondary text-xs">{copied ? '✓ Copied!' : '🔗 Share'}</button>
}

// "How sure are we?" — plain-language reliability card. Translates the
// calibrated posterior into a single sentence a student can act on.
function ReliabilityCard({ calibrated, numRatings }) {
  if (!calibrated) return null
  const good = calibrated.good_rating
  if (!good) return null

  const n = good.n || 0
  const ciWidth = (good.ci_upper || 1) - (good.ci_lower || 0)
  const shrink = good.shrinkage || 0

  let headline, tone
  if (n >= 50 && ciWidth < 0.2) {
    headline = 'Solid read'
    tone = 'var(--green)'
  } else if (n >= 15 && ciWidth < 0.35) {
    headline = 'Decent read'
    tone = 'var(--green)'
  } else if (n >= 5) {
    headline = 'Use with caution'
    tone = 'var(--yellow)'
  } else {
    headline = 'Too few reviews'
    tone = 'var(--orange)'
  }

  let explainer
  if (n < 5) {
    explainer = `Only ${n} usable reviews — real quality could differ a lot from what's shown.`
  } else if (shrink > 0.2) {
    explainer = `Numbers here are a bit adjusted toward ${calibrated.department_used || 'department'} norms because only ${n} students weighed in.`
  } else if (n >= 50) {
    explainer = `${n} reviews in — the numbers above should be pretty close to what you'd experience.`
  } else {
    explainer = `Based on ${n} reviews. Enough to get the gist, but could shift with more data.`
  }

  return (
    <div className="card p-5 flex items-start gap-3">
      <div className="w-9 h-9 rounded-xl flex items-center justify-center flex-shrink-0"
        style={{ background: 'var(--accent-bg)', border: '1.5px solid var(--accent-border)' }}>
        <span style={{ color: 'var(--accent)' }} className="text-base">✦</span>
      </div>
      <div>
        <div className="font-semibold text-sm" style={{ color: tone }}>{headline}</div>
        <p className="text-sm leading-relaxed mt-0.5" style={{ color: 'var(--text-2)' }}>{explainer}</p>
      </div>
    </div>
  )
}

// Tag cloud, sized by how strongly students agree, with a quiet subtitle
// rather than a bunch of numeric ranges. Tags with thin support are shown
// smaller and dimmer so users naturally downweight them.
function Tags({ tagPosteriors, topTags }) {
  // Prefer calibrated per-tag posteriors if present; fall back to raw top_tags.
  let chips = []
  if (tagPosteriors?.length) {
    chips = tagPosteriors.slice(0, 8).map(t => ({ name: t.tag, strength: t.mean, n: t.n }))
  } else if (topTags?.length) {
    const max = Math.max(...topTags.map(t => t.count || 1))
    chips = topTags.map(t => ({ name: t.tag, strength: (t.count || 1) / max, n: t.count || 1 }))
  }
  if (!chips.length) return null

  return (
    <div className="card p-5">
      <h3 className="font-semibold text-sm mb-1" style={{ color: 'var(--text-1)' }}>Students describe them as</h3>
      <p className="text-[11px] mb-3" style={{ color: 'var(--text-3)' }}>Bigger words = more students said it.</p>
      <div className="flex flex-wrap gap-1.5">
        {chips.map(t => {
          const s = Math.max(0.35, t.strength)
          const sizePx = 12 + Math.round(s * 5) // 12–17px
          return (
            <span key={t.name} className="inline-flex items-center px-2.5 py-1 rounded-lg"
              style={{
                background: `rgba(224, 139, 63, ${0.08 + s * 0.15})`,
                border: `1.5px solid rgba(224, 139, 63, ${0.18 + s * 0.32})`,
                color: 'var(--text-1)',
                fontSize: sizePx,
                fontWeight: 500,
                opacity: 0.55 + s * 0.45,
              }}>
              {t.name}
            </span>
          )
        })}
      </div>
    </div>
  )
}

// Main

export default function ProfessorDetail({ professor, school }) {
  if (!professor) return null
  const p = professor
  const flags = getRedFlags(p)

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-11 h-11 rounded-xl flex items-center justify-center text-base font-bold"
            style={{ background: 'var(--accent-bg)', color: 'var(--accent)', border: '1px solid var(--accent-border)' }}>
            {p.name?.split(' ').map(n => n[0]).join('')}
          </div>
          <div>
            <h2 className="text-lg font-bold" style={{ color: 'var(--text-1)' }}>{p.name}</h2>
            <p className="text-xs" style={{ color: 'var(--text-3)' }}>{p.department} · {p.summary?.num_ratings} reviews</p>
          </div>
        </div>
        <ShareBtn />
      </div>

      {/* Verdict */}
      <VerdictBanner verdict={p.verdict} emoji={p.verdict_emoji} confidence={p.confidence_level} detail={p.confidence_detail} trend={p.trend_summary} flags={flags} />

      {/* "Teaching X this term" — shown only when a current-term schedule
          has been scraped for this school and this prof is in it. */}
      <TeachingNow teaching={p.teaching_now} />

      {/* The Bottom Line */}
      <BottomLine summary={p.summary} gradeProbs={p.grade_probabilities} />

      {/* Plain-language reliability note */}
      <ReliabilityCard calibrated={p.calibrated_analysis} numRatings={p.summary?.num_ratings} />

      {/* Grade-inflation-adjusted quality — only renders when the correction
          is large enough to matter. */}
      <HonestQuality quality={p.quality_adjusted} />

      {/* Surfaces "recent reviews disagree with the all-time read" when it
          matters. Silent otherwise. */}
      <RecencyNote recency={p.recency} />

      {/* Personal grade forecast — student enters their GPA and sees their
          probable grade with this prof, driven by a Bayes update of the
          prof's historical grade distribution. */}
      <ForecastCard
        profId={p.professor_id}
        school={school}
        baseForecast={p.grade_forecast}
      />

      {/* Content grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
        <ProfVibe sentiment={p.category_sentiment} />
        <ReviewHighlights reviews={p.review_highlights} />
        <AttributesCard attributes={p.attributes} />
        <TrendChart gp={p.gp_trend} />
        <GradeChart grades={p.grade_distribution} />
        <CourseBreakdown classes={p.class_breakdown} />
        <Tags tagPosteriors={p.tag_posteriors} topTags={p.top_tags} />
      </div>
    </div>
  )
}
