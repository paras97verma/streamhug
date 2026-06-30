<template>
  <div class="player-view">
    <VideoPlayer 
      v-if="mediaId" 
      :mediaId="mediaId" 
      title="Playing" 
      :src="streamUrl"
      :initialAudioTracks="audioTracks"
      :initialSubtitleTracks="subtitleTracks"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, ref, onMounted } from 'vue';
import { useRoute } from 'vue-router';
import { api } from '@/api/endpoints';
import VideoPlayer from '@/components/player/VideoPlayer.vue';
import type { AudioTrack, SubtitleTrack } from '@/types/media';

const route = useRoute();
const mediaId = computed(() => route.params.id as string);
const streamUrl = computed(() => api.getStreamUrl(mediaId.value));

const audioTracks = ref<AudioTrack[]>([]);
const subtitleTracks = ref<SubtitleTrack[]>([]);

// Fetch track metadata from the media detail API on mount
onMounted(async () => {
  try {
    const res = await fetch(api.getMediaUrl(mediaId.value));
    if (res.ok) {
      const data = await res.json();
      const techInfo = data?.media?.technical_info ?? data?.technical_info ?? null;
      if (techInfo) {
        audioTracks.value = techInfo.audio_tracks ?? [];
        subtitleTracks.value = techInfo.subtitle_tracks ?? [];
      }
    }
  } catch (err) {
    console.warn('Failed to fetch track metadata:', err);
  }
});
</script>

<style scoped>
.player-view {
  width: 100vw;
  height: 100vh;
  background: #000;
}
</style>
