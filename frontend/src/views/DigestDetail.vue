<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import DomainFilter from '../components/DomainFilter.vue'
import DigestCard from '../components/DigestCard.vue'
import { getDigest } from '../api/client.js'
import { useI18n } from '../composables/useI18n.js'
import { DOMAIN_META, DOMAIN_ORDER } from '../constants/domains.js'

const route = useRoute()
const router = useRouter()
const { locale, t } = useI18n()

const props = defineProps({
  date: String
})

// State
const digest = ref(null)
const selectedDomain = ref(null)
const loading = ref(true)
const error = ref(null)

const availableDomains = DOMAIN_ORDER

const groupedItems = computed(() => {
  if (!digest.value?.items) return {}

  const filtered = selectedDomain.value
    ? digest.value.items.filter(item => item.domain === selectedDomain.value)
    : digest.value.items

  const groups = {}

  for (const item of filtered) {
    const domain = item.domain || 'general'
    if (!groups[domain]) {
      groups[domain] = []
    }
    groups[domain].push(item)
  }

  const sorted = {}
  for (const d of DOMAIN_ORDER) {
    if (groups[d]) {
      sorted[d] = groups[d]
    }
  }
  for (const d of Object.keys(groups)) {
    if (!sorted[d]) {
      sorted[d] = groups[d]
    }
  }
  return sorted
})

const totalItems = computed(() => digest.value?.items?.length || 0)
const filteredCount = computed(() => {
  if (!selectedDomain.value) return totalItems.value
  return digest.value?.items?.filter(i => i.domain === selectedDomain.value).length || 0
})

function formatDate(dateStr) {
  if (!dateStr) return ''
  const d = new Date(dateStr + 'T00:00:00')
  return d.toLocaleDateString(locale.value === 'zh' ? 'zh-CN' : 'en-US', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' })
}

async function loadDigest(date) {
  loading.value = true
  error.value = null
  selectedDomain.value = null

  try {
    const response = await getDigest(date)
    digest.value = response.data
  } catch (err) {
    error.value = err.response?.data?.detail || err.message || 'Failed to load digest'
  } finally {
    loading.value = false
  }
}

function handleDomainSelect(domain) {
  selectedDomain.value = domain
}

function goBack() {
  router.push('/')
}

watch(() => route.params.date, (newDate) => {
  if (newDate) {
    loadDigest(newDate)
  }
}, { immediate: true })
</script>

<template>
  <div class="digest-detail-view">
    <!-- Header -->
    <section class="detail-header">
      <div class="container">
        <button class="back-btn" @click="goBack">
          <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
            <path d="M7.78 12.53a.75.75 0 01-1.06 0L2.47 8.28a.75.75 0 010-1.06l4.25-4.25a.75.75 0 011.06 1.06L4.81 7h7.44a.75.75 0 010 1.5H4.81l2.97 2.97a.75.75 0 010 1.06z"/>
          </svg>
          {{ t('detail.backToToday') }}
        </button>

        <div class="detail-content animate-slide-up">
          <h1 class="detail-title">
            <span class="title-date" v-if="date">{{ formatDate(date) }}</span>
            <span class="title-fallback" v-else>{{ t('detail.digestDetail') }}</span>
          </h1>
          <p class="detail-subtitle" v-if="!loading && digest">
            {{ t('detail.itemsAcrossDomains', { count: totalItems, domains: Object.keys(groupedItems).length }) }}
          </p>
        </div>
      </div>
    </section>

    <!-- Controls -->
    <section class="controls-section container" v-if="!loading && !error">
      <DomainFilter
        :domains="availableDomains"
        :selected-domain="selectedDomain"
        @domain-select="handleDomainSelect"
      />
      <div class="filter-status" v-if="selectedDomain">
        <span class="filter-text">
          {{ t('detail.showing', { count: filteredCount, total: totalItems }) }}
        </span>
        <button class="clear-filter" @click="selectedDomain = null">
          {{ t('detail.clearFilter') }}
        </button>
      </div>
    </section>

    <!-- Loading -->
    <section v-if="loading" class="loading-section container">
      <div class="loading-grid">
        <div v-for="i in 3" :key="i" class="loading-card">
          <div class="loading-shimmer loading-score"></div>
          <div class="loading-body">
            <div class="loading-shimmer loading-title"></div>
            <div class="loading-shimmer loading-meta"></div>
            <div class="loading-shimmer loading-text"></div>
          </div>
        </div>
      </div>
    </section>

    <!-- Error -->
    <section v-else-if="error" class="error-section container">
      <div class="error-card">
        <div class="error-icon">!</div>
        <h3>{{ t('detail.unableToLoad') }}</h3>
        <p>{{ error }}</p>
        <div class="error-actions">
          <button class="retry-btn" @click="loadDigest(date)">{{ t('detail.tryAgain') }}</button>
          <button class="back-btn-secondary" @click="goBack">{{ t('detail.goBack') }}</button>
        </div>
      </div>
    </section>

    <!-- Content -->
    <section v-else class="content-section container">
      <div v-for="(items, domain) in groupedItems" :key="domain" class="domain-group">
        <div class="domain-header">
          <span class="domain-emoji">{{ DOMAIN_META[domain]?.emoji }}</span>
          <h2 class="domain-title">{{ t('domain.' + domain) }}</h2>
          <span class="domain-count">{{ items.length }}</span>
        </div>
        <div class="items-list">
          <DigestCard
            v-for="(item, idx) in items"
            :key="item.id || idx"
            :item="item"
            :index="idx"
          />
        </div>
      </div>

      <div v-if="Object.keys(groupedItems).length === 0 && !loading" class="empty-state">
        <p>{{ t('detail.noItemsFound') }}{{ selectedDomain ? t('detail.noItemsForDomain') : '' }}</p>
      </div>
    </section>
  </div>
</template>

<style scoped>
.detail-header {
  padding: var(--space-8) 0 var(--space-6);
  border-bottom: 1px solid var(--color-border-subtle);
}

.back-btn {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--text-sm);
  font-weight: 500;
  color: var(--color-text-secondary);
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-md);
  transition: all var(--duration-fast) var(--ease-out);
  margin-bottom: var(--space-4);
}

.back-btn:hover {
  color: var(--color-text-primary);
  background: var(--color-bg-tertiary);
}

.detail-title {
  font-size: var(--text-3xl);
  font-weight: 800;
  letter-spacing: var(--tracking-tight);
  line-height: var(--leading-tight);
}

.title-date {
  background: linear-gradient(135deg, var(--color-accent), #a371f7);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.detail-subtitle {
  font-size: var(--text-base);
  color: var(--color-text-muted);
  margin-top: var(--space-2);
}

/* Controls */
.controls-section {
  padding: var(--space-6) 0 var(--space-4);
}

.filter-status {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  margin-top: var(--space-3);
  padding: var(--space-2) var(--space-3);
  background: var(--color-accent-subtle);
  border-radius: var(--radius-md);
}

.filter-text {
  font-size: var(--text-sm);
  color: var(--color-accent);
}

.clear-filter {
  font-size: var(--text-sm);
  font-weight: 500;
  color: var(--color-text-secondary);
  padding: var(--space-1) var(--space-2);
  border-radius: var(--radius-sm);
  transition: all var(--duration-fast) var(--ease-out);
}

.clear-filter:hover {
  color: var(--color-text-primary);
  background: var(--color-bg-tertiary);
}

/* Loading */
.loading-section {
  padding: var(--space-8) 0;
}

.loading-grid {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.loading-card {
  display: flex;
  gap: var(--space-4);
  padding: var(--space-5);
  background: var(--color-bg-card);
  border: 1px solid var(--color-border-subtle);
  border-radius: var(--radius-lg);
}

.loading-shimmer {
  background: linear-gradient(90deg, var(--color-bg-tertiary) 25%, var(--color-bg-secondary) 50%, var(--color-bg-tertiary) 75%);
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite;
  border-radius: var(--radius-sm);
}

@keyframes shimmer {
  0% { background-position: -200% 0; }
  100% { background-position: 200% 0; }
}

.loading-score { width: 44px; height: 28px; flex-shrink: 0; }
.loading-body { flex: 1; display: flex; flex-direction: column; gap: var(--space-2); }
.loading-title { width: 70%; height: 20px; }
.loading-meta { width: 40%; height: 16px; }
.loading-text { width: 100%; height: 14px; }

/* Error */
.error-section {
  padding: var(--space-12) 0;
  display: flex;
  justify-content: center;
}

.error-card {
  text-align: center;
  padding: var(--space-8);
  background: var(--color-bg-card);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-xl);
  max-width: 400px;
}

.error-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 48px;
  height: 48px;
  background: rgba(248, 81, 73, 0.15);
  color: var(--color-error);
  font-size: var(--text-2xl);
  font-weight: 700;
  border-radius: var(--radius-full);
  margin-bottom: var(--space-4);
}

.error-card h3 {
  font-size: var(--text-lg);
  font-weight: 600;
  margin-bottom: var(--space-2);
}

.error-card p {
  font-size: var(--text-sm);
  color: var(--color-text-secondary);
  margin-bottom: var(--space-4);
}

.error-actions {
  display: flex;
  gap: var(--space-3);
  justify-content: center;
}

.retry-btn {
  padding: var(--space-2) var(--space-4);
  font-size: var(--text-sm);
  font-weight: 600;
  color: #ffffff;
  background: var(--color-accent);
  border-radius: var(--radius-md);
  transition: all var(--duration-fast) var(--ease-out);
}

.retry-btn:hover {
  background: var(--color-accent-hover);
}

.back-btn-secondary {
  padding: var(--space-2) var(--space-4);
  font-size: var(--text-sm);
  font-weight: 500;
  color: var(--color-text-secondary);
  background: var(--color-bg-tertiary);
  border-radius: var(--radius-md);
  transition: all var(--duration-fast) var(--ease-out);
}

.back-btn-secondary:hover {
  color: var(--color-text-primary);
}

/* Content */
.content-section {
  padding: var(--space-4) 0 var(--space-12);
}

.domain-group {
  margin-bottom: var(--space-10);
}

.domain-header {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  margin-bottom: var(--space-4);
  padding-bottom: var(--space-3);
  border-bottom: 1px solid var(--color-border-subtle);
}

.domain-emoji {
  font-size: var(--text-2xl);
  line-height: 1;
}

.domain-title {
  font-size: var(--text-xl);
  font-weight: 700;
  letter-spacing: var(--tracking-tight);
}

.domain-count {
  font-family: var(--font-mono);
  font-size: var(--text-sm);
  font-weight: 600;
  color: var(--color-text-muted);
  background: var(--color-bg-tertiary);
  padding: var(--space-1) var(--space-2);
  border-radius: var(--radius-full);
}

.items-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.empty-state {
  text-align: center;
  padding: var(--space-16) var(--space-4);
  color: var(--color-text-muted);
}
</style>
