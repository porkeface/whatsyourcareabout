<script setup>
import { ref, onMounted } from 'vue'
import { getHealth, triggerCollect, getDigests, getSources, updateSource, getKeys } from '../api/client.js'
import { useI18n } from '../composables/useI18n.js'

const { t } = useI18n()

// State
const healthStatus = ref(null)
const collecting = ref(false)
const collectMessage = ref('')
const collectMessageType = ref('info')
const recentDigests = ref([])
const loading = ref(true)

// Real data
const sources = ref({})
const apiKeys = ref([])
const savingSource = ref(null)
const expandedSources = ref({})

const sourceMeta = {
  hacker_news: { label: 'Hacker News', emoji: '🔶' },
  reddit: { label: 'Reddit', emoji: '🤖' },
  arxiv: { label: 'arXiv', emoji: '📄' },
  github_trending: { label: 'GitHub Trending', emoji: '⭐' },
  rss: { label: 'RSS Feeds', emoji: '📡' },
  newsapi: { label: 'NewsAPI', emoji: '📰' },
  finnhub: { label: 'Finnhub', emoji: '💰' },
  rsshub: { label: 'RSSHub', emoji: '🔗' },
  dailyhot: { label: 'DailyHotApi', emoji: '🔥' },
}

function getSourceLabel(name) {
  return sourceMeta[name]?.label || name
}

function getSourceEmoji(name) {
  return sourceMeta[name]?.emoji || '📌'
}

function hasRoutes(name) {
  const source = sources.value[name]
  return source && (source.routes || source.feeds)
}

function getRoutes(name) {
  const source = sources.value[name]
  return source?.routes || source?.feeds || []
}

function toggleExpand(name) {
  expandedSources.value[name] = !expandedSources.value[name]
}

async function loadHealth() {
  try {
    const response = await getHealth()
    healthStatus.value = response.data
  } catch {
    healthStatus.value = { status: 'disconnected' }
  }
}

async function loadDigests() {
  try {
    const response = await getDigests()
    recentDigests.value = (response.data || []).slice(0, 10)
  } catch {
    recentDigests.value = []
  }
}

async function loadSources() {
  try {
    const response = await getSources()
    sources.value = response.data?.sources || {}
  } catch {
    sources.value = {}
  }
}

async function loadKeys() {
  try {
    const response = await getKeys()
    apiKeys.value = response.data || []
  } catch {
    apiKeys.value = []
  }
}

async function toggleSource(name) {
  const source = sources.value[name]
  if (!source) return

  savingSource.value = name
  try {
    await updateSource(name, { enabled: !source.enabled })
    sources.value[name] = { ...source, enabled: !source.enabled }
  } catch (err) {
    console.error('Failed to toggle source:', err)
  } finally {
    savingSource.value = null
  }
}

async function toggleRoute(sourceName, routeIndex) {
  const source = sources.value[sourceName]
  if (!source) return

  const key = source.routes ? 'routes' : 'feeds'
  const routes = JSON.parse(JSON.stringify(source[key] || []))
  const route = routes[routeIndex]
  if (!route) return

  route.enabled = route.enabled === undefined ? false : !route.enabled

  try {
    await updateSource(sourceName, { [key]: routes })
    sources.value[sourceName] = { ...source, [key]: routes }
  } catch (err) {
    console.error('Failed to toggle route:', err)
  }
}

async function updateSourceWeight(name, weight) {
  const source = sources.value[name]
  if (!source) return

  const parsed = parseFloat(weight)
  if (isNaN(parsed)) return

  try {
    await updateSource(name, { weight: parsed })
    sources.value[name] = { ...source, weight: parsed }
  } catch (err) {
    console.error('Failed to update weight:', err)
  }
}

async function updateSourceMaxItems(name, maxItems) {
  const source = sources.value[name]
  if (!source) return

  const parsed = parseInt(maxItems)
  if (isNaN(parsed)) return

  try {
    await updateSource(name, { max_items: parsed })
    sources.value[name] = { ...source, max_items: parsed }
  } catch (err) {
    console.error('Failed to update max_items:', err)
  }
}

async function handleCollect() {
  collecting.value = true
  collectMessage.value = ''
  collectMessageType.value = 'info'

  try {
    const response = await triggerCollect()
    collectMessage.value = response.data?.status === 'started' ? t('settings.collectionStarted') : 'Collection triggered'
    collectMessageType.value = 'success'
  } catch (err) {
    collectMessage.value = err.userMessage || err.response?.data?.detail || t('settings.collectionFallback')
    collectMessageType.value = 'warning'
  } finally {
    collecting.value = false
    setTimeout(() => {
      collectMessage.value = ''
    }, 5000)
  }
}

onMounted(async () => {
  loading.value = true
  await Promise.all([loadHealth(), loadDigests(), loadSources(), loadKeys()])
  loading.value = false
})
</script>

<template>
  <div class="settings-view">
    <section class="settings-header">
      <div class="container">
        <h1 class="page-title animate-slide-up">{{ t('settings.title') }}</h1>
        <p class="page-subtitle">{{ t('settings.subtitle') }}</p>
      </div>
    </section>

    <div class="settings-grid container">
      <!-- API Status -->
      <section class="settings-card">
        <div class="card-header">
          <h2 class="card-title">
            <svg width="18" height="18" viewBox="0 0 16 16" fill="currentColor">
              <path d="M8 0a8 8 0 110 16A8 8 0 018 0zM1.5 8a6.5 6.5 0 1013 0 6.5 6.5 0 00-13 0z"/>
              <path d="M8 4a.75.75 0 01.75.75v3.5a.75.75 0 01-1.5 0v-3.5A.75.75 0 018 4zm0 8a1 1 0 100-2 1 1 0 000 2z"/>
            </svg>
            {{ t('settings.apiStatus') }}
          </h2>
          <span
            class="status-badge"
            :style="{ color: healthStatus?.status === 'ok' ? 'var(--color-success)' : 'var(--color-warning)' }"
          >
            <span class="status-dot" :style="{ background: healthStatus?.status === 'ok' ? 'var(--color-success)' : 'var(--color-warning)' }"></span>
            {{ healthStatus?.status === 'ok' ? t('settings.connected') : healthStatus?.status === 'disconnected' ? t('settings.disconnected') : t('settings.checking') }}
          </span>
        </div>
        <div class="card-body" v-if="healthStatus">
          <div class="status-grid">
            <div class="status-item">
              <span class="status-label">{{ t('settings.version') }}</span>
              <span class="status-value">{{ healthStatus.version || '1.0.0' }}</span>
            </div>
            <div class="status-item">
              <span class="status-label">{{ t('settings.lastRun') }}</span>
              <span class="status-value">{{ healthStatus.last_run || 'N/A' }}</span>
            </div>
          </div>
        </div>
      </section>

      <!-- Collect Button -->
      <section class="settings-card">
        <div class="card-header">
          <h2 class="card-title">
            <svg width="18" height="18" viewBox="0 0 16 16" fill="currentColor">
              <path d="M8 2a.75.75 0 01.75.75v4.5h4.5a.75.75 0 010 1.5h-4.5v4.5a.75.75 0 01-1.5 0v-4.5h-4.5a.75.75 0 010-1.5h4.5v-4.5A.75.75 0 018 2z"/>
            </svg>
            {{ t('settings.triggerCollection') }}
          </h2>
        </div>
        <div class="card-body">
          <p class="card-description">
            {{ t('settings.triggerDescription') }}
          </p>
          <button
            class="collect-btn"
            @click="handleCollect"
            :disabled="collecting"
          >
            <svg v-if="collecting" class="spinner" width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
              <path d="M8 0a8 8 0 100 16A8 8 0 008 0zm0 2a6 6 0 110 12A6 6 0 018 2z" opacity="0.2"/>
              <path d="M8 0a8 8 0 018 8h-2a6 6 0 00-6-6V0z"/>
            </svg>
            {{ collecting ? t('settings.collecting') : t('settings.startCollection') }}
          </button>
          <transition name="fade">
            <div
              v-if="collectMessage"
              class="collect-message"
              :class="collectMessageType"
            >
              {{ collectMessage }}
            </div>
          </transition>
        </div>
      </section>

      <!-- Sources -->
      <section class="settings-card full-width">
        <div class="card-header">
          <h2 class="card-title">
            <svg width="18" height="18" viewBox="0 0 16 16" fill="currentColor">
              <path d="M2 2.5A2.5 2.5 0 014.5 0h8.75a.75.75 0 01.75.75v12.5a.75.75 0 01-.75.75h-2.5a.75.75 0 110-1.5h1.75v-2h-8a1 1 0 00-.714 1.7.75.75 0 01-1.072 1.05A2.495 2.495 0 012 11.5v-9zm10.5-1h-8a1 1 0 00-1 1v6.708A2.486 2.486 0 014.5 9h8V1.5z"/>
            </svg>
            {{ t('settings.sources') }}
          </h2>
        </div>
        <div class="card-body">
          <div class="sources-list">
            <div
              v-for="(source, name) in sources"
              :key="name"
              class="source-item"
            >
              <div class="source-row">
                <div class="source-info">
                  <button
                    v-if="hasRoutes(name)"
                    class="expand-btn"
                    @click="toggleExpand(name)"
                    :aria-expanded="expandedSources[name]"
                  >
                    <svg width="12" height="12" viewBox="0 0 16 16" fill="currentColor" :class="{ rotated: expandedSources[name] }">
                      <path d="M6.22 3.22a.75.75 0 011.06 0l4.25 4.25a.75.75 0 010 1.06l-4.25 4.25a.75.75 0 01-1.06-1.06L9.94 8 6.22 4.28a.75.75 0 010-1.06z"/>
                    </svg>
                  </button>
                  <span class="source-emoji">{{ getSourceEmoji(name) }}</span>
                  <span class="source-name">{{ getSourceLabel(name) }}</span>
                  <span class="route-count" v-if="hasRoutes(name)">
                    {{ t('settings.routeCount', { count: getRoutes(name).length }) }}
                  </span>
                </div>
                <div class="source-controls">
                  <div class="source-param">
                    <label class="param-label">{{ t('settings.weight') }}</label>
                    <input
                      type="number"
                      class="param-input"
                      :value="source.weight || 1.0"
                      min="0"
                      max="2"
                      step="0.1"
                      @change="updateSourceWeight(name, $event.target.value)"
                    />
                  </div>
                  <div class="source-param">
                    <label class="param-label">{{ t('settings.maxItems') }}</label>
                    <input
                      type="number"
                      class="param-input"
                      :value="source.max_items || 20"
                      min="1"
                      max="100"
                      @change="updateSourceMaxItems(name, $event.target.value)"
                    />
                  </div>
                  <button
                    class="toggle-btn"
                    :class="{ active: source.enabled }"
                    :disabled="savingSource === name"
                    @click="toggleSource(name)"
                  >
                    <span class="toggle-track">
                      <span class="toggle-thumb"></span>
                    </span>
                    <span class="toggle-label">{{ source.enabled ? t('settings.enable') : t('settings.disable') }}</span>
                  </button>
                </div>
              </div>

              <!-- Nested routes -->
              <transition name="expand">
                <div v-if="expandedSources[name] && hasRoutes(name)" class="routes-list">
                  <div
                    v-for="(route, idx) in getRoutes(name)"
                    :key="idx"
                    class="route-item"
                  >
                    <div class="route-info">
                      <span class="route-name">{{ route.name }}</span>
                      <span class="route-path">{{ route.path || route.url }}</span>
                      <span class="route-domain" v-if="route.domain">{{ route.domain }}</span>
                    </div>
                    <button
                      class="route-toggle"
                      :class="{ active: route.enabled !== false }"
                      @click="toggleRoute(name, idx)"
                    >
                      <span class="toggle-track-sm">
                        <span class="toggle-thumb-sm"></span>
                      </span>
                    </button>
                  </div>
                </div>
              </transition>
            </div>
          </div>
        </div>
      </section>

      <!-- API Keys -->
      <section class="settings-card full-width">
        <div class="card-header">
          <h2 class="card-title">
            <svg width="18" height="18" viewBox="0 0 16 16" fill="currentColor">
              <path d="M0 8a4 4 0 018 0 4 4 0 01-8 0zm4-2.5a2.5 2.5 0 100 5 2.5 2.5 0 000-5zM13.5 8a1.5 1.5 0 11-3 0 1.5 1.5 0 013 0z"/>
              <path d="M2 13.5V12a2 2 0 012-2h8a2 2 0 012 2v1.5a.5.5 0 01-.5.5h-11a.5.5 0 01-.5-.5z"/>
            </svg>
            {{ t('settings.apiKeys') }}
          </h2>
        </div>
        <div class="card-body">
          <p class="card-description muted">
            {{ t('settings.apiKeysEnvHint') }}
          </p>
          <div class="keys-list">
            <div
              v-for="key in apiKeys"
              :key="key.key"
              class="key-item"
            >
              <div class="key-info">
                <span class="key-name">{{ key.name }}</span>
                <span class="key-value">{{ key.masked || t('settings.notSet') }}</span>
              </div>
              <span
                class="key-status"
                :class="{ configured: key.configured }"
              >
                {{ key.configured ? t('settings.configured') : t('settings.notSet') }}
              </span>
            </div>
          </div>
        </div>
      </section>

      <!-- Recent Digests -->
      <section class="settings-card full-width">
        <div class="card-header">
          <h2 class="card-title">
            <svg width="18" height="18" viewBox="0 0 16 16" fill="currentColor">
              <path d="M2.5 1A1.5 1.5 0 001 2.5v11A1.5 1.5 0 002.5 15h11a1.5 1.5 0 001.5-1.5v-11A1.5 1.5 0 0013.5 1h-11zM2 2.5a.5.5 0 01.5-.5h11a.5.5 0 01.5.5v11a.5.5 0 01-.5.5h-11a.5.5 0 01-.5-.5v-11z"/>
              <path d="M4 5.5a.5.5 0 01.5-.5h7a.5.5 0 010 1h-7a.5.5 0 01-.5-.5zm0 3a.5.5 0 01.5-.5h7a.5.5 0 010 1h-7a.5.5 0 01-.5-.5zm0 3a.5.5 0 01.5-.5h4a.5.5 0 010 1h-4a.5.5 0 01-.5-.5z"/>
            </svg>
            {{ t('settings.recentDigests') }}
          </h2>
        </div>
        <div class="card-body">
          <div class="digests-list" v-if="recentDigests.length > 0">
            <a
              v-for="d in recentDigests"
              :key="d.date"
              :href="`/digest/${d.date}`"
              class="digest-item"
              @click.prevent="$router.push(`/digest/${d.date}`)"
            >
              <span class="digest-date">{{ d.date }}</span>
              <span class="digest-count">{{ d.item_count }} {{ t('settings.items') }}</span>
              <svg width="14" height="14" viewBox="0 0 16 16" fill="currentColor" class="digest-arrow">
                <path d="M8.22 3.22a.75.75 0 011.06 0l4.25 4.25a.75.75 0 010 1.06l-4.25 4.25a.75.75 0 01-1.06-1.06L11.94 8 8.22 4.28a.75.75 0 010-1.06z"/>
              </svg>
            </a>
          </div>
          <p v-else class="empty-text">{{ t('settings.noDigests') }}</p>
        </div>
      </section>
    </div>
  </div>
</template>

<style scoped>
.settings-header {
  padding: var(--space-12) 0 var(--space-8);
}

.page-title {
  font-size: var(--text-3xl);
  font-weight: 800;
  letter-spacing: var(--tracking-tight);
  margin-bottom: var(--space-2);
}

.page-subtitle {
  font-size: var(--text-base);
  color: var(--color-text-secondary);
}

/* Grid */
.settings-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: var(--space-6);
  padding-bottom: var(--space-12);
}

@media (min-width: 768px) {
  .settings-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

/* Cards */
.settings-card {
  background: var(--color-bg-card);
  border: 1px solid var(--color-border-subtle);
  border-radius: var(--radius-xl);
  overflow: hidden;
}

.settings-card.full-width {
  grid-column: 1 / -1;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-5) var(--space-6);
  border-bottom: 1px solid var(--color-border-subtle);
}

.card-title {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--text-base);
  font-weight: 600;
  color: var(--color-text-primary);
}

.card-title svg {
  color: var(--color-accent);
  opacity: 0.8;
}

.card-body {
  padding: var(--space-5) var(--space-6);
}

.card-description {
  font-size: var(--text-sm);
  color: var(--color-text-secondary);
  margin-bottom: var(--space-4);
  line-height: var(--leading-relaxed);
}

.card-description.muted {
  color: var(--color-text-muted);
}

/* Status Badge */
.status-badge {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--text-sm);
  font-weight: 500;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: var(--radius-full);
  animation: pulse 2s infinite;
}

.status-dot-sm {
  width: 6px;
  height: 6px;
  border-radius: var(--radius-full);
  display: inline-block;
}

.status-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-4);
}

.status-item {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.status-label {
  font-size: var(--text-xs);
  color: var(--color-text-muted);
  text-transform: uppercase;
  letter-spacing: var(--tracking-wide);
}

.status-value {
  font-family: var(--font-mono);
  font-size: var(--text-sm);
  color: var(--color-text-primary);
}

/* Collect Button */
.collect-btn {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-3) var(--space-5);
  font-size: var(--text-sm);
  font-weight: 600;
  color: #ffffff;
  background: var(--color-accent);
  border-radius: var(--radius-md);
  transition: all var(--duration-fast) var(--ease-out);
}

.collect-btn:hover:not(:disabled) {
  background: var(--color-accent-hover);
  box-shadow: var(--shadow-glow);
}

.collect-btn:disabled {
  opacity: 0.7;
  cursor: not-allowed;
}

.spinner {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.collect-message {
  margin-top: var(--space-3);
  padding: var(--space-3) var(--space-4);
  font-size: var(--text-sm);
  border-radius: var(--radius-md);
}

.collect-message.success {
  color: var(--color-success);
  background: rgba(63, 185, 80, 0.1);
}

.collect-message.warning {
  color: var(--color-warning);
  background: rgba(210, 153, 34, 0.1);
}

.collect-message.error {
  color: var(--color-error);
  background: rgba(248, 81, 73, 0.1);
}

.fade-enter-active, .fade-leave-active {
  transition: opacity var(--duration-fast);
}
.fade-enter-from, .fade-leave-to {
  opacity: 0;
}

/* Sources */
.sources-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.source-item {
  padding: var(--space-3) var(--space-4);
  border-radius: var(--radius-md);
  transition: background var(--duration-fast) var(--ease-out);
}

.source-item:hover {
  background: var(--color-bg-tertiary);
}

.source-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4);
  flex-wrap: wrap;
}

.source-info {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.source-emoji {
  font-size: var(--text-lg);
}

.source-name {
  font-weight: 600;
  font-size: var(--text-sm);
  color: var(--color-text-primary);
}

.source-controls {
  display: flex;
  align-items: center;
  gap: var(--space-4);
}

.source-param {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.param-label {
  font-size: 10px;
  color: var(--color-text-muted);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.param-input {
  width: 60px;
  padding: var(--space-1) var(--space-2);
  font-size: var(--text-xs);
  font-family: var(--font-mono);
  background: var(--color-bg-input);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  color: var(--color-text-primary);
  text-align: center;
}

.param-input:focus {
  outline: none;
  border-color: var(--color-accent);
}

/* Toggle Button */
.toggle-btn {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-1) var(--space-2);
  border-radius: var(--radius-md);
  transition: all var(--duration-fast) var(--ease-out);
}

.toggle-btn:hover {
  background: var(--color-bg-tertiary);
}

.toggle-track {
  position: relative;
  width: 36px;
  height: 20px;
  background: var(--color-bg-tertiary);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-full);
  transition: all var(--duration-fast) var(--ease-out);
}

.toggle-btn.active .toggle-track {
  background: var(--color-accent);
  border-color: var(--color-accent);
}

.toggle-thumb {
  position: absolute;
  top: 2px;
  left: 2px;
  width: 14px;
  height: 14px;
  background: white;
  border-radius: var(--radius-full);
  transition: transform var(--duration-fast) var(--ease-out);
}

.toggle-btn.active .toggle-thumb {
  transform: translateX(16px);
}

.toggle-label {
  font-size: var(--text-xs);
  font-weight: 500;
  color: var(--color-text-secondary);
}

.toggle-btn.active .toggle-label {
  color: var(--color-accent);
}

/* Expand button */
.expand-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  color: var(--color-text-muted);
  transition: all var(--duration-fast) var(--ease-out);
}

.expand-btn:hover {
  color: var(--color-text-primary);
}

.expand-btn svg {
  transition: transform var(--duration-fast) var(--ease-out);
}

.expand-btn svg.rotated {
  transform: rotate(90deg);
}

.route-count {
  font-size: 10px;
  color: var(--color-text-muted);
  background: var(--color-bg-tertiary);
  padding: 1px 6px;
  border-radius: var(--radius-full);
}

/* Nested routes */
.routes-list {
  margin-left: 36px;
  margin-top: var(--space-2);
  padding-left: var(--space-3);
  border-left: 2px solid var(--color-border-subtle);
}

.route-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-sm);
  transition: background var(--duration-fast) var(--ease-out);
}

.route-item:hover {
  background: var(--color-bg-tertiary);
}

.route-info {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  min-width: 0;
}

.route-name {
  font-size: var(--text-sm);
  font-weight: 500;
  color: var(--color-text-primary);
}

.route-path {
  font-size: var(--text-xs);
  font-family: var(--font-mono);
  color: var(--color-text-muted);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.route-domain {
  font-size: 10px;
  color: var(--color-accent);
  background: var(--color-accent-subtle);
  padding: 1px 6px;
  border-radius: var(--radius-full);
}

/* Small toggle for routes */
.route-toggle {
  display: flex;
  align-items: center;
  padding: 2px;
  border-radius: var(--radius-full);
  transition: all var(--duration-fast) var(--ease-out);
}

.toggle-track-sm {
  position: relative;
  width: 28px;
  height: 16px;
  background: var(--color-bg-tertiary);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-full);
  transition: all var(--duration-fast) var(--ease-out);
}

.route-toggle.active .toggle-track-sm {
  background: var(--color-accent);
  border-color: var(--color-accent);
}

.toggle-thumb-sm {
  position: absolute;
  top: 1px;
  left: 1px;
  width: 12px;
  height: 12px;
  background: white;
  border-radius: var(--radius-full);
  transition: transform var(--duration-fast) var(--ease-out);
}

.route-toggle.active .toggle-thumb-sm {
  transform: translateX(12px);
}

/* Expand transition */
.expand-enter-active,
.expand-leave-active {
  transition: all var(--duration-fast) var(--ease-out);
  overflow: hidden;
}

.expand-enter-from,
.expand-leave-to {
  opacity: 0;
  max-height: 0;
  margin-top: 0;
}

.expand-enter-to,
.expand-leave-from {
  opacity: 1;
  max-height: 500px;
}

/* API Keys */
.keys-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.key-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-3) var(--space-4);
  background: var(--color-bg-tertiary);
  border-radius: var(--radius-md);
}

.key-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.key-name {
  font-family: var(--font-mono);
  font-size: var(--text-sm);
  font-weight: 600;
  color: var(--color-text-primary);
}

.key-value {
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  color: var(--color-text-muted);
}

.key-status {
  font-size: var(--text-xs);
  font-weight: 500;
  color: var(--color-text-muted);
}

.key-status.configured {
  color: var(--color-success);
}

/* Digests List */
.digests-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.digest-item {
  display: flex;
  align-items: center;
  gap: var(--space-4);
  padding: var(--space-3) var(--space-4);
  text-decoration: none;
  color: var(--color-text-primary);
  border-radius: var(--radius-md);
  transition: background var(--duration-fast) var(--ease-out);
}

.digest-item:hover {
  background: var(--color-bg-tertiary);
}

.digest-date {
  font-family: var(--font-mono);
  font-size: var(--text-sm);
  font-weight: 500;
}

.digest-count {
  font-size: var(--text-sm);
  color: var(--color-text-secondary);
}

.digest-arrow {
  margin-left: auto;
  color: var(--color-text-muted);
  transition: transform var(--duration-fast) var(--ease-out);
}

.digest-item:hover .digest-arrow {
  transform: translateX(2px);
  color: var(--color-accent);
}

.empty-text {
  font-size: var(--text-sm);
  color: var(--color-text-muted);
  text-align: center;
  padding: var(--space-8) 0;
}
</style>
