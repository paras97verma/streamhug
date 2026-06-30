<template>
  <div class="home-view">
    <div v-if="libraryStore.isLoading" class="loading-state">
      <HeroBanner :media="null" />
      <div style="margin-top: 40px; padding: 0 4%;">
        <LoadingSkeleton height="30px" width="200px" style="margin-bottom: 20px" />
        <div style="display: flex; gap: 10px;">
          <LoadingSkeleton v-for="i in 5" :key="i" height="250px" style="flex: 1" />
        </div>
      </div>
    </div>
    
    <ErrorMessage 
      v-else-if="libraryStore.error" 
      title="Failed to Load Library" 
      :message="libraryStore.error" 
      :retry="fetchData"
    />
    
    <div v-else-if="libraryStore.library">
      <!-- Search Results taking precedence if active -->
      <div v-if="searchStore.query" class="search-results-view">
        <h2 class="search-title">Search Results for "{{ searchStore.query }}"</h2>
        
        <div v-if="searchStore.isLoading" class="search-grid">
           <LoadingSkeleton v-for="i in 10" :key="i" height="300px" />
        </div>
        
        <div v-else-if="searchStore.results.length === 0" class="no-results">
          No results found.
        </div>
        
        <div v-else class="search-grid">
          <div v-for="media in searchStore.results" :key="media.id" class="grid-item">
            <MovieCard :media="media" />
          </div>
        </div>
      </div>
      
      <!-- Normal Dashboard -->
      <div v-else>
        <!-- Hero Banner uses the first movie, or first tv show -->
        <HeroBanner :media="heroMedia" />
        
        <div class="rows-container">
          <MovieRow id="movies" title="Movies" :mediaList="libraryStore.library.movies" />
          <MovieRow id="tvshows" title="TV Shows" :mediaList="libraryStore.library.tv_shows" />
          <MovieRow id="anime" title="Anime" :mediaList="libraryStore.library.anime" />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, computed } from 'vue';
import { useLibraryStore } from '@/stores/libraryStore';
import { useSearchStore } from '@/stores/searchStore';
import HeroBanner from '@/components/library/HeroBanner.vue';
import MovieRow from '@/components/library/MovieRow.vue';
import MovieCard from '@/components/library/MovieCard.vue';
import LoadingSkeleton from '@/components/ui/LoadingSkeleton.vue';
import ErrorMessage from '@/components/ui/ErrorMessage.vue';

const libraryStore = useLibraryStore();
const searchStore = useSearchStore();

const heroMedia = computed(() => {
  if (!libraryStore.library) return null;
  const { movies, tv_shows, anime } = libraryStore.library;
  if (movies.length > 0) return movies[0];
  if (tv_shows.length > 0) return tv_shows[0];
  if (anime.length > 0) return anime[0];
  return null;
});

const fetchData = () => {
  libraryStore.fetchLibrary();
};

onMounted(() => {
  fetchData();
});
</script>

<style scoped>
.home-view {
  min-height: 100vh;
  padding-bottom: 50px;
}

.rows-container {
  margin-top: -100px;
  position: relative;
  z-index: 20;
}

.search-results-view {
  padding: 100px 4% 50px;
  min-height: 100vh;
}

.search-title {
  font-size: 1.5rem;
  margin-bottom: 30px;
  color: #e5e5e5;
}

.search-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 20px;
}

.no-results {
  font-size: 1.2rem;
  color: #a3a3a3;
  text-align: center;
  margin-top: 50px;
}
</style>
