import { useState } from 'react'
import {
  AreaChart, Area, BarChart, Bar, RadarChart, Radar, PolarGrid,
  PolarAngleAxis, PolarRadiusAxis, XAxis, YAxis, Tooltip,
  ResponsiveContainer, CartesianGrid, Cell, ReferenceLine,
} from 'recharts'

function getRedFlags(p) {
  const f = [], s = p.summary || {}
  if (s.would_take_again_pct != null && s.would_take_again_pct >= 0 && s.would_take_again_pct < 35) f.push('Only ' + s.would_take_again_pct.toFixed(0) + '% would take again')
  if (s.avg_rating && s.avg_rating < 2.5) f.push('Very low overall rating')
  if (s.avg_difficulty && s.avg_difficulty >= 4.5) f.push('Extremely high difficulty')
  const lec = p.category_sentiment?.lectures
  if (lec && lec.pct_positive < 30) f.push('Lectures rated poorly (' + lec.pct_positive.toFixed(0) + '% positive)')
  if (p.trend_summary?.toLowerCase().includes('declining')) f.push('Ratings declining over time')
  return f
}

function VerdictBanner({ verdict, emoji, confidence, detail, trend, flags }) {
  const colors = { great: 'var(--green)', good: 'var(--accent)', mixed: 'var(--yellow)', caution: 'var(--orange)', poor: 'var(--red)' }
  const bgs = { great: 'var(--green-bg)', good: 'var(--accent-bg)', mixed: 'var(--yellow-bg)', caution: 'var(--orange-bg)', poor: 'var(--red-bg)' }
  const c = colors[emoji] || 'var(--text-2)'
  return (
    <div className="rounded-xl p-4" style={{ background: bgs[emoji] || 'var(--bg-2)', border: `1px solid color-mix(in srgb, ${c} 20%, transparent)` }}>
      <div className="font-semibold text-sm" style={{ color: c }}>{verdict}</div>
      <div className="flex flex-wrap gap-x-4 gap-y-1 mt-1.5 text-xs" style={{ color: 'var(--text-3)' }}>
        <span>Confidence: <strong style={{ color: 'var(--text-2)' }}>{confidence}</strong> — {detail}</span>
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

function QuickStats({ summary, gradeProbs }) {
  const r = summary?.avg_rating
  const rc = r >= 4 ? 'var(--green)' : r >= 3 ? 'var(--yellow)' : 'var(--red)'
  const wta = summary?.would_take_again_pct
  const wc = wta >= 60 ? 'var(--green)' : wta >= 40 ? 'var(--yellow)' : 'var(--red)'
  const a = gradeProbs?.['A range'] || 0
  const items = [
    { label: 'Quality', val: r?.toFixed(1), sub: '/5', color: rc },
    { label: 'Difficulty', val: summary?.avg_difficulty?.toFixed(1), sub: '/5' },
    { label: 'Reviews', val: summary?.num_ratings },
    { label: 'Would retake', val: wta >= 0 ? wta?.toFixed(0) + '%' : '—', color: wta >= 0 ? wc : null },
    { label: 'Chance of A', val: a > 0 ? a.toFixed(0) + '%' : '—', color: a >= 60 ? 'var(--green)' : null },
  ]
  return (
    <div className="grid grid-cols-2 sm:grid-cols-5 gap-2">
      {items.map(i => (
        <div key={i.label} className="card px-4 py-3">
          <div className="text-2xl font-bold" style={{ color: i.color || 'var(--text-1)' }}>
            {i.val || '—'}{i.sub && <span className="text-sm font-normal ml-0.5" style={{ color: 'var(--text-3)' }}>{i.sub}</span>}
          </div>
          <div className="text-[10px] uppercase tracking-wider mt-0.5" style={{ color: 'var(--text-3)' }}>{i.label}</div>
        </div>
      ))}
    </div>
  )
}

function WhatToExpect({ sentiment }) {
  if (!sentiment || !Object.keys(sentiment).length) return null
  const cats = Object.entries(sentiment).sort((a, b) => b[1].n_reviews - a[1].n_reviews)
  const icons = { grading: '📝', lectures: '🎓', workload: '📚', approachability: '💬', exams: '📋' }
  return (
    <div className="card p-5">
      <h3 className="font-semibold text-sm mb-3" style={{ color: 'var(--text-1)' }}>What to expect</h3>
      <div className="space-y-3">
        {cats.map(([cat, info]) => {
          const pct = info.pct_positive
          const c = pct >= 70 ? 'var(--green)' : pct >= 50 ? 'var(--yellow)' : 'var(--red)'
          return (
            <div key={cat}>
              <div className="flex items-center justify-between mb-1">
                <span className="text-sm" style={{ color: 'var(--text-2)' }}>{icons[cat] || '📌'} {cat.charAt(0).toUpperCase() + cat.slice(1)}</span>
                <span className="text-xs font-semibold" style={{ color: c }}>{pct.toFixed(0)}% positive</span>
              </div>
              <div className="h-1.5 rounded-full overflow-hidden" style={{ background: 'var(--bg-3)' }}>
                <div className="h-full rounded-full" style={{ width: `${pct}%`, background: c }} />
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

function ReviewHighlights({ reviews }) {
  if (!reviews?.length) return null
  return (
    <div className="card p-5">
      <h3 className="font-semibold text-sm mb-3" style={{ color: 'var(--text-1)' }}>What students are saying</h3>
      <div className="space-y-3">
        {reviews.map((r, i) => (
          <div key={i} className="pl-3" style={{ borderLeft: '2px solid var(--border)' }}>
            <p className="text-sm leading-relaxed" style={{ color: 'var(--text-2)' }}>{r.comment}</p>
            <div className="flex gap-3 mt-1.5 text-xs" style={{ color: 'var(--text-3)' }}>
              {r.class_name && <span style={{ color: 'var(--accent)' }}>{r.class_name}</span>}
              {r.grade && <span>Grade: {r.grade}</span>}
              {r.date && <span>{r.date}</span>}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

function TrendChart({ gp }) {
  if (!gp || gp.insufficient_data) return null
  const data = gp.pred_dates.map((d, i) => ({ date: d, mean: gp.pred_mean[i], ci_range: [gp.pred_ci_lower[i], gp.pred_ci_upper[i]] }))
  return (
    <div className="card p-5">
      <h3 className="font-semibold text-sm mb-1" style={{ color: 'var(--text-1)' }}>Rating trend</h3>
      <p className="text-xs mb-3" style={{ color: 'var(--text-3)' }}>{gp.n_data_points} data points · {gp.date_range}</p>
      <ResponsiveContainer width="100%" height={200}>
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

function GradeChart({ grades }) {
  if (!grades || !Object.keys(grades).length) return null
  const order = ['A+','A','A-','B+','B','B-','C+','C','C-','D+','D','D-','F']
  const data = order.filter(g => grades[g]).map(g => ({ grade: g, count: grades[g] }))
  const gc = { 'A+':'#059669',A:'#10b981','A-':'#34d399','B+':'#eab308',B:'#facc15','B-':'#fde047','C+':'#f97316',C:'#fb923c','C-':'#fdba74','D+':'#ef4444',D:'#f87171','D-':'#fca5a5',F:'#dc2626' }
  return (
    <div className="card p-5">
      <h3 className="font-semibold text-sm mb-3" style={{ color: 'var(--text-1)' }}>Grade distribution</h3>
      <ResponsiveContainer width="100%" height={160}>
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

function CourseBreakdown({ classes }) {
  if (!classes?.length) return null
  return (
    <div className="card p-5">
      <h3 className="font-semibold text-sm mb-3" style={{ color: 'var(--text-1)' }}>By course</h3>
      <div className="space-y-0">
        {classes.slice(0, 8).map((c, i) => {
          const rc = c.avg_rating >= 4 ? 'var(--green)' : c.avg_rating >= 3 ? 'var(--yellow)' : 'var(--red)'
          return (
            <div key={c.class_name} className="flex items-center justify-between py-2" style={{ borderBottom: i < Math.min(classes.length, 8) - 1 ? '1px solid var(--border)' : 'none' }}>
              <div>
                <span className="text-sm font-medium" style={{ color: 'var(--text-1)' }}>{c.class_name}</span>
                <span className="text-xs ml-2" style={{ color: 'var(--text-3)' }}>{c.num_reviews} reviews</span>
              </div>
              <div className="flex items-center gap-3">
                {Object.keys(c.grades || {})[0] && <span className="text-xs" style={{ color: 'var(--text-3)' }}>Common: {Object.keys(c.grades)[0]}</span>}
                {c.avg_rating && <span className="text-sm font-semibold" style={{ color: rc }}>{c.avg_rating}/5</span>}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

function Tags({ tags }) {
  if (!tags?.length) return null
  const max = Math.max(...tags.map(t => t.count || 1))
  return (
    <div className="card p-5">
      <h3 className="font-semibold text-sm mb-3" style={{ color: 'var(--text-1)' }}>Common tags</h3>
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

function ShareBtn() {
  const [copied, setCopied] = useState(false)
  const copy = () => { navigator.clipboard.writeText(window.location.href); setCopied(true); setTimeout(() => setCopied(false), 2000) }
  return <button onClick={copy} className="btn-secondary text-xs">{copied ? '✓ Copied!' : '🔗 Share'}</button>
}

function BayesianSection({ analysis, sentiment }) {
  const [open, setOpen] = useState(false)
  if (!analysis) return null
  const posteriors = analysis.rating_posteriors || {}
  return (
    <div className="card">
      <button onClick={() => setOpen(!open)} className="w-full flex items-center justify-between px-5 py-4 text-left">
        <div>
          <h3 className="font-semibold text-sm" style={{ color: 'var(--text-1)' }}>Bayesian analysis</h3>
          <p className="text-xs" style={{ color: 'var(--text-3)' }}>Beta-Binomial posteriors · Naive Bayes · GP regression</p>
        </div>
        <svg className={`w-4 h-4 transition-transform ${open ? 'rotate-180' : ''}`} style={{ color: 'var(--text-3)' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>
      {open && (
        <div className="px-5 pb-5 space-y-3 pt-3" style={{ borderTop: '1px solid var(--border)' }}>
          {Object.entries(posteriors).map(([level, p]) => (
            <div key={level}>
              <div className="flex justify-between text-xs mb-1">
                <span style={{ color: 'var(--text-2)' }}>P({level}) — rating ≥ {p.threshold}</span>
                <span className="font-mono" style={{ color: 'var(--text-1)' }}>{(p.mean*100).toFixed(1)}%  <span style={{ color: 'var(--text-3)' }}>[{(p.ci_lower*100).toFixed(0)}%, {(p.ci_upper*100).toFixed(0)}%]</span></span>
              </div>
              <div className="h-1.5 rounded-full overflow-hidden" style={{ background: 'var(--bg-3)' }}>
                <div className="h-full rounded-full" style={{ width: `${p.mean*100}%`, background: 'var(--accent)', opacity: 0.6 }} />
              </div>
            </div>
          ))}
          {sentiment && Object.keys(sentiment).length > 0 && (
            <div className="mt-4">
              <p className="text-xs font-medium mb-2" style={{ color: 'var(--text-3)' }}>Naive Bayes category sentiment</p>
              <ResponsiveContainer width="100%" height={220}>
                <RadarChart data={Object.entries(sentiment).map(([c, i]) => ({ category: c.charAt(0).toUpperCase() + c.slice(1), sentiment: i.mean_sentiment }))}>
                  <PolarGrid stroke="var(--border)" />
                  <PolarAngleAxis dataKey="category" tick={{ fontSize: 11 }} />
                  <PolarRadiusAxis domain={[0, 5]} tick={{ fontSize: 9 }} />
                  <Radar dataKey="sentiment" stroke="var(--accent)" fill="var(--accent)" fillOpacity={0.08} strokeWidth={2} />
                </RadarChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default function ProfessorDetail({ professor }) {
  if (!professor) return null
  const p = professor
  const flags = getRedFlags(p)

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-11 h-11 rounded-xl flex items-center justify-center text-base font-bold"
            style={{ background: 'var(--accent-bg)', color: 'var(--accent)', border: '1px solid var(--accent-border)' }}>
            {p.name?.split(' ').map(n => n[0]).join('')}
          </div>
          <div>
            <h2 className="text-lg font-bold" style={{ color: 'var(--text-1)' }}>{p.name}</h2>
            <p className="text-xs" style={{ color: 'var(--text-3)' }}>{p.department}</p>
          </div>
        </div>
        <ShareBtn />
      </div>
      <VerdictBanner verdict={p.verdict} emoji={p.verdict_emoji} confidence={p.confidence_level} detail={p.confidence_detail} trend={p.trend_summary} flags={flags} />
      <QuickStats summary={p.summary} gradeProbs={p.grade_probabilities} />
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
        <WhatToExpect sentiment={p.category_sentiment} />
        <ReviewHighlights reviews={p.review_highlights} />
        <TrendChart gp={p.gp_trend} />
        <GradeChart grades={p.grade_distribution} />
        <CourseBreakdown classes={p.class_breakdown} />
        <Tags tags={p.top_tags} />
      </div>
      <BayesianSection analysis={p.bayesian_analysis} sentiment={p.category_sentiment} />
    </div>
  )
}
