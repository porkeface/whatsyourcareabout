<script setup>
import { ref, watch, onMounted } from 'vue'
import { usePreferredDark, useLocalStorage } from '@vueuse/core'
import NavBar from './components/NavBar.vue'
import { useI18n } from './composables/useI18n.js'

const { t, locale } = useI18n()

const prefersDark = usePreferredDark()
const theme = useLocalStorage('wyca-theme', 'dark')

const resolvedTheme = ref('dark')

function applyTheme(newTheme) {
  resolvedTheme.value = newTheme
  document.documentElement.setAttribute('data-theme', newTheme)
}

function toggleTheme() {
  const next = resolvedTheme.value === 'dark' ? 'light' : 'dark'
  theme.value = next
  applyTheme(next)
}

onMounted(() => {
  applyTheme(theme.value)
  document.documentElement.lang = locale.value === 'zh' ? 'zh-CN' : 'en'
})

watch(locale, (newLocale) => {
  document.documentElement.lang = newLocale === 'zh' ? 'zh-CN' : 'en'
})

watch(prefersDark, (isDark) => {
  if (theme.value === 'auto') {
    applyTheme(isDark ? 'dark' : 'light')
  }
})
</script>

<template>
  <div class="app-shell">
    <NavBar :theme="resolvedTheme" @toggle-theme="toggleTheme" />
    <main class="main-content">
      <router-view v-slot="{ Component }">
        <transition name="page" mode="out-in">
          <component :is="Component" />
        </transition>
      </router-view>
    </main>
    <footer class="app-footer">
      <div class="container">
        <p class="footer-text">
          <span class="footer-logo">WYCA</span>
          <span class="footer-separator">&middot;</span>
          <span>{{ t('footer.tagline') }}</span>
          <span class="footer-separator">&middot;</span>
          <span class="footer-status">v1.0</span>
        </p>
      </div>
    </footer>
  </div>
</template>

<style scoped>
.app-shell {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
}

.main-content {
  flex: 1;
  padding-top: var(--nav-height);
}

/* Page transitions */
.page-enter-active,
.page-leave-active {
  transition: opacity var(--duration-normal) var(--ease-out),
              transform var(--duration-normal) var(--ease-out);
}

.page-enter-from {
  opacity: 0;
  transform: translateY(8px);
}

.page-leave-to {
  opacity: 0;
  transform: translateY(-8px);
}

/* Footer */
.app-footer {
  border-top: 1px solid var(--color-border);
  padding: var(--space-6) 0;
  margin-top: var(--space-16);
}

.footer-text {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
  font-size: var(--text-sm);
  color: var(--color-text-muted);
  flex-wrap: wrap;
}

.footer-logo {
  font-weight: 700;
  color: var(--color-accent);
  letter-spacing: var(--tracking-wide);
}

.footer-separator {
  opacity: 0.4;
}

.footer-status {
  font-size: var(--text-xs);
  opacity: 0.6;
}
</style>
