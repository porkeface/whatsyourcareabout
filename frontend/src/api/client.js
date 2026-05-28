import axios from 'axios'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api',
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
    console.error('[API Error]', message)
    return Promise.reject(error)
  }
)

export const getLatestDigest = () => api.get('/digest/latest')
export const getDigest = (date) => api.get(`/digest/${date}`)
export const getDigests = () => api.get('/digests')
export const getItems = (params) => api.get('/items', { params })
export const triggerCollect = () => api.post('/collect')
export const getHealth = () => api.get('/health')

export default api
