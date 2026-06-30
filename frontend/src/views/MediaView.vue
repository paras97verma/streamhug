<template>
  <div class="media-view">
    <div v-if="isLoading" class="loading-state">
       <LoadingSkeleton height="60vh" />
    </div>
    
    <ErrorMessage 
      v-else-if="error" 
      title="Failed to load details" 
      :message="error" 
      :retry="fetchMedia"
    />
    
    <div v-else-if="media" class="details-container">
      <div class="backdrop">
        <img :src="bannerUrl" :alt="media.title" @error="onImageError" />
        <div class="gradient-overlay"></div>
      </div>
      
      <div class="content">
        <button class="back-btn" @click="router.back()">
          <ArrowLeft class="icon" /> Back
        </button>
        
        <div class="info-layout">
          <div class="poster-col">
            <img :src="posterUrl" :alt="media.title" class="poster-img" />
          </div>
          
          <div class="details-col">
            <h1 class="title">{{ media.title }}</h1>
            
            <div class="meta-tags">
              <span class="tag year">{{ media.year || 'N/A' }}</span>
              <span class="tag type">{{ media.type.toUpperCase() }}</span>
              <span v-if="media.technical_info?.resolution" class="tag res">
                {{ media.technical_info.resolution }}
              </span>
              <span v-if="media.technical_info?.duration_seconds" class="tag duration">
                {{ formatTime(media.technical_info.duration_seconds) }}
              </span>
            </div>
            
            <p class="filename-info">
              <FileVideo class="icon-small" /> {{ media.filename }}
            </p>
            
            <button class="play-btn" @click="play">
              <Play class="icon" fill="currentColor" /> Play
            </button>
            
            <!-- Seasons and Episodes -->
            <div v-if="media.seasons && media.seasons.length > 0" class="seasons-section">
              <h2>Episodes</h2>
              
              <div v-for="season in media.seasons" :key="season.season_number" class="season">
                <h3>Season {{ season.season_number }}</h3>
                <div class="episodes-list">
                  <div 
                    v-for="ep in season.episodes" 
                    :key="ep.id" 
                    class="episode-card"
                    @click="playEpisode(ep.id)"
                  >
                    <div class="ep-number">{{ ep.episode_number }}</div>
                    <div class="ep-details">
                      <h4>{{ ep.title }}</h4>
                      <span class="ep-duration" v-if="ep.technical_info?.duration_seconds">
                        {{ formatTime(ep.technical_info.duration_seconds) }}
                      </span>
                    </div>
                    <Play class="ep-play-icon" />
                  </div>
                </div>
              </div>
            </div>
            
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { ArrowLeft, Play, FileVideo } from '@lucide/vue';
import { api } from '@/api/endpoints';
import type { Media } from '@/types/media';
import { formatTime } from '@/utils/formatters';
import LoadingSkeleton from '@/components/ui/LoadingSkeleton.vue';
import ErrorMessage from '@/components/ui/ErrorMessage.vue';

const route = useRoute();
const router = useRouter();

const media = ref<Media | null>(null);
const isLoading = ref(true);
const error = ref<string | null>(null);
const bannerError = ref(false);

const posterUrl = computed(() => media.value ? api.getPosterUrl(media.value.id) : '');
const bannerUrl = computed(() => {
  if (!media.value) return '';
  return bannerError.value ? api.getPosterUrl(media.value.id) : api.getBannerUrl(media.value.id);
});

const onImageError = () => {
  bannerError.value = true;
};

const fetchMedia = async () => {
  const id = route.params.id as string;
  if (!id) return;
  
  isLoading.value = true;
  error.value = null;
  try {
    const data = await api.getMediaDetail(id);
    media.value = data.media;
  } catch (err: any) {
    error.value = err?.response?.data?.detail || 'Failed to load details';
  } finally {
    isLoading.value = false;
  }
};

const play = () => {
  if (media.value) {
    // If it has episodes, play the first one by default, else play the media itself
    let targetId = media.value.id;
    if (media.value.seasons && media.value.seasons.length > 0) {
      const firstSeason = media.value.seasons[0];
      if (firstSeason.episodes.length > 0) {
        targetId = firstSeason.episodes[0].id;
      }
    }
    router.push({ name: 'player', params: { id: targetId } });
  }
};

const playEpisode = (episodeId: string) => {
  router.push({ name: 'player', params: { id: episodeId } });
};

onMounted(() => {
  fetchMedia();
});
</script>

<style scoped>
.media-view {
  min-height: 100vh;
  position: relative;
  background-color: var(--neu-base);
  padding-bottom: 60px;
}

.backdrop {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 60vh;
  z-index: 0;
}

.backdrop img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  opacity: 0.22;
}

.gradient-overlay {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: linear-gradient(to top, var(--neu-base) 0%, rgba(18, 21, 31, 0.4) 60%, var(--neu-base) 100%);
}

.content {
  position: relative;
  z-index: 10;
  padding: 100px 5% 50px;
}

.back-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--text-secondary);
  font-size: 0.9rem;
  margin-bottom: 40px;
  padding: 10px 20px;
  border-radius: var(--radius-pill);
  background: var(--neu-base);
  box-shadow: var(--shadow-btn);
  border: 1px solid var(--neu-border);
  transition: all var(--transition-fast);
}

.back-btn:hover {
  color: var(--accent-light);
  box-shadow: var(--shadow-outset);
}

.back-btn:active {
  box-shadow: var(--shadow-btn-press);
}

.info-layout {
  display: flex;
  gap: 60px;
}

.poster-col {
  flex: 0 0 320px;
}

.poster-img {
  width: 100%;
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-card);
  border: 1px solid var(--neu-border);
  transition: box-shadow var(--transition-normal);
}

.poster-img:hover {
  box-shadow: var(--shadow-card-hover);
}

.details-col {
  flex: 1;
}

.title {
  font-size: clamp(2rem, 3.5vw, 3.2rem);
  font-weight: 800;
  margin-bottom: 20px;
  background: linear-gradient(135deg, var(--text-primary), var(--text-secondary));
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.meta-tags {
  display: flex;
  gap: 12px;
  margin-bottom: 28px;
  flex-wrap: wrap;
}

.tag {
  padding: 5px 12px;
  border-radius: var(--radius-pill);
  font-size: 0.8rem;
  font-weight: 600;
  color: var(--text-secondary);
  background: var(--neu-mid);
  box-shadow: var(--shadow-btn-press);
  border: 1px solid rgba(255, 255, 255, 0.02);
}

.tag.res {
  color: var(--accent-light);
  border: 1px solid rgba(167, 139, 250, 0.2);
}

.filename-info {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--text-muted);
  margin-bottom: 40px;
  font-family: 'Courier New', Courier, monospace;
  font-size: 0.85rem;
}

.icon-small {
  width: 15px;
  height: 15px;
}

.play-btn {
  display: flex;
  align-items: center;
  gap: 10px;
  background: linear-gradient(135deg, var(--accent) 0%, #5b21b6 100%);
  color: white;
  padding: 14px 44px;
  border-radius: var(--radius-pill);
  font-size: 1.15rem;
  font-weight: 700;
  box-shadow: var(--shadow-btn), 0 4px 20px var(--accent-glow);
  transition: all var(--transition-fast);
  margin-bottom: 50px;
}

.play-btn:hover {
  box-shadow: var(--shadow-outset), 0 6px 28px var(--accent-glow);
  transform: translateY(-2px);
}

.play-btn:active {
  box-shadow: var(--shadow-btn-press);
  transform: translateY(0);
}

.seasons-section h2 {
  font-size: 1.6rem;
  margin-bottom: 24px;
  padding-bottom: 12px;
  color: var(--text-primary);
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
}

.season {
  margin-bottom: 40px;
}

.season h3 {
  font-size: 1.15rem;
  color: var(--text-secondary);
  margin-bottom: 18px;
}

.episodes-list {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.episode-card {
  display: flex;
  align-items: center;
  background-color: var(--neu-base);
  box-shadow: var(--shadow-card);
  padding: 18px 24px;
  border-radius: var(--radius-md);
  border: 1px solid var(--neu-border);
  cursor: pointer;
  transition: all var(--transition-normal);
}

.episode-card:hover {
  box-shadow: var(--shadow-card-hover), 0 0 0 1px rgba(124, 58, 237, 0.2);
  transform: translateY(-2px);
}

.episode-card:active {
  box-shadow: var(--shadow-btn-press);
  transform: translateY(0);
}

.episode-card:hover .ep-play-icon {
  opacity: 1;
  color: var(--accent-light);
  transform: scale(1.1);
}

.ep-number {
  font-size: 1.4rem;
  font-weight: 700;
  color: var(--text-muted);
  width: 50px;
}

.ep-details {
  flex: 1;
}

.ep-details h4 {
  font-size: 1.05rem;
  font-weight: 600;
  margin-bottom: 4px;
  color: var(--text-primary);
}

.ep-duration {
  font-size: 0.8rem;
  color: var(--text-secondary);
}

.ep-play-icon {
  opacity: 0.3;
  width: 22px;
  height: 22px;
  transition: all var(--transition-fast);
}

@media (max-width: 768px) {
  .info-layout {
    flex-direction: column;
    gap: 30px;
  }
  .poster-col {
    flex: 0 0 220px;
    margin: 0 auto;
  }
  .title {
    font-size: 2.2rem;
    text-align: center;
  }
  .meta-tags {
    justify-content: center;
  }
  .play-btn {
    width: 100%;
    justify-content: center;
  }
}
</style>
