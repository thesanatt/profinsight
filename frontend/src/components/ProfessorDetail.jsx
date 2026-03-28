import { useState } from 'react'
import {
  AreaChart, Area, BarChart, Bar, XAxis, YAxis, Tooltip,
  ResponsiveContainer, CartesianGrid, Cell, ReferenceLine,
} from 'recharts'

// ─── Helpers ─────────────────────────────────────────────────────────────────

function sentimentLabel(pct) {
  if (pct >= 80) return { text: 'Great', color: 'var(--green)' }
  if (pct >= 60) return { text: 'Good', color: '#8be78b' }
  if (pct >= 45) return { text: 'Mixed', color: 'var(--yellow)' }
  if (pct >= 30) return { text: 'Weak', color: 'var(--orange)' }
  return { text: 'Poor', color: 'var(--red)' }
}

function diffLabel(d) {
  if (d >= 4.5) return 'Very hard'
  if (d >= 3.5) return 'Hard'
  if (d >= 2.5) return 'Medium'
  if (d >= 1.5) return 'Easy'
  return 'Very easy'
}

function getRedFlags(p) {
  const f = [], s = p.summary || {}
  if (s.would_take_again_pct != null && s.would_take_again_pct >= 0 && s.would_take_again_pct < 35) f.push('Only ' + s.would_take_again_pct.toFixed(0) + '% would take again')
  if (s.avg_rating && s.avg_rating < 2.5) f.push('Very low overall rating')
  if (s.avg_difficulty && s.avg_difficulty >= 4.5) f.push('Extremely difficult')
  const lec = p.category_sentiment?.lectures
  if (lec && lec.pct_positive < 30) f.push('Lectures rated poorly')
  if (p.trend_summary?.toLowerCase().includes('declining')) f.push('Ratings have been declining')
  return f
}

// ─── Verdict Banner ──────────────────────────────────────────────────────────

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

// ─── The Bottom Line (replaces Quick Stats) ──────────────────────────────────

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

// ─── What's This Prof Like (replaces What To Expect) ─────────────────────────

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

// ─── Review Highlights ───────────────────────────────────────────────────────

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

// ─── Rating Over Time ────────────────────────────────────────────────────────

function TrendChart({ gp }) {
  if (!gp || gp.insufficient_data) return null
  const data = gp.pred_dates.map((d, i) => ({ date: d, mean: gp.pred_mean[i], ci_range: [gp.pred_ci_lower[i], gp.pred_ci_upper[i]] }))

  // Plain language trend description
  const means = gp.pred_mean || []
  const first = means[0], last = means[means.length - 1]
  const diff = last - first
  let trendText = 'Ratings have been fairly stable'
  if (diff > 0.5) trendText = 'Ratings have improved significantly over time'
  else if (diff > 0.2) trendText = 'Ratings have been trending up slightly'
  else if (diff < -0.5) trendText = 'Ratings have dropped significantly over time'
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
          <Tooltip />
          <ReferenceLine y={3.5} stroke="var(--border)" strokeDasharray="4 4" />
          <Area dataKey="ci_range" stroke="none" fill="var(--accent)" fillOpacity={0.06} type="monotone" />
          <Area dataKey="mean" stroke="var(--accent)" strokeWidth={2} fill="none" type="monotone" dot={false} />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  )
}

// ─── Grades ──────────────────────────────────────────────────────────────────

function GradeChart({ grades }) {
  if (!grades || !Object.keys(grades).length) return null
  const order = ['A+','A','A-','B+','B','B-','C+','C','C-','D+','D','D-','F']
  const data = order.filter(g => grades[g]).map(g => ({ grade: g, count: grades[g] }))
  const gc = { 'A+':'#059669',A:'#10b981','A-':'#34d399','B+':'#eab308',B:'#facc15','B-':'#fde047','C+':'#f97316',C:'#fb923c','C-':'#fdba74','D+':'#ef4444',D:'#f87171','D-':'#fca5a5',F:'#dc2626' }
  const total = data.reduce((s, d) => s + d.count, 0)
  const mostCommon = data[0]?.grade || '?'

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

// ─── Course Breakdown ────────────────────────────────────────────────────────

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

// ─── Tags ────────────────────────────────────────────────────────────────────

function Tags({ tags }) {
  if (!tags?.length) return null
  const max = Math.max(...tags.map(t => t.count || 1))
  return (
    <div className="card p-5">
      <h3 className="font-semibold text-sm mb-3" style={{ color: 'var(--text-1)' }}>Students describe them as</h3>
      <div className="flex flex-wrap gap-1.5">
        {tags.map(t => {
          const a = Math.max(0.25, (t.count || 1) / max)
          return (
            <span key={t.tag} className="px-2.5 py-1 rounded-lg text-xs"
              style={{ background: `rgba(201,160,255,${a * 0.1})`, border: `1px solid rgba(201,160,255,${a * 0.2})`, color: `rgba(224,193,255,${0.45 + a * 0.55})` }}>
              {t.tag} <span style={{ opacity: 0.45 }}>{t.count}</span>
            </span>
          )
        })}
      </div>
    </div>
  )
}

// ─── Share + Bayesian Deep Dive ──────────────────────────────────────────────

function ShareBtn() {
  const [copied, setCopied] = useState(false)
  const copy = () => { navigator.clipboard.writeText(window.location.href); setCopied(true); setTimeout(() => setCopied(false), 2000) }
  return <button onClick={copy} className="btn-secondary text-xs">{copied ? '✓ Copied!' : '🔗 Share'}</button>
}

function BayesianDetails({ analysis }) {
  const [open, setOpen] = useState(false)
  if (!analysis) return null
  const posteriors = analysis.rating_posteriors || {}
  return (
    <div className="card">
      <button onClick={() => setOpen(!open)} className="w-full flex items-center justify-between px-5 py-3 text-left">
        <span className="text-xs" style={{ color: 'var(--text-3)' }}>Show statistical details (Bayesian analysis)</span>
        <svg className={`w-4 h-4 transition-transform ${open ? 'rotate-180' : ''}`} style={{ color: 'var(--text-3)' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>
      {open && (
        <div className="px-5 pb-4 space-y-2" style={{ borderTop: '1px solid var(--border)' }}>
          <p className="text-[11px] pt-3 mb-2" style={{ color: 'var(--text-3)' }}>
            These are Beta-Binomial posterior probabilities. The confidence interval shows the range where the true value likely falls.
          </p>
          {Object.entries(posteriors).map(([level, p]) => (
            <div key={level}>
              <div className="flex justify-between text-xs mb-1">
                <span style={{ color: 'var(--text-2)' }}>P({level}), rating ≥ {p.threshold}</span>
                <span className="font-mono" style={{ color: 'var(--text-1)' }}>{(p.mean*100).toFixed(1)}% <span style={{ color: 'var(--text-3)' }}>[{(p.ci_lower*100).toFixed(0)}%, {(p.ci_upper*100).toFixed(0)}%]</span></span>
              </div>
              <div className="h-1.5 rounded-full overflow-hidden" style={{ background: 'var(--bg-3)' }}>
                <div className="h-full rounded-full" style={{ width: `${p.mean*100}%`, background: 'var(--accent)', opacity: 0.6 }} />
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ─── Main ────────────────────────────────────────────────────────────────────

export default function ProfessorDetail({ professor }) {
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

      {/* The Bottom Line */}
      <BottomLine summary={p.summary} gradeProbs={p.grade_probabilities} />

      {/* Content grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
        <ProfVibe sentiment={p.category_sentiment} />
        <ReviewHighlights reviews={p.review_highlights} />
        <TrendChart gp={p.gp_trend} />
        <GradeChart grades={p.grade_distribution} />
        <CourseBreakdown classes={p.class_breakdown} />
        <Tags tags={p.top_tags} />
      </div>

      {/* Nerdy details (collapsed) */}
      <BayesianDetails analysis={p.bayesian_analysis} />
    </div>
  )
}
