<script setup>
import { useI18n } from '../composables/useI18n.js'
import { DOMAIN_META } from '../constants/domains.js'

const { t } = useI18n()

const props = defineProps({
  domains: {
    type: Array,
    default: () => []
  },
  selectedDomain: {
    type: String,
    default: null
  }
})

const emit = defineEmits(['domain-select'])

function getDomainMeta(domain) {
  return DOMAIN_META[domain] || { emoji: '\u{1F4CC}', color: 'var(--color-text-muted)' }
}

function select(domain) {
  emit('domain-select', domain === props.selectedDomain ? null : domain)
}
</script>

<template>
  <div class="domain-filter">
    <button
      class="filter-chip"
      :class="{ active: !selectedDomain }"
      @click="emit('domain-select', null)"
    >
      <span class="chip-emoji">{{ t('filter.all') }}</span>
    </button>
    <button
      v-for="domain in domains"
      :key="domain"
      class="filter-chip"
      :class="{ active: selectedDomain === domain }"
      :style="{ '--chip-color': getDomainMeta(domain).color }"
      @click="select(domain)"
    >
      <span class="chip-emoji">{{ getDomainMeta(domain).emoji }}</span>
      <span class="chip-label">{{ t('domain.' + domain) }}</span>
    </button>
  </div>
</template>

<style scoped>
.domain-filter {
  display: flex;
  gap: var(--space-2);
  overflow-x: auto;
  padding: var(--space-1) 0;
  scrollbar-width: none;
  -ms-overflow-style: none;
}

.domain-filter::-webkit-scrollbar {
  display: none;
}

.filter-chip {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  padding: var(--space-2) var(--space-3);
  font-size: var(--text-sm);
  font-weight: 500;
  color: var(--color-text-secondary);
  background: var(--color-bg-tertiary);
  border: 1px solid transparent;
  border-radius: var(--radius-full);
  white-space: nowrap;
  transition: all var(--duration-fast) var(--ease-out);
  flex-shrink: 0;
}

.filter-chip:hover {
  color: var(--color-text-primary);
  border-color: var(--color-border);
}

.filter-chip.active {
  color: var(--chip-color, var(--color-accent));
  background: color-mix(in srgb, var(--chip-color, var(--color-accent)) 15%, transparent);
  border-color: color-mix(in srgb, var(--chip-color, var(--color-accent)) 40%, transparent);
}

.chip-emoji {
  font-size: var(--text-base);
  line-height: 1;
}

.chip-label {
  line-height: 1;
}
</style>
