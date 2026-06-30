<template>
  <div class="search-container" :class="{ 'is-active': isActive }">
    <button class="search-btn" @click="toggleSearch" aria-label="Search">
      <Search class="icon" />
    </button>
    <input
      ref="searchInput"
      v-model="searchQuery"
      type="text"
      placeholder="Titles, people, genres"
      class="search-input"
      @blur="handleBlur"
      @keydown.esc="closeSearch"
    />
    <button
      v-if="searchQuery"
      class="clear-btn"
      @click="clearSearch"
      aria-label="Clear search"
    >
      <X class="icon-small" />
    </button>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, nextTick } from 'vue';
import { useRouter } from 'vue-router';
import { Search, X } from '@lucide/vue';
import { useSearchStore } from '@/stores/searchStore';
import { debounce } from '@/utils/debounce';

const router = useRouter();
const searchStore = useSearchStore();

const isActive = ref(false);
const searchQuery = ref('');
const searchInput = ref<HTMLInputElement | null>(null);

const toggleSearch = async () => {
  if (!isActive.value) {
    isActive.value = true;
    await nextTick();
    searchInput.value?.focus();
  } else if (!searchQuery.value) {
    isActive.value = false;
  } else {
    // Perform search
    executeSearch(searchQuery.value);
  }
};

const closeSearch = () => {
  if (!searchQuery.value) {
    isActive.value = false;
  }
};

const handleBlur = () => {
  if (!searchQuery.value) {
    isActive.value = false;
  }
};

const clearSearch = () => {
  searchQuery.value = '';
  searchStore.clearSearch();
  searchInput.value?.focus();
  router.push('/');
};

const executeSearch = debounce((query: string) => {
  if (query.trim()) {
    searchStore.search(query);
    if (router.currentRoute.value.name !== 'search') {
      router.push({ name: 'search', query: { q: query } });
    } else {
      router.replace({ name: 'search', query: { q: query } });
    }
  } else {
    searchStore.clearSearch();
    router.push('/');
  }
}, 500);

watch(searchQuery, (newVal) => {
  executeSearch(newVal);
});
</script>

<style scoped>
.search-container {
  display: flex;
  align-items: center;
  background-color: transparent;
  border: 1px solid transparent;
  transition: var(--transition-normal);
  padding: 4px;
  position: relative;
}

.search-container.is-active {
  background-color: rgba(0, 0, 0, 0.75);
  border: 1px solid rgba(255, 255, 255, 0.85);
}

.search-btn {
  color: var(--text-color);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 4px;
}

.icon {
  width: 24px;
  height: 24px;
}

.icon-small {
  width: 16px;
  height: 16px;
}

.search-input {
  width: 0;
  opacity: 0;
  background: transparent;
  border: none;
  color: var(--text-color);
  font-size: 14px;
  outline: none;
  transition: width 0.3s ease, opacity 0.3s ease;
  padding: 0;
}

.search-container.is-active .search-input {
  width: 200px;
  opacity: 1;
  padding: 0 10px;
}

.clear-btn {
  color: var(--text-color);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 4px;
  opacity: 0;
  transition: opacity 0.2s;
}

.search-container.is-active .clear-btn {
  opacity: 1;
}

@media (max-width: 768px) {
  .search-container.is-active .search-input {
    width: 140px;
  }
}
</style>
