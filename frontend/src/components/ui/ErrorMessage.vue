<template>
  <div class="error-container">
    <AlertTriangle class="icon" />
    <h2>{{ title }}</h2>
    <p>{{ message }}</p>
    <button v-if="retry" class="retry-btn" @click="retry">
      Try Again
    </button>
  </div>
</template>

<script setup lang="ts">
import { AlertTriangle } from '@lucide/vue';

defineProps<{
  title?: string;
  message: string;
  retry?: () => void;
}>();
</script>

<style scoped>
.error-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px 20px;
  text-align: center;
  background: var(--card-bg);
  border-radius: 8px;
  margin: 20px auto;
  max-width: 400px;
}

.icon {
  width: 48px;
  height: 48px;
  color: var(--brand-color);
  margin-bottom: 16px;
}

h2 {
  font-size: 1.25rem;
  margin-bottom: 8px;
}

p {
  color: var(--text-muted);
  margin-bottom: 24px;
}

.retry-btn {
  background-color: var(--text-color);
  color: var(--bg-color);
  padding: 8px 24px;
  border-radius: 4px;
  font-weight: 600;
  font-size: 1rem;
  transition: background-color 0.2s;
}

.retry-btn:hover {
  background-color: #e6e6e6;
}
</style>
