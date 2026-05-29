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
    error.userMessage = message
    return Promise.reject(error)
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

// Settings API
export const getSettings = () => api.get('/settings')
export const updateSettings = (settings) => api.put('/settings', settings)
export const getSources = () => api.get('/settings/sources')
export const updateSource = (name, config) => api.put(`/settings/sources/${name}`, config)
export const getKeys = () => api.get('/settings/keys')
export const updateKeys = (keys) => api.put('/settings/keys', keys)
export const testSource = (name) => api.post(`/settings/sources/${name}/test`)

export default api
