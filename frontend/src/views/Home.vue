<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { usePreferredDark, useLocalStorage } from '@vueuse/core'
import DomainFilter from '../components/DomainFilter.vue'
import DigestCard from '../components/DigestCard.vue'
import { getLatestDigest, getDigests } from '../api/client.js'

const router = useRouter()

// State
const digest = ref(null)
const digests = ref([])
const selectedDomain = ref(null)
const loading = ref(true)
const error = ref(null)
const selectedDate = ref('')
const showDatePicker = ref(false)

// Available domains
const availableDomains = ['ai', 'finance', 'academic', 'tech', 'general', 'social']

// Grouped items by domain
const groupedItems = computed(() => {
  if (!digest.value?.items) return {}

  const filtered = selectedDomain.value
    ? digest.value.items.filter(item => item.domain === selectedDomain.value)
    : digest.value.items

  const groups = {}
  const domainOrder = ['ai', 'finance', 'academic', 'tech', 'general', 'social']

  for (const item of filtered) {
    const domain = item.domain || 'general'
    if (!groups[domain]) {
      groups[domain] = []
    }
    groups[domain].push(item)
  }

  // Sort groups by domain order
  const sorted = {}
  for (const d of domainOrder) {
    if (groups[d]) {
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

const domainMeta = {
  ai: { emoji: '\u{1F916}', label: 'AI' },
  finance: { emoji: '\u{1F4B0}', label: 'Finance' },
  academic: { emoji: '\u{1F4DA}', label: 'Academic' },
  tech: { emoji: '\u{1F4BB}', label: 'Tech' },
  general: { emoji: '\u{1F4F0}', label: 'General' },
  social: { emoji: '\u{1F310}', label: 'Social' }
}

function formatDate(dateStr) {
  if (!dateStr) return 'Today'
  const d = new Date(dateStr + 'T00:00:00')
  return d.toLocaleDateString('en-US', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' })
}

function getTodayStr() {
  return new Date().toISOString().split('T')[0]
}

function getYesterdayStr() {
  const d = new Date()
  d.setDate(d.getDate() - 1)
  return d.toISOString().split('T')[0]
}

async function loadDigest(date = null) {
  loading.value = true
  error.value = null

  try {
    let response
    if (date) {
      response = await getDigest(date)
    } else {
      response = await getLatestDigest()
    }
    digest.value = response.data
    if (date) {
      selectedDate.value = date
    } else if (response.data?.date) {
      selectedDate.value = response.data.date
    }
  } catch (err) {
    error.value = err.response?.data?.detail || err.message || 'Failed to load digest'
    // Use mock data for demo
    digest.value = createMockDigest()
    selectedDate.value = getTodayStr()
  } finally {
    loading.value = false
  }
}

async function loadDigestList() {
  try {
    const response = await getDigests()
    digests.value = response.data || []
  } catch {
    // Ignore - not critical
  }
}

function handleDateChange(event) {
  const date = event.target.value
  if (date) {
    loadDigest(date)
    showDatePicker.value = false
  }
}

function navigateToDate(date) {
  loadDigest(date)
}

function createMockDigest() {
  return {
    date: getTodayStr(),
    items: [
      { id: 1, title: 'OpenAI Announces GPT-5 with Enhanced Reasoning', url: 'https://example.com/1', source: 'TechCrunch', domain: 'ai', score: 95, summary: 'Major breakthrough in language model capabilities with significant improvements in mathematical reasoning and code generation.' },
      { id: 2, title: 'Federal Reserve Signals Rate Cut in September', url: 'https://example.com/2', source: 'Bloomberg', domain: 'finance', score: 88, summary: 'Fed chair indicates openness to rate reduction as inflation data shows continued cooling trend.' },
      { id: 3, title: 'New Transformer Architecture Achieves SOTA on Multiple Benchmarks', url: 'https://example.com/3', source: 'arXiv', domain: 'academic', score: 82, summary: 'Research paper introduces sparse attention mechanism that reduces compute by 40% while maintaining performance.' },
      { id: 4, title: 'Apple Vision Pro 2 Leaked Specs Reveal Major Upgrade', url: 'https://example.com/4', source: 'The Verge', domain: 'tech', score: 79, summary: 'Thinner design, wider field of view, and significantly improved battery life reported in supply chain leaks.' },
      { id: 5, title: 'Global Climate Summit Reaches Historic Agreement', url: 'https://example.com/5', source: 'Reuters', domain: 'general', score: 85, summary: '195 nations commit to accelerating carbon neutrality timeline with binding enforcement mechanisms.' },
      { id: 6, title: 'Twitter Introduces Creator Monetization 2.0', url: 'https://example.com', source: 'SocialMediaToday', domain: 'social', score: 72, summary: 'New revenue sharing model promises 70% ad revenue share for creators meeting engagement thresholds.' },
      { id: 7, title: 'Claude 4 Opus Sets New Performance Records', url: 'https://example.com/7', source: 'AI News', domain: 'ai', score: 91, summary: 'Anthropic releases latest model showing significant improvements in coding, analysis, and creative tasks.' },
      { id: 8, title: 'Bitcoin ETF Inflows Hit Record $2.4B in Single Day', url: 'https://example.com/8', source: 'CoinDesk', domain: 'finance', score: 87, summary: 'Institutional demand for crypto exposure continues to surge as major asset managers compete for market share.' },
    ]
  }
}

// Handle domain filter
function handleDomainSelect(domain) {
  selectedDomain.value = domain
}

onMounted(async () => {
  await Promise.all([loadDigest(), loadDigestList()])
})
</script>

<template>
  <div class="home-view">
    <!-- Hero Header -->
    <section class="hero-section">
      <div class="container">
        <div class="hero-content animate-slide-up">
          <h1 class="hero-title">
            <span class="hero-greeting">Today's</span>
            <span class="hero-highlight">Digest</span>
          </h1>
          <p class="hero-date" v-if="selectedDate">
            {{ formatDate(selectedDate) }}
          </p>
          <div class="hero-stats" v-if="!loading">
            <span class="stat">
              <span class="stat-number">{{ totalItems }}</span>
              <span class="stat-label">items</span>
            </span>
            <span class="stat-separator">&middot;</span>
            <span class="stat">
              <span class="stat-number">{{ Object.keys(groupedItems).length }}</span>
              <span class="stat-label">domains</span>
            </span>
          </div>
        </div>
      </div>
    </section>

    <!-- Controls -->
    <section class="controls-section container">
      <div class="controls-row">
        <!-- Domain Filter -->
        <DomainFilter
          :domains="availableDomains"
          :selected-domain="selectedDomain"
          @domain-select="handleDomainSelect"
        />

        <!-- Date Picker -->
        <div class="date-picker-wrapper">
          <button
            class="date-picker-toggle"
            @click="showDatePicker = !showDatePicker"
            :aria-expanded="showDatePicker"
          >
            <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
              <path d="M4.75 0a.75.75 0 01.75.75V2h5V.75a.75.75 0 011.5 0V2h1.25c.966 0 1.75.784 1.75 1.75v10.5A1.75 1.75 0 0113.25 16H2.75A1.75 1.75 0 011 14.25V3.75C1 2.784 1.784 2 2.75 2H4V.75A.75.75 0 014.75 0zM2.5 7.5v6.75c0 .138.112.25.25.25h10.5a.25.25 0 00.25-.25V7.5H14.5v3.25a.75.75 0 01-1.5 0V7.5H3v3.25a.75.75 0 01-1.5 0V7.5H2.5z"/>
            </svg>
            Browse
          </button>
          <transition name="dropdown">
            <div v-if="showDatePicker" class="date-dropdown">
              <input
                type="date"
                class="date-input"
                :value="selectedDate || getTodayStr()"
                :max="getTodayStr()"
                @change="handleDateChange"
              />
              <div class="recent-dates" v-if="digests.length > 0">
                <button
                  v-for="d in digests.slice(0, 5)"
                  :key="d.date"
                  class="recent-date-btn"
                  :class="{ active: selectedDate === d.date }"
                  @click="navigateToDate(d.date)"
                >
                  {{ d.date }}
                </button>
              </div>
            </div>
          </transition>
        </div>
      </div>

      <!-- Filter status -->
      <div class="filter-status" v-if="selectedDomain">
        <span class="filter-text">
          Showing {{ filteredCount }} of {{ totalItems }} items
        </span>
        <button class="clear-filter" @click="selectedDomain = null">
          Clear filter
        </button>
      </div>
    </section>

    <!-- Loading State -->
    <section v-if="loading" class="loading-section container">
      <div class="loading-grid">
        <div v-for="i in 4" :key="i" class="loading-card">
          <div class="loading-shimmer loading-score"></div>
          <div class="loading-body">
            <div class="loading-shimmer loading-title"></div>
            <div class="loading-shimmer loading-meta"></div>
            <div class="loading-shimmer loading-text"></div>
            <div class="loading-shimmer loading-text short"></div>
          </div>
        </div>
      </div>
    </section>

    <!-- Error State -->
    <section v-else-if="error" class="error-section container">
      <div class="error-card">
        <div class="error-icon">!</div>
        <h3>Unable to load digest</h3>
        <p>{{ error }}</p>
        <button class="retry-btn" @click="loadDigest()">Try again</button>
      </div>
    </section>

    <!-- Content -->
    <section v-else class="content-section container">
      <!-- Domain Groups -->
      <div v-for="(items, domain) in groupedItems" :key="domain" class="domain-group">
        <div class="domain-header">
          <span class="domain-emoji">{{ domainMeta[domain]?.emoji }}</span>
          <h2 class="domain-title">{{ domainMeta[domain]?.label || domain }}</h2>
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

      <!-- Empty State -->
      <div v-if="Object.keys(groupedItems).length === 0 && !loading" class="empty-state">
        <div class="empty-icon">
          <svg width="48" height="48" viewBox="0 0 16 16" fill="currentColor">
            <path d="M8 0a8 8 0 110 16A8 8 0 018 0zM1.5 8a6.5 6.5 0 1013 0 6.5 6.5 0 00-13 0zm7.25-3.25v2.992l2.028.812a.75.75 0 01-.557 1.392l-2.5-1A.75.75 0 017.25 8.25v-3.5a.75.75 0 011.5 0z"/>
          </svg>
        </div>
        <h3>No items found</h3>
        <p v-if="selectedDomain">No items match the selected domain filter.</p>
        <p v-else>No digest available for this date.</p>
      </div>
    </section>
  </div>
</template>

<style scoped>
/* Hero */
.hero-section {
  padding: var(--space-12) 0 var(--space-8);
  border-bottom: 1px solid var(--color-border-subtle);
}

.hero-content {
  text-align: center;
}

.hero-title {
  font-size: var(--text-4xl);
  font-weight: 800;
  letter-spacing: var(--tracking-tight);
  line-height: var(--leading-tight);
  margin-bottom: var(--space-3);
}

.hero-greeting {
  display: block;
  font-size: var(--text-lg);
  font-weight: 500;
  color: var(--color-text-secondary);
  letter-spacing: var(--tracking-wide);
  text-transform: uppercase;
  margin-bottom: var(--space-1);
}

.hero-highlight {
  background: linear-gradient(135deg, var(--color-accent), #a371f7);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.hero-date {
  font-size: var(--text-base);
  color: var(--color-text-muted);
  margin-bottom: var(--space-4);
}

.hero-stats {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-3);
}

.stat {
  display: flex;
  align-items: baseline;
  gap: var(--space-1);
}

.stat-number {
  font-family: var(--font-mono);
  font-size: var(--text-xl);
  font-weight: 700;
  color: var(--color-accent);
}

.stat-label {
  font-size: var(--text-sm);
  color: var(--color-text-muted);
}

.stat-separator {
  color: var(--color-text-muted);
  opacity: 0.4;
}

/* Controls */
.controls-section {
  padding-top: var(--space-6);
  padding-bottom: var(--space-4);
}

.controls-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4);
  flex-wrap: wrap;
}

.date-picker-wrapper {
  position: relative;
}

.date-picker-toggle {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3);
  font-size: var(--text-sm);
  font-weight: 500;
  color: var(--color-text-secondary);
  background: var(--color-bg-tertiary);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  transition: all var(--duration-fast) var(--ease-out);
}

.date-picker-toggle:hover {
  color: var(--color-text-primary);
  border-color: var(--color-text-muted);
}

.date-dropdown {
  position: absolute;
  top: calc(100% + var(--space-2));
  right: 0;
  background: var(--color-bg-elevated);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  padding: var(--space-3);
  box-shadow: var(--shadow-lg);
  min-width: 240px;
  z-index: 50;
}

.date-input {
  width: 100%;
  padding: var(--space-2) var(--space-3);
  background: var(--color-bg-input);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  color: var(--color-text-primary);
  font-size: var(--text-sm);
  margin-bottom: var(--space-3);
}

.date-input:focus {
  outline: none;
  border-color: var(--color-accent);
}

.recent-dates {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.recent-date-btn {
  display: block;
  width: 100%;
  padding: var(--space-2) var(--space-3);
  font-size: var(--text-sm);
  font-family: var(--font-mono);
  color: var(--color-text-secondary);
  text-align: left;
  border-radius: var(--radius-md);
  transition: all var(--duration-fast) var(--ease-out);
}

.recent-date-btn:hover {
  color: var(--color-text-primary);
  background: var(--color-bg-tertiary);
}

.recent-date-btn.active {
  color: var(--color-accent);
  background: var(--color-accent-subtle);
}

/* Dropdown transition */
.dropdown-enter-active,
.dropdown-leave-active {
  transition: opacity var(--duration-fast) var(--ease-out),
              transform var(--duration-fast) var(--ease-out);
}

.dropdown-enter-from,
.dropdown-leave-to {
  opacity: 0;
  transform: translateY(-4px) scale(0.98);
}

/* Filter Status */
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
  background: linear-gradient(
    90deg,
    var(--color-bg-tertiary) 25%,
    var(--color-bg-secondary) 50%,
    var(--color-bg-tertiary) 75%
  );
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite;
  border-radius: var(--radius-sm);
}

@keyframes shimmer {
  0% { background-position: -200% 0; }
  100% { background-position: 200% 0; }
}

.loading-score {
  width: 44px;
  height: 28px;
  flex-shrink: 0;
}

.loading-body {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.loading-title {
  width: 70%;
  height: 20px;
}

.loading-meta {
  width: 40%;
  height: 16px;
}

.loading-text {
  width: 100%;
  height: 14px;
}

.loading-text.short {
  width: 60%;
}

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
  box-shadow: var(--shadow-glow);
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

/* Empty State */
.empty-state {
  text-align: center;
  padding: var(--space-16) var(--space-4);
}

.empty-icon {
  color: var(--color-text-muted);
  margin-bottom: var(--space-4);
  opacity: 0.5;
}

.empty-state h3 {
  font-size: var(--text-lg);
  font-weight: 600;
  margin-bottom: var(--space-2);
}

.empty-state p {
  font-size: var(--text-sm);
  color: var(--color-text-secondary);
}

/* Responsive */
@media (max-width: 640px) {
  .hero-section {
    padding: var(--space-8) 0 var(--space-6);
  }

  .hero-title {
    font-size: var(--text-3xl);
  }

  .controls-row {
    flex-direction: column;
    align-items: stretch;
  }

  .date-picker-wrapper {
    align-self: flex-end;
  }

  .date-dropdown {
    right: 0;
    left: auto;
  }
}
</style>
