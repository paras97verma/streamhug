<template>
  <div class="hero-banner" v-if="media">
    <div class="image-layer">
      <img
        :src="bannerUrl"
        :alt="media.title"
        @error="onImageError"
        class="banner-img"
      />
      <div class="vignette-layer"></div>
    </div>
    
    <div class="content-layer">
      <h1 class="title">{{ media.title }}</h1>
      <p class="description">
        {{ media.category || 'A ' + userStore.appName + ' Original' }} &bull; {{ media.year || 'Unknown Year' }}
      </p>
      
      <div class="buttons">
        <button class="btn btn-play" @click="play">
          <Play class="icon" fill="currentColor" /> Play
        </button>
        <button class="btn btn-info" @click="goToDetails">
          <Info class="icon" /> More Info
        </button>
      </div>
    </div>
  </div>
  <div v-else class="hero-banner-skeleton">
    <LoadingSkeleton />
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue';
import { useRouter } from 'vue-router';
import { Play, Info } from '@lucide/vue';
import type { Media } from '@/types/media';
import { api } from '@/api/endpoints';
import LoadingSkeleton from '../ui/LoadingSkeleton.vue';
import { useUserStore } from '@/stores/userStore';

const props = defineProps<{
  media: Media | null;
}>();

const router = useRouter();
const userStore = useUserStore();
const imageError = ref(false);

const bannerUrl = computed(() => {
  if (!props.media) return '';
  // Try banner, fallback to poster if banner fails (handled by backend or @error event)
  return api.getBannerUrl(props.media.id);
});

const onImageError = (e: Event) => {
  if (!imageError.value && props.media) {
    imageError.value = true;
    (e.target as HTMLImageElement).src = api.getPosterUrl(props.media.id);
  }
};

const play = () => {
  if (props.media) {
    router.push({ name: 'player', params: { id: props.media.id } });
  }
};

const goToDetails = () => {
  if (props.media) {
    router.push({ name: 'media-detail', params: { id: props.media.id } });
  }
};
</script>

<style scoped>
.hero-banner {
  position: relative;
  width: 100vw;
  height: 80vh;
  min-height: 500px;
  background-color: #000;
  overflow: hidden;
}

.hero-banner-skeleton {
  width: 100vw;
  height: 80vh;
  min-height: 500px;
}

.image-layer {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
}

.banner-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  object-position: center 20%;
}

.vignette-layer {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: 
    linear-gradient(to right, rgba(20,20,20,0.8) 0%, rgba(20,20,20,0) 50%),
    linear-gradient(to top, var(--bg-color) 0%, rgba(20,20,20,0) 30%);
}

.content-layer {
  position: absolute;
  bottom: 30%;
  left: 4%;
  width: 40%;
  min-width: 300px;
  z-index: 10;
}

@media (max-width: 768px) {
  .content-layer {
    width: 80%;
    bottom: 20%;
  }
}

.title {
  font-size: clamp(2rem, 4vw, 4rem);
  font-weight: 800;
  line-height: 1.1;
  text-shadow: 2px 2px 4px rgba(0,0,0,0.45);
  margin-bottom: 1rem;
}

.description {
  font-size: clamp(1rem, 1.2vw, 1.5rem);
  font-weight: 500;
  text-shadow: 2px 2px 4px rgba(0,0,0,0.45);
  margin-bottom: 1.5rem;
  color: #e5e5e5;
}

.buttons {
  display: flex;
  gap: 1rem;
}

.btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 0.8rem 1.8rem;
  border-radius: 4px;
  font-size: 1.1rem;
  font-weight: 600;
  transition: all 0.2s;
}

.btn-play {
  background-color: white;
  color: black;
}

.btn-play:hover {
  background-color: rgba(255, 255, 255, 0.75);
}

.btn-info {
  background-color: rgba(109, 109, 110, 0.7);
  color: white;
}

.btn-info:hover {
  background-color: rgba(109, 109, 110, 0.4);
}

.icon {
  width: 24px;
  height: 24px;
}
</style>
