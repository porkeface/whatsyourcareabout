<script setup>
import { ref, onMounted } from 'vue'
import { getHealth, triggerCollect, getDigests } from '../api/client.js'

// State
const healthStatus = ref(null)
const collecting = ref(false)
const collectMessage = ref('')
const collectMessageType = ref('info')
const recentDigests = ref([])
const loading = ref(true)

// Mock API key display
const apiKeys = ref([
  { name: 'NEWS_API_KEY', masked: 'news_****...****8f3a', configured: true },
  { name: 'OPENAI_API_KEY', masked: 'sk-****...****k7j2', configured: true },
  { name: 'REDDIT_CLIENT_ID', masked: 'rdt_****...****4x9q', configured: false },
])

// Mock sources
const sources = ref([
  { name: 'RSS Feeds', type: 'rss', status: 'active', items: 12, lastSync: '2 min ago' },
  { name: 'Hacker News', type: 'api', status: 'active', items: 24, lastSync: '5 min ago' },
  { name: 'ArXiv Papers', type: 'api', status: 'active', items: 8, lastSync: '10 min ago' },
  { name: 'Reddit', type: 'api', status: 'error', items: 0, lastSync: 'Failed', error: 'Invalid credentials' },
  { name: 'TechCrunch', type: 'rss', status: 'active', items: 6, lastSync: '15 min ago' },
  { name: 'Bloomberg', type: 'rss', status: 'inactive', items: 0, lastSync: 'Never' },
])

function getStatusColor(status) {
  switch (status) {
    case 'active': return 'var(--color-success)'
    case 'error': return 'var(--color-error)'
    case 'inactive': return 'var(--color-text-muted)'
    default: return 'var(--color-text-muted)'
  }
}

function getStatusLabel(status) {
  switch (status) {
    case 'active': return 'Active'
    case 'error': return 'Error'
    case 'inactive': return 'Inactive'
    default: return 'Unknown'
  }
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
    // Use mock data
    recentDigests.value = [
      { date: '2026-05-28', item_count: 18 },
      { date: '2026-05-27', item_count: 22 },
      { date: '2026-05-26', item_count: 15 },
      { date: '2026-05-25', item_count: 20 },
      { date: '2026-05-24', item_count: 12 },
    ]
  }
}

async function handleCollect() {
  collecting.value = true
  collectMessage.value = ''
  collectMessageType.value = 'info'

  try {
    const response = await triggerCollect()
    collectMessage.value = response.data?.message || 'Collection triggered successfully'
    collectMessageType.value = 'success'
  } catch (err) {
    collectMessage.value = err.response?.data?.detail || 'Collection triggered (backend may not be running)'
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
  await Promise.all([loadHealth(), loadDigests()])
  loading.value = false
})
</script>

<template>
  <div class="settings-view">
    <section class="settings-header">
      <div class="container">
        <h1 class="page-title animate-slide-up">Settings</h1>
        <p class="page-subtitle">Configure your WYCA digest sources and preferences</p>
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
            API Status
          </h2>
          <span
            class="status-badge"
            :style="{ color: healthStatus?.status === 'ok' ? 'var(--color-success)' : 'var(--color-warning)' }"
          >
            <span class="status-dot" :style="{ background: healthStatus?.status === 'ok' ? 'var(--color-success)' : 'var(--color-warning)' }"></span>
            {{ healthStatus?.status === 'ok' ? 'Connected' : healthStatus?.status === 'disconnected' ? 'Disconnected' : 'Checking...' }}
          </span>
        </div>
        <div class="card-body" v-if="healthStatus">
          <div class="status-grid">
            <div class="status-item">
              <span class="status-label">Version</span>
              <span class="status-value">{{ healthStatus.version || '1.0.0' }}</span>
            </div>
            <div class="status-item">
              <span class="status-label">Last Run</span>
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
            Trigger Collection
          </h2>
        </div>
        <div class="card-body">
          <p class="card-description">
            Manually trigger a new collection run to fetch the latest items from all configured sources.
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
            {{ collecting ? 'Collecting...' : 'Start Collection' }}
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
            Sources
          </h2>
        </div>
        <div class="card-body">
          <div class="sources-list">
            <div
              v-for="source in sources"
              :key="source.name"
              class="source-item"
            >
              <div class="source-info">
                <span class="source-name">{{ source.name }}</span>
                <span class="source-type">{{ source.type }}</span>
              </div>
              <div class="source-meta">
                <span class="source-items" v-if="source.items > 0">
                  {{ source.items }} items
                </span>
                <span class="source-sync">{{ source.lastSync }}</span>
                <span
                  class="source-status"
                  :style="{ color: getStatusColor(source.status) }"
                >
                  <span class="status-dot-sm" :style="{ background: getStatusColor(source.status) }"></span>
                  {{ getStatusLabel(source.status) }}
                </span>
              </div>
              <p class="source-error" v-if="source.error">{{ source.error }}</p>
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
            API Keys
          </h2>
        </div>
        <div class="card-body">
          <p class="card-description muted">
            API keys are configured via environment variables. Contact your administrator to update keys.
          </p>
          <div class="keys-list">
            <div
              v-for="key in apiKeys"
              :key="key.name"
              class="key-item"
            >
              <div class="key-info">
                <span class="key-name">{{ key.name }}</span>
                <span class="key-value">{{ key.masked }}</span>
              </div>
              <span
                class="key-status"
                :class="{ configured: key.configured }"
              >
                {{ key.configured ? 'Configured' : 'Not set' }}
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
            Recent Digests
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
              <span class="digest-count">{{ d.item_count }} items</span>
              <svg width="14" height="14" viewBox="0 0 16 16" fill="currentColor" class="digest-arrow">
                <path d="M8.22 3.22a.75.75 0 011.06 0l4.25 4.25a.75.75 0 010 1.06l-4.25 4.25a.75.75 0 01-1.06-1.06L11.94 8 8.22 4.28a.75.75 0 010-1.06z"/>
              </svg>
            </a>
          </div>
          <p v-else class="empty-text">No digests available yet.</p>
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

.source-info {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  margin-bottom: var(--space-1);
}

.source-name {
  font-weight: 600;
  font-size: var(--text-sm);
  color: var(--color-text-primary);
}

.source-type {
  font-size: var(--text-xs);
  color: var(--color-text-muted);
  background: var(--color-bg-tertiary);
  padding: 1px var(--space-2);
  border-radius: var(--radius-sm);
  text-transform: uppercase;
  letter-spacing: var(--tracking-wide);
  font-weight: 500;
}

.source-meta {
  display: flex;
  align-items: center;
  gap: var(--space-4);
  font-size: var(--text-xs);
  color: var(--color-text-secondary);
}

.source-status {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  font-weight: 500;
}

.source-error {
  font-size: var(--text-xs);
  color: var(--color-error);
  margin-top: var(--space-1);
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
