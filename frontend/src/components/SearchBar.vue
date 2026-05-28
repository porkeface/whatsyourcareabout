<script setup>
import { ref, watch, onUnmounted } from 'vue'
import { useI18n } from '../composables/useI18n.js'

const { t } = useI18n()

const props = defineProps({
  modelValue: { type: String, default: '' }
})

const emit = defineEmits(['update:modelValue'])

const localValue = ref(props.modelValue)
let debounceTimer = null

watch(() => props.modelValue, (val) => {
  localValue.value = val
})

function onInput(event) {
  localValue.value = event.target.value
  clearTimeout(debounceTimer)
  debounceTimer = setTimeout(() => {
    emit('update:modelValue', localValue.value)
  }, 300)
}

function clear() {
  localValue.value = ''
  clearTimeout(debounceTimer)
  emit('update:modelValue', '')
}

onUnmounted(() => {
  clearTimeout(debounceTimer)
})
</script>

<template>
  <div class="search-bar" :class="{ 'has-value': localValue }">
    <svg class="search-icon" width="16" height="16" viewBox="0 0 16 16" fill="currentColor" aria-hidden="true">
      <path d="M10.68 11.74a6 6 0 01-7.922-8.982 6 6 0 018.982 7.922l3.04 3.04a.749.749 0 01-.326 1.275.749.749 0 01-.734-.215zM11.5 7a4.499 4.499 0 10-8.997 0A4.499 4.499 0 0011.5 7z"/>
    </svg>
    <input
      type="text"
      class="search-input"
      :value="localValue"
      :placeholder="t('search.placeholder')"
      :aria-label="t('search.placeholder')"
      @input="onInput"
    />
    <button
      v-if="localValue"
      class="clear-btn"
      type="button"
      aria-label="Clear search"
      @click="clear"
    >
      <svg width="14" height="14" viewBox="0 0 16 16" fill="currentColor">
        <path d="M3.72 3.72a.75.75 0 011.06 0L8 6.94l3.22-3.22a.749.749 0 011.275.326.749.749 0 01-.215.734L9.06 8l3.22 3.22a.749.749 0 01-.326 1.275.749.749 0 01-.734-.215L8 9.06l-3.22 3.22a.751.751 0 01-1.042-.018.751.751 0 01-.018-1.042L6.94 8 3.72 4.78a.75.75 0 010-1.06z"/>
      </svg>
    </button>
  </div>
</template>

<style scoped>
.search-bar {
  position: relative;
  display: flex;
  align-items: center;
  width: 100%;
  background: var(--color-bg-input);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  transition: border-color var(--duration-fast) var(--ease-out),
              box-shadow var(--duration-fast) var(--ease-out);
}

.search-bar:focus-within {
  border-color: var(--color-accent);
  box-shadow: 0 0 0 3px var(--color-accent-subtle);
}

.search-bar.has-value {
  border-color: var(--color-border);
}

.search-bar.has-value:focus-within {
  border-color: var(--color-accent);
}

.search-icon {
  position: absolute;
  left: var(--space-3);
  color: var(--color-text-muted);
  pointer-events: none;
  flex-shrink: 0;
  transition: color var(--duration-fast) var(--ease-out);
}

.search-bar:focus-within .search-icon {
  color: var(--color-accent);
}

.search-input {
  width: 100%;
  padding: var(--space-2) var(--space-3) var(--space-2) calc(var(--space-3) + 16px + var(--space-2));
  background: transparent;
  border: none;
  outline: none;
  color: var(--color-text-primary);
  font-size: var(--text-sm);
  line-height: var(--leading-normal);
}

.search-input::placeholder {
  color: var(--color-text-muted);
}

.clear-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  width: 24px;
  height: 24px;
  margin-right: var(--space-2);
  color: var(--color-text-muted);
  border-radius: var(--radius-sm);
  transition: color var(--duration-fast) var(--ease-out),
              background var(--duration-fast) var(--ease-out);
}

.clear-btn:hover {
  color: var(--color-text-primary);
  background: var(--color-bg-tertiary);
}
</style>
