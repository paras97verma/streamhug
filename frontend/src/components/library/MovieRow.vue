<template>
  <div class="movie-row" v-if="mediaList.length > 0">
    <h2 class="row-title">{{ title }}</h2>
    
    <div class="slider-container" @mouseenter="showControls = true" @mouseleave="showControls = false">
      <button 
        class="slider-control prev" 
        @click="scroll('left')" 
        v-show="showControls && canScrollLeft"
        aria-label="Previous"
      >
        <ChevronLeft class="icon" />
      </button>
      
      <div class="slider" ref="sliderRef" @scroll="handleScroll">
        <div class="slider-inner">
          <div v-for="media in mediaList" :key="media.id" class="card-wrapper">
            <MovieCard :media="media" />
          </div>
        </div>
      </div>
      
      <button 
        class="slider-control next" 
        @click="scroll('right')" 
        v-show="showControls && canScrollRight"
        aria-label="Next"
      >
        <ChevronRight class="icon" />
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, nextTick } from 'vue';
import { ChevronLeft, ChevronRight } from '@lucide/vue';
import type { Media } from '@/types/media';
import MovieCard from './MovieCard.vue';

const props = defineProps<{
  title: string;
  mediaList: Media[];
}>();

const sliderRef = ref<HTMLElement | null>(null);
const showControls = ref(false);
const canScrollLeft = ref(false);
const canScrollRight = ref(true); // Assume true initially if there's items

const handleScroll = () => {
  if (!sliderRef.value) return;
  const { scrollLeft, scrollWidth, clientWidth } = sliderRef.value;
  canScrollLeft.value = scrollLeft > 0;
  // Use a small threshold (2px) to account for rounding errors
  canScrollRight.value = scrollLeft + clientWidth < scrollWidth - 2;
};

const scroll = (direction: 'left' | 'right') => {
  if (!sliderRef.value) return;
  const clientWidth = sliderRef.value.clientWidth;
  const scrollAmount = direction === 'left' ? -clientWidth * 0.8 : clientWidth * 0.8;
  
  sliderRef.value.scrollBy({
    left: scrollAmount,
    behavior: 'smooth'
  });
};

onMounted(() => {
  nextTick(() => {
    handleScroll();
  });
});
</script>

<style scoped>
.movie-row {
  margin: 3vw 0;
  position: relative;
}

.row-title {
  font-size: clamp(1rem, 1.4vw, 1.4rem);
  font-weight: 700;
  color: var(--text-primary);
  margin: 0 4% 0.8em 4%;
  letter-spacing: 0.2px;
  display: flex;
  align-items: center;
  gap: 10px;
}

.row-title::before {
  content: '';
  display: inline-block;
  width: 4px;
  height: 1.1em;
  background: linear-gradient(to bottom, #a78bfa, #7c3aed);
  border-radius: 2px;
  box-shadow: 0 0 8px rgba(124, 58, 237, 0.5);
}

.slider-container {
  position: relative;
}

.slider {
  overflow-x: auto;
  overflow-y: hidden;
  scrollbar-width: none; /* Firefox */
  padding: 0 4%;
  scroll-behavior: smooth;
}

.slider::-webkit-scrollbar {
  display: none; /* Safari and Chrome */
}

.slider-inner {
  display: flex;
  gap: 8px;
  padding: 10px 0;
}

.card-wrapper {
  flex: 0 0 calc(20% - 6.4px); /* 5 items per row */
  min-width: calc(20% - 6.4px);
}

@media (max-width: 1200px) {
  .card-wrapper {
    flex: 0 0 calc(25% - 6px); /* 4 items */
    min-width: calc(25% - 6px);
  }
}

@media (max-width: 800px) {
  .card-wrapper {
    flex: 0 0 calc(33.333% - 5.33px); /* 3 items */
    min-width: calc(33.333% - 5.33px);
  }
}

@media (max-width: 500px) {
  .card-wrapper {
    flex: 0 0 calc(50% - 4px); /* 2 items */
    min-width: calc(50% - 4px);
  }
}

.slider-control {
  position: absolute;
  top: 50%;
  transform: translateY(-50%);
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: rgba(12, 15, 23, 0.85);
  backdrop-filter: blur(12px);
  border: 1px solid rgba(124, 58, 237, 0.3);
  box-shadow: 4px 4px 12px var(--neu-dark), -2px -2px 8px var(--neu-light);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--accent-light);
  z-index: 20;
  transition: all var(--transition-fast);
}

.slider-control:hover {
  background: rgba(124, 58, 237, 0.2);
  border-color: var(--accent-light);
  box-shadow: 0 0 16px var(--accent-glow);
  transform: translateY(-50%) scale(1.1);
}

.slider-control .icon { width: 18px; height: 18px; }

.slider-control.prev { left: 1%; }
.slider-control.next { right: 1%; }
</style>
