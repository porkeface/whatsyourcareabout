<script setup>
import { computed } from 'vue'
import { useI18n } from '../composables/useI18n.js'
import { DOMAIN_META } from '../constants/domains.js'

const { locale, t } = useI18n()

const props = defineProps({
  item: {
    type: Object,
    required: true
  },
  index: {
    type: Number,
    default: 0
  }
})

function getDomainInfo(domain) {
  const meta = DOMAIN_META[domain]
  return meta
    ? { emoji: meta.emoji, color: meta.color }
    : { emoji: '\u{1F4CC}', color: 'var(--color-text-muted)' }
}

function getScoreColor(score) {
  if (score >= 80) return 'var(--color-score-high)'
  if (score >= 50) return 'var(--color-score-medium)'
  return 'var(--color-score-low)'
}

function formatDate(dateStr) {
  if (!dateStr) return ''
  const d = new Date(dateStr)
  return d.toLocaleDateString(locale.value === 'zh' ? 'zh-CN' : 'en-US', { month: 'short', day: 'numeric' })
}

const domain = getDomainInfo(props.item.domain)

const domainLabel = computed(() => t('domain.' + props.item.domain))

function truncateText(text, maxLen) {
  if (!text || text.length <= maxLen) return text
  const truncated = text.substring(0, maxLen)

  // Try sentence boundary
  const lastPeriod = Math.max(truncated.lastIndexOf('. '), truncated.lastIndexOf('。'), truncated.lastIndexOf('！'), truncated.lastIndexOf('？'))
  if (lastPeriod > maxLen * 0.5) {
    return truncated.substring(0, lastPeriod + 1).trim() + '...'
  }

  // Word boundary
  const lastSpace = truncated.lastIndexOf(' ')
  if (lastSpace > maxLen * 0.5) {
    return truncated.substring(0, lastSpace).trim() + '...'
  }

  return truncated.trim() + '...'
}

const displayText = computed(() => {
  const text = props.item.summary || props.item.raw_text || ''
  if (!text) return t('card.noPreview')
  return truncateText(text, 200)
})
</script>

<template>
  <article
    class="digest-card"
    :style="{ '--delay': `${index * 50}ms` }"
  >
    <!-- Score indicator -->
    <div class="card-score" :style="{ color: getScoreColor(item.score) }">
      <span class="score-value">{{ item.score }}</span>
    </div>

    <div class="card-body">
      <!-- Title -->
      <h3 class="card-title">
        <a
          :href="item.url"
          target="_blank"
          rel="noopener noreferrer"
          class="title-link"
        >
          {{ item.title }}
          <svg class="external-icon" width="12" height="12" viewBox="0 0 16 16" fill="currentColor">
            <path d="M3.75 2h3.5a.75.75 0 010 1.5H4.5v8h8V8.75a.75.75 0 011.5 0v3.5A1.75 1.75 0 0112.25 14h-8.5A1.75 1.75 0 012 12.25v-8.5C2 2.784 2.784 2 3.75 2zm6.72.72l3 3a.75.75 0 010 1.06l-3 3a.75.75 0 11-1.06-1.06l1.72-1.72H7a.75.75 0 010-1.5h4.13L9.41 3.78a.75.75 0 011.06-1.06z"/>
          </svg>
        </a>
      </h3>

      <!-- Meta row -->
      <div class="card-meta">
        <!-- Source badge -->
        <span class="badge badge-source" v-if="item.source">
          {{ item.source }}
        </span>

        <!-- Domain badge -->
        <span
          class="badge badge-domain"
          :style="{ '--domain-color': domain.color }"
        >
          <span class="badge-emoji">{{ domain.emoji }}</span>
          {{ domainLabel }}
        </span>

        <!-- Date -->
        <span class="meta-date" v-if="item.published_at || item.created_at">
          {{ formatDate(item.published_at || item.created_at) }}
        </span>
      </div>

      <!-- Summary -->
      <p class="card-summary" :class="{ 'no-preview': !item.summary && !item.raw_text }">
        {{ displayText }}
      </p>

      <!-- Tags -->
      <div class="card-tags" v-if="item.tags && item.tags.length">
        <span
          v-for="tag in item.tags"
          :key="tag"
          class="tag"
        >
          {{ tag }}
        </span>
      </div>
    </div>
  </article>
</template>

<style scoped>
.digest-card {
  display: flex;
  gap: var(--space-4);
  padding: var(--space-5);
  background: var(--color-bg-card);
  border: 1px solid var(--color-border-subtle);
  border-radius: var(--radius-lg);
  transition: all var(--duration-fast) var(--ease-out);
  animation: slideUp var(--duration-slow) var(--ease-out) var(--delay, 0ms) both;
}

.digest-card:hover {
  background: var(--color-bg-card-hover);
  border-color: var(--color-border);
  box-shadow: var(--shadow-md);
  transform: translateY(-1px);
}

/* Score */
.card-score {
  display: flex;
  align-items: flex-start;
  justify-content: center;
  flex-shrink: 0;
  min-width: 44px;
  padding-top: var(--space-1);
}

.score-value {
  font-family: var(--font-mono);
  font-size: var(--text-xl);
  font-weight: 700;
  line-height: 1;
  letter-spacing: -0.02em;
}

/* Body */
.card-body {
  flex: 1;
  min-width: 0;
}

/* Title */
.card-title {
  font-size: var(--text-base);
  font-weight: 600;
  line-height: var(--leading-tight);
  margin-bottom: var(--space-2);
}

.title-link {
  color: var(--color-text-primary);
  text-decoration: none;
  display: inline-flex;
  align-items: flex-start;
  gap: var(--space-2);
  transition: color var(--duration-fast) var(--ease-out);
}

.title-link:hover {
  color: var(--color-accent);
}

.external-icon {
  flex-shrink: 0;
  margin-top: 3px;
  opacity: 0.4;
  transition: opacity var(--duration-fast);
}

.title-link:hover .external-icon {
  opacity: 0.8;
}

/* Meta */
.card-meta {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--space-2);
  margin-bottom: var(--space-3);
}

.badge {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  padding: 2px var(--space-2);
  font-size: var(--text-xs);
  font-weight: 500;
  border-radius: var(--radius-full);
  line-height: 1.5;
}

.badge-source {
  background: var(--color-accent-subtle);
  color: var(--color-accent);
}

.badge-domain {
  background: color-mix(in srgb, var(--domain-color, var(--color-text-muted)) 15%, transparent);
  color: var(--domain-color, var(--color-text-muted));
}

.badge-emoji {
  font-size: 10px;
  line-height: 1;
}

.meta-date {
  font-size: var(--text-xs);
  color: var(--color-text-muted);
}

/* Summary */
.card-summary {
  font-size: var(--text-sm);
  color: var(--color-text-secondary);
  line-height: var(--leading-relaxed);
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.card-summary.no-preview {
  color: var(--color-text-muted);
  font-style: italic;
  opacity: 0.6;
}

/* Tags */
.card-tags {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-1);
  margin-top: var(--space-3);
}

.tag {
  display: inline-block;
  padding: 1px var(--space-2);
  font-size: 11px;
  font-weight: 500;
  color: var(--color-text-muted);
  background: var(--color-bg-tertiary);
  border-radius: var(--radius-sm);
}

/* Responsive */
@media (max-width: 640px) {
  .digest-card {
    padding: var(--space-4);
    gap: var(--space-3);
  }

  .card-score {
    min-width: 36px;
  }

  .score-value {
    font-size: var(--text-lg);
  }
}
</style>
