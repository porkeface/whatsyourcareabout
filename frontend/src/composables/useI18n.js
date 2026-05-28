import { computed } from 'vue'
import { useLocalStorage } from '@vueuse/core'
import en from '../locales/en.json'
import zh from '../locales/zh.json'

const messages = { en, zh }

// Module-level singleton — shared across all components
const locale = useLocalStorage('wyca-locale', 'en')

function resolveKey(obj, path) {
  return path.split('.').reduce((acc, key) => acc?.[key], obj)
}

export function t(key, params = {}) {
  const value = resolveKey(messages[locale.value] || messages.en, key)
  if (value === undefined) return key
  if (typeof value !== 'string') return key
  return value.replace(/\{(\w+)\}/g, (_, name) =>
    params[name] !== undefined ? params[name] : `{${name}}`
  )
}

export function useI18n() {
  const localeLabel = computed(() => locale.value === 'en' ? '中文' : 'EN')

  function setLocale(code) {
    locale.value = code
  }

  return { locale, localeLabel, setLocale, t }
}
