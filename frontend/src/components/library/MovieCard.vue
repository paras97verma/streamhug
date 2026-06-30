<template>
  <div class="movie-card neu-card" @click="goToDetails" @mouseenter="isHovered = true" @mouseleave="isHovered = false">
    <div class="image-wrapper">
      <img
        :src="posterUrl"
        :alt="media.title"
        loading="lazy"
        @error="onImageError"
        class="poster"
        :class="{ 'opacity-0': imageError }"
      />
      <div v-if="imageError" class="fallback-poster">
        <span class="fallback-initial">{{ media.title.charAt(0).toUpperCase() }}</span>
        <span class="fallback-title">{{ media.title }}</span>
      </div>
      
      <!-- Progress Bar -->
      <div v-if="progress > 0 && technicalInfo" class="progress-bar-container">
        <div class="progress-bar" :style="{ width: progressPercentage + '%' }"></div>
      </div>

      <!-- Overlay on hover -->
      <div class="card-overlay" :class="{ visible: isHovered }">
        <div class="play-btn">
          <span class="play-icon">▶</span>
        </div>
      </div>
    </div>
    
    <div class="card-info">
      <h3 class="title">{{ media.title }}</h3>
      <div class="meta">
        <span v-if="media.year" class="year">{{ media.year }}</span>
        <span class="type-badge">{{ media.type }}</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue';
import { useRouter } from 'vue-router';
import type { Media } from '@/types/media';
import { api } from '@/api/endpoints';
import { useContinueWatchingStore } from '@/stores/continueWatchingStore';

const props = defineProps<{ media: Media; }>();

const router = useRouter();
const continueWatchingStore = useContinueWatchingStore();

const isHovered = ref(false);
const imageError = ref(false);

const posterUrl = computed(() => api.getPosterUrl(props.media.id));
const technicalInfo = computed(() => props.media.technical_info);
const progress = computed(() => continueWatchingStore.getProgress(props.media.id));

const progressPercentage = computed(() => {
  if (!technicalInfo.value?.duration_seconds) return 0;
  return Math.min((progress.value / technicalInfo.value.duration_seconds) * 100, 100);
});

const onImageError = () => { imageError.value = true; };
const goToDetails = () => { router.push({ name: 'media-detail', params: { id: props.media.id } }); };
</script>

<style scoped>
.movie-card {
  position: relative;
  width: 100%;
  aspect-ratio: 2 / 3;
  cursor: pointer;
  border-radius: var(--radius-lg) !important;
  overflow: hidden;
  background: var(--neu-mid);
  box-shadow: var(--shadow-card) !important;
  border: 1px solid var(--neu-border) !important;
  transition: box-shadow var(--transition-normal), transform var(--transition-normal) !important;
}

.movie-card:hover {
  box-shadow: var(--shadow-card-hover), 0 0 0 1px rgba(124,58,237,0.25) !important;
  transform: translateY(-6px) scale(1.02) !important;
}

.image-wrapper {
  position: absolute;
  inset: 0;
}

.poster {
  width: 100%;
  height: 100%;
  object-fit: cover;
  transition: transform var(--transition-normal), opacity 0.3s;
}

.movie-card:hover .poster {
  transform: scale(1.04);
}

.opacity-0 { opacity: 0; }

.fallback-poster {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #1a1d2e 0%, #12151f 100%);
  padding: 16px;
  gap: 12px;
}

.fallback-initial {
  font-size: 3.5rem;
  font-weight: 900;
  background: linear-gradient(135deg, #a78bfa, #7c3aed);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  line-height: 1;
}

.fallback-title {
  font-size: 0.78rem;
  font-weight: 600;
  color: var(--text-secondary);
  text-align: center;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

/* Progress bar */
.progress-bar-container {
  position: absolute;
  bottom: 0;
  left: 0;
  width: 100%;
  height: 3px;
  background: rgba(255, 255, 255, 0.12);
  z-index: 5;
}

.progress-bar {
  height: 100%;
  background: linear-gradient(to right, #7c3aed, #a78bfa);
  box-shadow: 0 0 6px rgba(124, 58, 237, 0.5);
}

/* Hover overlay */
.card-overlay {
  position: absolute;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  backdrop-filter: blur(2px);
  display: flex;
  align-items: center;
  justify-content: center;
  opacity: 0;
  transition: opacity var(--transition-normal);
  z-index: 3;
}

.card-overlay.visible { opacity: 1; }

.play-btn {
  width: 56px;
  height: 56px;
  border-radius: 50%;
  background: rgba(124, 58, 237, 0.9);
  border: 2px solid rgba(167, 139, 250, 0.7);
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 0 24px rgba(124, 58, 237, 0.6);
  transform: scale(0.8);
  transition: transform var(--transition-normal);
}

.card-overlay.visible .play-btn { transform: scale(1); }

.play-icon {
  font-size: 20px;
  color: white;
  margin-left: 4px;
}

/* Info strip at bottom */
.card-info {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  padding: 40px 12px 12px;
  background: linear-gradient(to top, rgba(0,0,0,0.9) 0%, rgba(0,0,0,0) 100%);
  z-index: 4;
}

.title {
  font-size: 0.88rem;
  font-weight: 600;
  margin-bottom: 5px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  color: var(--text-primary);
}

.meta {
  display: flex;
  gap: 6px;
  align-items: center;
  font-size: 0.72rem;
}

.year { color: var(--text-muted); }

.type-badge {
  background: rgba(124, 58, 237, 0.25);
  color: var(--accent-light);
  padding: 1px 7px;
  border-radius: var(--radius-pill);
  font-weight: 600;
  font-size: 0.65rem;
  text-transform: uppercase;
  letter-spacing: 0.4px;
}
</style>
