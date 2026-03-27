// In dev, Vite proxy handles /api -> localhost:8000
// In production, we hit the Render backend directly
export const API_BASE = import.meta.env.VITE_API_URL || ''
