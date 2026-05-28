<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from '../composables/useI18n.js'

defineProps({
  theme: {
    type: String,
    default: 'dark'
  }
})

const emit = defineEmits(['toggle-theme'])
const router = useRouter()
const mobileMenuOpen = ref(false)
const { locale, localeLabel, setLocale, t } = useI18n()

function toggleLocale() {
  setLocale(locale.value === 'en' ? 'zh' : 'en')
}

function navigate(path) {
  router.push(path)
  mobileMenuOpen.value = false
}
</script>

<template>
  <header class="navbar">
    <div class="navbar-inner container">
      <!-- Logo -->
      <a href="/" class="navbar-brand" @click.prevent="navigate('/')">
        <span class="brand-icon">W</span>
        <span class="brand-text">WYCA</span>
      </a>

      <!-- Desktop Nav -->
      <nav class="navbar-nav" aria-label="Main navigation">
        <a
          href="/"
          class="nav-link"
          :class="{ active: router.currentRoute.value.path === '/' }"
          @click.prevent="navigate('/')"
        >
          <span class="nav-icon">
            <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
              <path d="M8 1.5l6 5v7.5a1 1 0 01-1 1H3a1 1 0 01-1-1V6.5l6-5zm0 1.2L3 6.5V14h10V6.5L8 2.7z"/>
            </svg>
          </span>
          {{ t('nav.today') }}
        </a>
        <a
          href="/settings"
          class="nav-link"
          :class="{ active: router.currentRoute.value.path === '/settings' }"
          @click.prevent="navigate('/settings')"
        >
          <span class="nav-icon">
            <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
              <path d="M8 4.754a3.246 3.246 0 100 6.492 3.246 3.246 0 000-6.492zM5.754 8a2.246 2.246 0 114.492 0 2.246 2.246 0 01-4.492 0z"/>
              <path d="M9.796 1.343c-.527-1.79-3.065-1.79-3.592 0l-.094.319a.873.873 0 01-1.255.52l-.292-.16c-1.64-.892-3.433.902-2.54 2.541l.159.292a.873.873 0 01-.52 1.255l-.319.094c-1.79.527-1.79 3.065 0 3.592l.319.094a.873.873 0 01.52 1.255l-.16.292c-.892 1.64.901 3.434 2.541 2.54l.292-.159a.873.873 0 011.255.52l.094.319c.527 1.79 3.065 1.79 3.592 0l.094-.319a.873.873 0 011.255-.52l.292.16c1.64.893 3.434-.902 2.54-2.541l-.159-.292a.873.873 0 01.52-1.255l.319-.094c1.79-.527 1.79-3.065 0-3.592l-.319-.094a.873.873 0 01-.52-1.255l.16-.292c.893-1.64-.902-3.433-2.541-2.54l-.292.159a.873.873 0 01-1.255-.52l-.094-.319zm-2.633.283c.246-.835 1.428-.835 1.674 0l.094.319a1.873 1.873 0 002.693 1.115l.291-.16c.764-.415 1.6.42 1.184 1.185l-.159.292a1.873 1.873 0 001.116 2.692l.318.094c.835.246.835 1.428 0 1.674l-.319.094a1.873 1.873 0 00-1.115 2.693l.16.291c.415.764-.421 1.6-1.185 1.184l-.291-.159a1.873 1.873 0 00-2.693 1.116l-.094.318c-.246.835-1.428.835-1.674 0l-.094-.319a1.873 1.873 0 00-2.692-1.115l-.292.16c-.764.415-1.6-.421-1.184-1.185l.159-.291A1.873 1.873 0 001.945 8.93l-.319-.094c-.835-.246-.835-1.428 0-1.674l.319-.094A1.873 1.873 0 003.06 4.377l-.16-.292c-.415-.764.42-1.6 1.185-1.184l.292.159a1.873 1.873 0 002.692-1.115l.094-.319z"/>
            </svg>
          </span>
          {{ t('nav.settings') }}
        </a>
      </nav>

      <!-- Actions -->
      <div class="navbar-actions">
        <button
          class="locale-toggle"
          @click="toggleLocale"
          :aria-label="localeLabel"
          :title="localeLabel"
        >
          {{ localeLabel }}
        </button>
        <button
          class="theme-toggle"
          @click="emit('toggle-theme')"
          :aria-label="theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'"
          :title="theme === 'dark' ? 'Light mode' : 'Dark mode'"
        >
          <!-- Sun icon for dark mode (click to go light) -->
          <svg v-if="theme === 'dark'" class="theme-icon" width="18" height="18" viewBox="0 0 16 16" fill="currentColor">
            <path d="M8 12a4 4 0 100-8 4 4 0 000 8zM8 0a.75.75 0 01.75.75v1.5a.75.75 0 01-1.5 0V.75A.75.75 0 018 0zm0 13a.75.75 0 01.75.75v1.5a.75.75 0 01-1.5 0v-1.5A.75.75 0 018 13zM2.343 2.343a.75.75 0 011.061 0l1.06 1.061a.75.75 0 01-1.06 1.06l-1.06-1.06a.75.75 0 010-1.06zm9.193 9.193a.75.75 0 011.06 0l1.061 1.06a.75.75 0 01-1.06 1.061l-1.061-1.06a.75.75 0 010-1.061zM16 8a.75.75 0 01-.75.75h-1.5a.75.75 0 010-1.5h1.5A.75.75 0 0116 8zM3 8a.75.75 0 01-.75.75H.75a.75.75 0 010-1.5h1.5A.75.75 0 013 8zm10.657-5.657a.75.75 0 010 1.061l-1.061 1.06a.75.75 0 11-1.06-1.06l1.06-1.06a.75.75 0 011.06 0zM4.464 11.536a.75.75 0 010 1.06l-1.06 1.061a.75.75 0 01-1.061-1.06l1.06-1.061a.75.75 0 011.061 0z"/>
          </svg>
          <!-- Moon icon for light mode (click to go dark) -->
          <svg v-else class="theme-icon" width="18" height="18" viewBox="0 0 16 16" fill="currentColor">
            <path d="M9.598 1.591a.75.75 0 01.785-.175 7.001 7.001 0 01-2.698 13.046.75.75 0 01-.98-.98 5.5 5.5 0 002.096-7.046.75.75 0 01.175-.786zm1.616 1.945a7 7 0 01-7.678 7.678 5.499 5.499 0 107.678-7.678z"/>
          </svg>
        </button>

        <!-- Mobile menu toggle -->
        <button
          class="mobile-toggle"
          @click="mobileMenuOpen = !mobileMenuOpen"
          :aria-expanded="mobileMenuOpen"
          aria-label="Toggle navigation menu"
        >
          <svg v-if="!mobileMenuOpen" width="20" height="20" viewBox="0 0 16 16" fill="currentColor">
            <path d="M1 2.75A.75.75 0 011.75 2h12.5a.75.75 0 010 1.5H1.75A.75.75 0 011 2.75zm0 5A.75.75 0 011.75 7h12.5a.75.75 0 010 1.5H1.75A.75.75 0 011 7.75zM1.75 12h12.5a.75.75 0 010 1.5H1.75a.75.75 0 010-1.5z"/>
          </svg>
          <svg v-else width="20" height="20" viewBox="0 0 16 16" fill="currentColor">
            <path d="M3.72 3.72a.75.75 0 011.06 0L8 6.94l3.22-3.22a.75.75 0 111.06 1.06L9.06 8l3.22 3.22a.75.75 0 11-1.06 1.06L8 9.06l-3.22 3.22a.75.75 0 01-1.06-1.06L6.94 8 3.72 4.78a.75.75 0 010-1.06z"/>
          </svg>
        </button>
      </div>

      <!-- Mobile Nav -->
      <transition name="mobile-menu">
        <nav v-if="mobileMenuOpen" class="navbar-nav-mobile" aria-label="Mobile navigation">
          <a
            href="/"
            class="nav-link-mobile"
            :class="{ active: router.currentRoute.value.path === '/' }"
            @click.prevent="navigate('/')"
          >
            {{ t('nav.today') }}
          </a>
          <a
            href="/settings"
            class="nav-link-mobile"
            :class="{ active: router.currentRoute.value.path === '/settings' }"
            @click.prevent="navigate('/settings')"
          >
            {{ t('nav.settings') }}
          </a>
        </nav>
      </transition>
    </div>
  </header>
</template>

<style scoped>
.navbar {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  height: var(--nav-height);
  background: rgba(13, 17, 23, 0.8);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border-bottom: 1px solid var(--color-border);
  z-index: 100;
  transition: background-color var(--duration-normal) var(--ease-out);
}

[data-theme="light"] .navbar {
  background: rgba(255, 255, 255, 0.85);
}

.navbar-inner {
  display: flex;
  align-items: center;
  height: 100%;
  gap: var(--space-8);
}

/* Brand */
.navbar-brand {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  text-decoration: none;
  color: var(--color-text-primary);
  flex-shrink: 0;
}

.brand-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  background: var(--color-accent);
  color: #ffffff;
  font-weight: 800;
  font-size: var(--text-base);
  border-radius: var(--radius-md);
  letter-spacing: -0.5px;
}

.brand-text {
  font-weight: 700;
  font-size: var(--text-lg);
  letter-spacing: var(--tracking-tight);
}

/* Desktop Nav */
.navbar-nav {
  display: none;
  align-items: center;
  gap: var(--space-1);
}

@media (min-width: 640px) {
  .navbar-nav {
    display: flex;
  }
}

.nav-link {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3);
  font-size: var(--text-sm);
  font-weight: 500;
  color: var(--color-text-secondary);
  text-decoration: none;
  border-radius: var(--radius-md);
  transition: all var(--duration-fast) var(--ease-out);
}

.nav-link:hover {
  color: var(--color-text-primary);
  background: var(--color-bg-tertiary);
}

.nav-link.active {
  color: var(--color-text-primary);
  background: var(--color-accent-subtle);
}

.nav-icon {
  display: flex;
  align-items: center;
  opacity: 0.7;
}

.nav-link.active .nav-icon {
  opacity: 1;
  color: var(--color-accent);
}

/* Actions */
.navbar-actions {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin-left: auto;
}

.theme-toggle {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  color: var(--color-text-secondary);
  border-radius: var(--radius-md);
  transition: all var(--duration-fast) var(--ease-out);
}

.theme-toggle:hover {
  color: var(--color-text-primary);
  background: var(--color-bg-tertiary);
}

.theme-icon {
  transition: transform var(--duration-normal) var(--ease-out);
}

.theme-toggle:hover .theme-icon {
  transform: rotate(15deg);
}

/* Locale Toggle */
.locale-toggle {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 36px;
  padding: 0 var(--space-3);
  font-size: var(--text-xs);
  font-weight: 600;
  color: var(--color-text-secondary);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-full);
  transition: all var(--duration-fast) var(--ease-out);
}

.locale-toggle:hover {
  color: var(--color-text-primary);
  border-color: var(--color-text-muted);
  background: var(--color-bg-tertiary);
}

/* Mobile */
.mobile-toggle {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  color: var(--color-text-secondary);
  border-radius: var(--radius-md);
}

@media (min-width: 640px) {
  .mobile-toggle {
    display: none;
  }
}

.mobile-toggle:hover {
  color: var(--color-text-primary);
  background: var(--color-bg-tertiary);
}

/* Mobile Nav Dropdown */
.navbar-nav-mobile {
  position: absolute;
  top: var(--nav-height);
  left: 0;
  right: 0;
  background: var(--color-bg-secondary);
  border-bottom: 1px solid var(--color-border);
  padding: var(--space-2);
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

@media (min-width: 640px) {
  .navbar-nav-mobile {
    display: none !important;
  }
}

.nav-link-mobile {
  display: block;
  padding: var(--space-3) var(--space-4);
  font-size: var(--text-sm);
  font-weight: 500;
  color: var(--color-text-secondary);
  text-decoration: none;
  border-radius: var(--radius-md);
  transition: all var(--duration-fast) var(--ease-out);
}

.nav-link-mobile:hover,
.nav-link-mobile.active {
  color: var(--color-text-primary);
  background: var(--color-bg-tertiary);
}

/* Mobile menu transition */
.mobile-menu-enter-active,
.mobile-menu-leave-active {
  transition: opacity var(--duration-fast) var(--ease-out),
              transform var(--duration-fast) var(--ease-out);
}

.mobile-menu-enter-from,
.mobile-menu-leave-to {
  opacity: 0;
  transform: translateY(-8px);
}
</style>
