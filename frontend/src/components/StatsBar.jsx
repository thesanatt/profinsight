export default function StatsBar({ stats }) {
  const items = [
    { label: 'Avg Rating', value: stats.avg_rating_across_school?.toFixed(1), suffix: '/ 5' },
    { label: 'Avg Difficulty', value: stats.avg_difficulty_across_school?.toFixed(1), suffix: '/ 5' },
    { label: 'Professors', value: stats.total_professors },
    { label: 'Reviews', value: stats.total_reviews?.toLocaleString() },
    { label: 'Departments', value: stats.departments },
  ]

  return (
    <div className="grid grid-cols-2 sm:grid-cols-5 gap-3 mb-6">
      {items.map(item => (
        <div key={item.label} className="card px-4 py-3">
          <div className="stat-value text-2xl">
            {item.value || '—'}
            {item.suffix && <span className="text-sm font-normal text-gray-400 ml-1">{item.suffix}</span>}
          </div>
          <div className="stat-label">{item.label}</div>
        </div>
      ))}
    </div>
  )
}
