import { useState } from 'react'
import {
  AreaChart, Area, BarChart, Bar, RadarChart, Radar, PolarGrid,
  PolarAngleAxis, PolarRadiusAxis, XAxis, YAxis, Tooltip,
  ResponsiveContainer, CartesianGrid, Cell, ReferenceLine,
} from 'recharts'

// ─── Verdict Banner ──────────────────────────────────────────────────────────

const verdictStyles = {
  great:   { bg: 'bg-emerald-50', border: 'border-emerald-200', text: 'text-emerald-800', icon: '✓', iconBg: 'bg-emerald-500' },
  good:    { bg: 'bg-blue-50', border: 'border-blue-200', text: 'text-blue-800', icon: '↑', iconBg: 'bg-blue-500' },
  mixed:   { bg: 'bg-amber-50', border: 'border-amber-200', text: 'text-amber-800', icon: '~', iconBg: 'bg-amber-500' },
  caution: { bg: 'bg-orange-50', border: 'border-orange-200', text: 'text-orange-800', icon: '!', iconBg: 'bg-orange-500' },
  poor:    { bg: 'bg-red-50', border: 'border-red-200', text: 'text-red-800', icon: '✕', iconBg: 'bg-red-500' },
}

function VerdictBanner({ verdict, emoji, confidence, confidenceDetail, trend }) {
  const s = verdictStyles[emoji] || verdictStyles.mixed
  return (
    <div className={`${s.bg} border ${s.border} rounded-xl px-5 py-4`}>
      <div className="flex items-start gap-3">
        <div className={`w-8 h-8 rounded-lg ${s.iconBg} flex items-center justify-center text-white font-bold text-sm flex-shrink-0 mt-0.5`}>
          {s.icon}
        </div>
        <div>
          <div className={`font-semibold ${s.text}`}>{verdict}</div>
          <div className="flex flex-wrap gap-x-4 gap-y-1 mt-1.5 text-xs text-gray-500">
            <span>Confidence: <strong className="text-gray-700">{confidence}</strong> — {confidenceDetail}</span>
            {trend && trend !== 'Not enough data' && (
              <span>Trend: <strong className="text-gray-700">{trend}</strong></span>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

// ─── Quick Stats Row ─────────────────────────────────────────────────────────

function QuickStats({ summary, gradeProbs }) {
  const rating = summary?.avg_rating
  const ratingColor = rating >= 4 ? 'text-emerald-600' : rating >= 3 ? 'text-amber-600' : 'text-red-500'
  const wta = summary?.would_take_again_pct
  const wtaColor = wta >= 60 ? 'text-emerald-600' : wta >= 40 ? 'text-amber-600' : 'text-red-500'
  const aRange = gradeProbs?.['A range'] || 0

  return (
    <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
      <Stat label="Quality" value={rating?.toFixed(1)} sub="/5" color={ratingColor} />
      <Stat label="Difficulty" value={summary?.avg_difficulty?.toFixed(1)} sub="/5" />
      <Stat label="Reviews" value={summary?.num_ratings} />
      <Stat label="Would take again" value={wta >= 0 ? `${wta?.toFixed(0)}%` : '—'} color={wta >= 0 ? wtaColor : ''} />
      <Stat label="Chance of A" value={aRange > 0 ? `${aRange.toFixed(0)}%` : '—'} color={aRange >= 60 ? 'text-emerald-600' : ''} />
    </div>
  )
}

function Stat({ label, value, sub, color }) {
  return (
    <div className="bg-white rounded-xl border border-gray-100 px-4 py-3">
      <div className={`text-2xl font-bold ${color || 'text-gray-900'}`}>
        {value || '—'}
        {sub && <span className="text-sm font-normal text-gray-300 ml-0.5">{sub}</span>}
      </div>
      <div className="text-[10px] text-gray-400 uppercase tracking-wider mt-0.5">{label}</div>
    </div>
  )
}

// ─── What To Expect (Category Sentiment) ─────────────────────────────────────

function WhatToExpect({ sentiment }) {
  if (!sentiment || !Object.keys(sentiment).length) return null
  const categories = Object.entries(sentiment).sort((a, b) => b[1].n_reviews - a[1].n_reviews)
  const labels = { grading: 'Grading', lectures: 'Lectures', workload: 'Workload', approachability: 'Approachability', exams: 'Exams' }
  const icons = { grading: '📝', lectures: '🎓', workload: '📚', approachability: '💬', exams: '📋' }

  return (
    <div className="bg-white rounded-xl border border-gray-100 p-5">
      <h3 className="font-semibold text-gray-900 mb-3">What to expect</h3>
      <div className="space-y-3">
        {categories.map(([cat, info]) => {
          const pct = info.pct_positive
          const color = pct >= 70 ? 'bg-emerald-500' : pct >= 50 ? 'bg-amber-500' : 'bg-red-400'
          const textColor = pct >= 70 ? 'text-emerald-600' : pct >= 50 ? 'text-amber-600' : 'text-red-500'
          return (
            <div key={cat}>
              <div className="flex items-center justify-between mb-1">
                <span className="text-sm text-gray-700">
                  {icons[cat] || '📌'} {labels[cat] || cat}
                </span>
                <span className={`text-sm font-semibold ${textColor}`}>{pct.toFixed(0)}% positive</span>
              </div>
              <div className="h-1.5 bg-gray-100 rounded-full overflow-hidden">
                <div className={`h-full rounded-full ${color}`} style={{ width: `${pct}%` }} />
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
    <div className="bg-white rounded-xl border border-gray-100 p-5">
      <h3 className="font-semibold text-gray-900 mb-3">What students are saying</h3>
      <div className="space-y-3">
        {reviews.map((r, i) => (
          <div key={i} className="border-l-2 border-gray-200 pl-3">
            <p className="text-sm text-gray-700 leading-relaxed">{r.comment}</p>
            <div className="flex gap-3 mt-1.5 text-xs text-gray-400">
              {r.class_name && <span className="font-medium text-gray-500">{r.class_name}</span>}
              {r.grade && <span>Grade: {r.grade}</span>}
              {r.date && <span>{r.date}</span>}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

// ─── Course Breakdown ────────────────────────────────────────────────────────

function CourseBreakdown({ classes }) {
  if (!classes?.length) return null
  return (
    <div className="bg-white rounded-xl border border-gray-100 p-5">
      <h3 className="font-semibold text-gray-900 mb-3">By course</h3>
      <div className="space-y-2">
        {classes.slice(0, 8).map(c => {
          const rColor = c.avg_rating >= 4 ? 'text-emerald-600' : c.avg_rating >= 3 ? 'text-amber-600' : 'text-red-500'
          const topGrade = Object.keys(c.grades || {})[0]
          return (
            <div key={c.class_name} className="flex items-center justify-between py-1.5 border-b border-gray-50 last:border-0">
              <div>
                <span className="text-sm font-medium text-gray-800">{c.class_name}</span>
                <span className="text-xs text-gray-400 ml-2">{c.num_reviews} reviews</span>
              </div>
              <div className="flex items-center gap-3">
                {topGrade && <span className="text-xs text-gray-400">Most common: {topGrade}</span>}
                {c.avg_rating && <span className={`text-sm font-semibold ${rColor}`}>{c.avg_rating}/5</span>}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

// ─── Grade Distribution ──────────────────────────────────────────────────────

function GradeChart({ grades }) {
  if (!grades || !Object.keys(grades).length) return null
  const order = ['A+', 'A', 'A-', 'B+', 'B', 'B-', 'C+', 'C', 'C-', 'D+', 'D', 'D-', 'F']
  const data = order.filter(g => grades[g]).map(g => ({ grade: g, count: grades[g] }))
  const colors = {
    'A+': '#059669', A: '#10b981', 'A-': '#34d399',
    'B+': '#f59e0b', B: '#fbbf24', 'B-': '#fcd34d',
    'C+': '#f97316', C: '#fb923c', 'C-': '#fdba74',
    'D+': '#ef4444', D: '#f87171', 'D-': '#fca5a5', F: '#dc2626',
  }
  return (
    <div className="bg-white rounded-xl border border-gray-100 p-5">
      <h3 className="font-semibold text-gray-900 mb-3">Grade distribution</h3>
      <ResponsiveContainer width="100%" height={160}>
        <BarChart data={data} margin={{ top: 5, right: 5, left: -20, bottom: 0 }}>
          <XAxis dataKey="grade" tick={{ fontSize: 11, fill: '#6b7280' }} axisLine={false} tickLine={false} />
          <YAxis tick={{ fontSize: 10, fill: '#9ca3af' }} axisLine={false} tickLine={false} />
          <Tooltip contentStyle={{ borderRadius: 8, border: '1px solid #e5e7eb', fontSize: 12 }} />
          <Bar dataKey="count" radius={[4, 4, 0, 0]}>
            {data.map(e => <Cell key={e.grade} fill={colors[e.grade] || '#6b7280'} />)}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}

// ─── GP Trend ────────────────────────────────────────────────────────────────

function TrendChart({ gp }) {
  if (!gp || gp.insufficient_data) return null
  const data = gp.pred_dates.map((d, i) => ({
    date: d, mean: gp.pred_mean[i],
    ci_range: [gp.pred_ci_lower[i], gp.pred_ci_upper[i]],
  }))
  return (
    <div className="bg-white rounded-xl border border-gray-100 p-5">
      <h3 className="font-semibold text-gray-900 mb-1">Rating trend</h3>
      <p className="text-xs text-gray-400 mb-3">{gp.n_data_points} data points · {gp.date_range}</p>
      <ResponsiveContainer width="100%" height={200}>
        <AreaChart data={data} margin={{ top: 5, right: 5, left: -10, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" />
          <XAxis dataKey="date" tick={{ fontSize: 10, fill: '#9ca3af' }} axisLine={false} tickLine={false} />
          <YAxis domain={[1, 5]} ticks={[1, 2, 3, 4, 5]} tick={{ fontSize: 10, fill: '#9ca3af' }} axisLine={false} tickLine={false} />
          <Tooltip contentStyle={{ borderRadius: 8, fontSize: 12 }}
            formatter={(val, name) => name === 'ci_range' ? [`${val[0].toFixed(1)}–${val[1].toFixed(1)}`, '95% range'] : [val.toFixed(2), 'Rating']} />
          <ReferenceLine y={3.5} stroke="#e5e7eb" strokeDasharray="4 4" />
          <Area dataKey="ci_range" stroke="none" fill="#6366f1" fillOpacity={0.08} type="monotone" />
          <Area dataKey="mean" stroke="#6366f1" strokeWidth={2} fill="none" type="monotone" dot={false} />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  )
}

// ─── Tags ────────────────────────────────────────────────────────────────────

function Tags({ tags }) {
  if (!tags?.length) return null
  const max = Math.max(...tags.map(t => t.count || 1))
  return (
    <div className="bg-white rounded-xl border border-gray-100 p-5">
      <h3 className="font-semibold text-gray-900 mb-3">Common tags</h3>
      <div className="flex flex-wrap gap-2">
        {tags.map(t => {
          const intensity = Math.max(0.3, (t.count || 1) / max)
          return (
            <span key={t.tag} className="px-2.5 py-1 rounded-lg text-xs border"
              style={{
                backgroundColor: `rgba(99, 102, 241, ${intensity * 0.1})`,
                borderColor: `rgba(99, 102, 241, ${intensity * 0.25})`,
                color: `rgba(55, 48, 163, ${0.5 + intensity * 0.5})`,
              }}>
              {t.tag} <span className="opacity-50">{t.count}</span>
            </span>
          )
        })}
      </div>
    </div>
  )
}

// ─── Bayesian Deep Dive (expandable) ─────────────────────────────────────────

function BayesianSection({ analysis, sentiment }) {
  const [open, setOpen] = useState(false)
  if (!analysis) return null
  const posteriors = analysis.rating_posteriors || {}

  return (
    <div className="bg-white rounded-xl border border-gray-100">
      <button onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between px-5 py-4 text-left">
        <div>
          <h3 className="font-semibold text-gray-900 text-sm">Bayesian analysis details</h3>
          <p className="text-xs text-gray-400">Beta-Binomial posteriors · Naive Bayes classification · GP regression</p>
        </div>
        <svg className={`w-5 h-5 text-gray-400 transition-transform ${open ? 'rotate-180' : ''}`}
          fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>
      {open && (
        <div className="px-5 pb-5 space-y-4 border-t border-gray-50 pt-4">
          {/* Posteriors */}
          <div>
            <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">Rating posteriors</h4>
            {Object.entries(posteriors).map(([level, p]) => (
              <div key={level} className="mb-2">
                <div className="flex justify-between text-xs mb-0.5">
                  <span className="text-gray-600">P({level}) — rating ≥ {p.threshold}</span>
                  <span className="font-mono text-gray-800">{(p.mean * 100).toFixed(1)}% [{(p.ci_lower * 100).toFixed(0)}%, {(p.ci_upper * 100).toFixed(0)}%]</span>
                </div>
                <div className="h-1.5 bg-gray-100 rounded-full overflow-hidden">
                  <div className="h-full bg-indigo-500 rounded-full" style={{ width: `${p.mean * 100}%`, opacity: 0.7 }} />
                </div>
              </div>
            ))}
          </div>
          {/* Category Sentiment Radar */}
          {sentiment && Object.keys(sentiment).length > 0 && (
            <div>
              <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">Naive Bayes category sentiment</h4>
              <ResponsiveContainer width="100%" height={220}>
                <RadarChart data={Object.entries(sentiment).map(([c, i]) => ({
                  category: c.charAt(0).toUpperCase() + c.slice(1), sentiment: i.mean_sentiment,
                }))}>
                  <PolarGrid stroke="#e5e7eb" />
                  <PolarAngleAxis dataKey="category" tick={{ fontSize: 11, fill: '#6b7280' }} />
                  <PolarRadiusAxis domain={[0, 5]} tick={{ fontSize: 9, fill: '#9ca3af' }} />
                  <Radar dataKey="sentiment" stroke="#6366f1" fill="#6366f1" fillOpacity={0.12} strokeWidth={2} />
                </RadarChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// ─── Main ────────────────────────────────────────────────────────────────────

export default function ProfessorDetail({ professor }) {
  if (!professor) return null
  const p = professor

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center gap-4 mb-2">
        <div className="w-12 h-12 rounded-xl bg-indigo-50 flex items-center justify-center text-indigo-600 font-bold text-lg">
          {p.name?.split(' ').map(n => n[0]).join('')}
        </div>
        <div>
          <h2 className="text-xl font-bold text-gray-900">{p.name}</h2>
          <p className="text-sm text-gray-400">{p.department}</p>
        </div>
      </div>

      {/* Verdict */}
      <VerdictBanner
        verdict={p.verdict} emoji={p.verdict_emoji}
        confidence={p.confidence_level} confidenceDetail={p.confidence_detail}
        trend={p.trend_summary}
      />

      {/* Quick Stats */}
      <QuickStats summary={p.summary} gradeProbs={p.grade_probabilities} />

      {/* Main content grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <WhatToExpect sentiment={p.category_sentiment} />
        <ReviewHighlights reviews={p.review_highlights} />
        <TrendChart gp={p.gp_trend} />
        <GradeChart grades={p.grade_distribution} />
        <CourseBreakdown classes={p.class_breakdown} />
        <Tags tags={p.top_tags} />
      </div>

      {/* Expandable Bayesian section */}
      <BayesianSection analysis={p.bayesian_analysis} sentiment={p.category_sentiment} />
    </div>
  )
}
