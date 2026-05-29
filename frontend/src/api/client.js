import axios from 'axios'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || `${window.location.origin}/api`,
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json'
  }
})

// Response interceptor for error handling
api.interceptors.response.use(
  response => response,
  error => {
    const message = error.response?.data?.detail || error.message || 'Request failed'
    return Promise.reject(new Error(message))
  }
)

// Validate date format before API call
function _validateDateFormat(date) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(date)) {
    throw new Error(`Invalid date format: ${date}. Expected YYYY-MM-DD.`)
  }
}

export const getLatestDigest = () => api.get('/digest/latest')
export const getDigest = (date) => {
  _validateDateFormat(date)
  return api.get(`/digest/${encodeURIComponent(date)}`)
}
export const getDigests = () => api.get('/digests')
export const getItems = (params) => api.get('/items', { params })
export const triggerCollect = () => api.post('/collect')
export const getHealth = () => api.get('/health')

export default api
