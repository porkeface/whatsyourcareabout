<script setup>
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

const domainMeta = {
  ai: { emoji: '\u{1F916}', label: 'AI', color: 'var(--color-domain-ai)' },
  finance: { emoji: '\u{1F4B0}', label: 'Finance', color: 'var(--color-domain-finance)' },
  academic: { emoji: '\u{1F4DA}', label: 'Academic', color: 'var(--color-domain-academic)' },
  tech: { emoji: '\u{1F4BB}', label: 'Tech', color: 'var(--color-domain-tech)' },
  general: { emoji: '\u{1F4F0}', label: 'General', color: 'var(--color-domain-general)' },
  social: { emoji: '\u{1F310}', label: 'Social', color: 'var(--color-domain-social)' }
}

function getDomainMeta(domain) {
  return domainMeta[domain] || { emoji: '\u{1F4CC}', label: domain, color: 'var(--color-text-muted)' }
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
      <span class="chip-emoji">All</span>
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
      <span class="chip-label">{{ getDomainMeta(domain).label }}</span>
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
