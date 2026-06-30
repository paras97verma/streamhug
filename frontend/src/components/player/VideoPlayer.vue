<template>
  <div 
    ref="containerRef" 
    class="player-container" 
    :class="{ 'hide-cursor': !showControls && !isPaused }"
    @mousemove="triggerShowControls"
    @click="triggerShowControls"
    @touchstart="triggerShowControls"
  >
    <!-- Video element -->
    <video
      ref="videoRef"
      class="player"
      autoplay
      crossorigin="anonymous"
      playsinline
      @canplay="onCanPlay"
      @timeupdate="onTimeUpdate"
      @waiting="onWaiting"
      @playing="onPlaying"
      @click.stop="togglePlay"
      @touchstart.stop="handleVideoTouch"
    ></video>

    <!-- Gradient overlays -->
    <div class="overlay-top" :class="{ 'visible': showControls || isPaused }"></div>
    <div class="overlay-bottom" :class="{ 'visible': showControls || isPaused }"></div>

    <!-- Back Button -->
    <button 
      class="back-btn" 
      :class="{ 'visible': showControls || isPaused }" 
      @click.stop="goBack" 
      aria-label="Go Back"
    >
      <ArrowLeft class="icon" />
    </button>

    <!-- Buffer / Loading Spinner -->
    <div class="loader-container" v-if="isLoading">
      <Loader2 class="spinner" />
    </div>

    <!-- Double-Tap / Double-Click Skip Animations -->
    <div class="skip-anim back" v-if="showSkipBackAnim">
      <div class="skip-content">
        <span class="skip-icon">◀◀</span>
        <span class="skip-text">-10s</span>
      </div>
    </div>
    <div class="skip-anim forward" v-if="showSkipForwardAnim">
      <div class="skip-content">
        <span class="skip-icon">▶▶</span>
        <span class="skip-text">+10s</span>
      </div>
    </div>

    <!-- Custom Controls Bar -->
    <div class="controls-overlay" :class="{ 'visible': showControls || isPaused }">
      <!-- Timeline Seek Bar -->
      <div class="timeline-container" @click.stop>
        <div class="timeline-track"></div>
        <div class="timeline-buffer" :style="{ width: bufferPercent + '%' }"></div>
        <div class="timeline-progress" :style="{ width: progressPercent + '%' }"></div>
        <input 
          type="range" 
          min="0" 
          :max="duration || 100" 
          step="any" 
          :value="currentTime" 
          @input="onSeekInput"
          @change="onSeekChange"
          class="timeline-slider"
        />
      </div>

      <!-- Button Controls -->
      <div class="controls-row" @click.stop>
        <div class="controls-left">
          <!-- Play / Pause -->
          <button class="control-btn" @click="togglePlay" :aria-label="isPaused ? 'Play' : 'Pause'">
            <Play v-if="isPaused" class="icon" />
            <Pause v-else class="icon" />
          </button>

          <!-- Skip buttons -->
          <button class="control-btn skip-btn" @click="skip(-10)" aria-label="Rewind 10 seconds">
            <span class="skip-btn-text">-10s</span>
          </button>
          <button class="control-btn skip-btn" @click="skip(10)" aria-label="Forward 10 seconds">
            <span class="skip-btn-text">+10s</span>
          </button>

          <!-- Volume & Boost Control -->
          <div class="volume-control-wrapper">
            <button class="control-btn" @click="toggleMute" aria-label="Mute">
              <VolumeX v-if="isMuted || volumeValue === 0" class="icon" />
              <Volume2 v-else class="icon" />
            </button>
            <div class="volume-slider-container">
              <input 
                type="range" 
                min="0" 
                max="1.0" 
                step="0.05" 
                :value="isMuted ? 0 : volumeValue" 
                @input="onVolumeSliderInput"
                class="volume-slider"
                :style="{ '--val': (isMuted ? 0 : volumeValue) * 100 + '%' }"
              />
              <span class="volume-text">
                {{ Math.round((isMuted ? 0 : volumeValue) * 100) }}%
              </span>
            </div>
          </div>

          <!-- Time Display -->
          <div class="time-display">
            {{ formatTime(currentTime) }} / {{ formatTime(duration) }}
          </div>
        </div>

        <div class="controls-right">
          <!-- Subtitles Trigger -->
          <div class="settings-wrapper" @click.stop>
            <button class="control-btn" @click="toggleSubtitlesMenu" aria-label="Subtitles">
              <Subtitles class="icon" :class="{ 'active-btn': currentSubtitleTrack !== -1 }" />
            </button>

            <!-- Subtitles Popover -->
            <div v-if="showSubtitlesMenu" class="settings-menu">
              <div class="menu-title">Subtitles</div>
              <button 
                class="menu-item"
                :class="{ active: currentSubtitleTrack === -1 }"
                @click="changeSubtitleTrack(-1, null)"
              >Off</button>
              <button 
                v-for="track in subtitleTracks" 
                :key="track.index"
                class="menu-item"
                :class="{ active: currentSubtitleTrack === track.index }"
                @click="changeSubtitleTrack(track.index, track)"
              >{{ formatTrackName(track, 'Sub') }}</button>
              <div v-if="subtitleTracks.length === 0" class="menu-no-tracks">
                No subtitles available
              </div>
            </div>
          </div>

          <!-- Audio Trigger -->
          <div class="settings-wrapper" @click.stop>
            <button class="control-btn" @click="toggleAudioMenu" aria-label="Audio Tracks">
              <Languages class="icon" :class="{ 'active-btn': audioTracks.length > 1 }" />
            </button>

            <!-- Audio Tracks Popover -->
            <div v-if="showAudioMenu" class="settings-menu">
              <div class="menu-title">Audio Tracks</div>
              <button 
                v-for="track in audioTracks" 
                :key="track.index"
                class="menu-item"
                :class="{ active: currentAudioTrack === track.index }"
                @click="changeAudioTrack(track)"
              >
                <span>{{ formatTrackName(track, 'Track') }}</span>
                <span class="track-badge" v-if="track.channels">{{ track.channels === 6 ? '5.1' : 'Stereo' }}</span>
              </button>
              <div v-if="audioTracks.length === 0" class="menu-no-tracks">
                Default Audio
              </div>
            </div>
          </div>

          <!-- Quality Trigger -->
          <div class="settings-wrapper" @click.stop>
            <button class="control-btn" @click="toggleQualityMenu" aria-label="Quality">
              <Settings class="icon" :class="{ 'rotate': showQualityMenu }" />
              <span class="quality-badge" v-if="currentQualityLabel">
                {{ currentQualityLabel }}
              </span>
            </button>

            <!-- Quality Popover -->
            <div v-if="showQualityMenu" class="settings-menu">
              <div class="menu-title">Quality</div>
              <button 
                class="menu-item"
                :class="{ active: currentQuality === (isHlsSupported ? -1 : 'auto') }"
                @click="changeQuality(isHlsSupported ? -1 : 'auto')"
              >Auto</button>
              <button 
                v-for="level in qualityLevels" 
                :key="level.index"
                class="menu-item"
                :class="{ active: isHlsSupported ? currentQuality === level.index : currentQuality === level.value }"
                @click="changeQuality(isHlsSupported ? level.index : level.value)"
              >{{ level.label }}</button>
            </div>
          </div>

          <!-- Fullscreen Toggle -->
          <button class="control-btn" @click="toggleFullscreen" :aria-label="isFullscreen ? 'Exit Fullscreen' : 'Enter Fullscreen'">
            <Minimize v-if="isFullscreen" class="icon" />
            <Maximize v-else class="icon" />
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed, watch } from 'vue';
import { useRouter } from 'vue-router';
import { 
  ArrowLeft, 
  Play, 
  Pause, 
  Volume2, 
  VolumeX, 
  Maximize, 
  Minimize, 
  Settings, 
  Loader2,
  Subtitles,
  Languages
} from '@lucide/vue';
import Hls from 'hls.js';
import { useContinueWatchingStore } from '@/stores/continueWatchingStore';

const props = defineProps<{
  mediaId: string;
  title: string;
  src: string;
  initialAudioTracks?: any[];
  initialSubtitleTracks?: any[];
}>();

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? '';

const router = useRouter();
const continueWatchingStore = useContinueWatchingStore();

const iso6392Map: Record<string, string> = {
  'eng': 'en', 'hin': 'hi', 'spa': 'es', 'fra': 'fr', 'deu': 'de', 'jpn': 'ja', 
  'kor': 'ko', 'chi': 'zh', 'zho': 'zh', 'rus': 'ru', 'por': 'pt', 'ita': 'it'
};

const getLanguageName = (code: string | undefined): string | null => {
  if (!code || code === 'und') return null;
  let iso1 = code.toLowerCase();
  if (iso6392Map[iso1]) {
    iso1 = iso6392Map[iso1];
  }
  try {
    const displayNames = new Intl.DisplayNames(['en'], { type: 'language' });
    return displayNames.of(iso1) || code;
  } catch (e) {
    return code;
  }
};

const formatTrackName = (track: any, defaultPrefix: string) => {
  const lang = getLanguageName(track.language || track.lang);
  let title = track.title || track.name;
  
  // Clean spam titles
  if (title && (title.toLowerCase().includes('.vip') || title.toLowerCase().includes('.com') || title.toLowerCase().includes('.org') || title.toLowerCase().includes('.net'))) {
    title = '';
  }

  let baseName = '';
  if (lang && title && lang.toLowerCase() !== title.toLowerCase()) {
    baseName = `${lang} (${title})`;
  } else if (lang) {
    baseName = lang;
  } else if (title) {
    baseName = title;
  } else {
    const idx = track.index !== undefined ? track.index : track.id;
    return `${defaultPrefix} ${idx !== undefined ? idx + 1 : ''}`;
  }

  // Check for duplicates in tracks list to append option index
  const list = defaultPrefix === 'Sub' ? subtitleTracks.value : audioTracks.value;
  const matches = list.filter((t: any) => {
    const tLang = getLanguageName(t.language || t.lang);
    let tTitle = t.title || t.name;
    if (tTitle && (tTitle.toLowerCase().includes('.vip') || tTitle.toLowerCase().includes('.com') || tTitle.toLowerCase().includes('.org') || tTitle.toLowerCase().includes('.net'))) {
      tTitle = '';
    }
    const tBase = tLang && tTitle && tLang.toLowerCase() !== tTitle.toLowerCase()
      ? `${tLang} (${tTitle})`
      : (tLang || tTitle || '');
    return tBase === baseName;
  });

  if (matches.length > 1) {
    const currentId = track.index !== undefined ? track.index : track.id;
    const matchIndex = matches.findIndex((t: any) => (t.index !== undefined ? t.index : t.id) === currentId);
    return `${baseName} - Option ${matchIndex + 1}`;
  }

  return baseName;
};

// Element refs
const containerRef = ref<HTMLDivElement | null>(null);
const videoRef = ref<HTMLVideoElement | null>(null);

// Player state
const isPaused = ref(true);
const isLoading = ref(true);
const isFullscreen = ref(false);
const showControls = ref(true);
const currentTime = ref(0);
const duration = ref(0);
const bufferPercent = ref(0);

// Volume state
const volumeValue = ref(1.0); 
const isMuted = ref(false);

// Quality state
const isHlsSupported = ref(false);
const qualityLevels = ref<any[]>([]);
const currentQuality = ref<any>(-1);

// Settings panel state
const showSubtitlesMenu = ref(false);
const showAudioMenu = ref(false);
const showQualityMenu = ref(false);

// Audio & subtitle track state
const audioTracks = ref<any[]>(props.initialAudioTracks ?? []);
const subtitleTracks = ref<any[]>(props.initialSubtitleTracks ?? []);
const currentAudioTrack = ref<number>(-1);
const currentSubtitleTrack = ref<number>(-1);

watch(() => props.initialAudioTracks, (newVal) => {
  if (newVal && newVal.length > 0) {
    audioTracks.value = newVal;
    if (currentAudioTrack.value === -1) {
      const defaultTrack = newVal.find(t => t.index === 0) || newVal[0];
      currentAudioTrack.value = defaultTrack ? defaultTrack.index : -1;
    }
  }
}, { immediate: true });

watch(() => props.initialSubtitleTracks, (newVal) => {
  if (newVal && newVal.length > 0) {
    subtitleTracks.value = newVal;
  }
}, { immediate: true });

// Touch interaction
const showSkipBackAnim = ref(false);
const showSkipForwardAnim = ref(false);
let hideControlsTimeout: number | null = null;
let lastTouchTime = 0;

// Web Audio API volume booster nodes

// HLS.js instance
let hls: Hls | null = null;
let initializedTime = false;
let isSeeking = ref(false);

const progressPercent = computed(() => {
  return duration.value ? (currentTime.value / duration.value) * 100 : 0;
});

const isIOS = computed(() => {
  return /iPad|iPhone|iPod/.test(navigator.userAgent) || 
         (navigator.userAgent.includes('Mac') && 'ontouchend' in document);
});

const currentQualityLabel = computed(() => {
  if (isHlsSupported.value) {
    if (currentQuality.value === -1) return 'Auto';
    const activeLevel = qualityLevels.value.find(l => l.index === currentQuality.value);
    return activeLevel ? activeLevel.label : '';
  } else {
    if (currentQuality.value === 'auto') return 'Auto';
    return currentQuality.value || 'Auto';
  }
});

const toggleSubtitlesMenu = () => {
  showSubtitlesMenu.value = !showSubtitlesMenu.value;
  showAudioMenu.value = false;
  showQualityMenu.value = false;
};

const toggleAudioMenu = () => {
  showAudioMenu.value = !showAudioMenu.value;
  showSubtitlesMenu.value = false;
  showQualityMenu.value = false;
};

const toggleQualityMenu = () => {
  showQualityMenu.value = !showQualityMenu.value;
  showSubtitlesMenu.value = false;
  showAudioMenu.value = false;
};

const closeAllMenus = () => {
  showSubtitlesMenu.value = false;
  showAudioMenu.value = false;
  showQualityMenu.value = false;
};

const updateVolume = () => {
  if (!videoRef.value) return;
  videoRef.value.muted = isMuted.value;
  videoRef.value.volume = isMuted.value ? 0 : volumeValue.value;
};

const onVolumeSliderInput = (e: Event) => {
  const val = parseFloat((e.target as HTMLInputElement).value);
  volumeValue.value = val;
  isMuted.value = (val === 0);
  updateVolume();
};

const toggleMute = () => {
  isMuted.value = !isMuted.value;
  updateVolume();
};

// ── Shared HLS.js config for adaptive, low-latency playback ─────────
const hlsConfig = () => ({
  startLevel: -1,                   // Adaptive — let ABR pick the best level
  capLevelToPlayerSize: true,
  maxBufferLength: 10,              // Buffer 10s ahead (reduced from 15s to save bandwidth)
  maxMaxBufferLength: 20,           // (reduced from 30s)
  maxBufferSize: 30 * 1000 * 1000,  // 30 MB (reduced from 60 MB)
  maxBufferHole: 0.5,               // Allow small buffer gaps
  lowLatencyMode: false,            // VOD, not live
  enableWorker: true,
  backBufferLength: 5,              // (reduced from 10s)
  startFragPrefetch: true,          // Prefetch first fragment eagerly
  // Timeouts tuned for Indian connections / on-demand transcoding
  fragLoadingTimeOut: 60000,        // 60s for fragment loading (transcoding takes time)
  fragLoadingMaxRetry: 8,           // Retry fragments up to 8 times
  fragLoadingRetryDelay: 1000,      // 1s between retries
  fragLoadingMaxRetryTimeout: 120000,
  manifestLoadingTimeOut: 30000,
  manifestLoadingMaxRetry: 4,
  levelLoadingTimeOut: 30000,
  levelLoadingMaxRetry: 4,
  // ABR tuning for adaptive quality
  abrEwmaDefaultEstimate: 400_000,     // Start assuming ~400 kbps (forces 240p/360p start)
  abrBandWidthUpFactor: 0.7,           // Conservative upgrade
  abrBandWidthFactor: 0.95,
});

const setupHlsErrorRecovery = (hlsInstance: Hls) => {
  hlsInstance.on(Hls.Events.ERROR, (_event: any, data: any) => {
    if (!data.fatal) return;

    switch (data.type) {
      case Hls.ErrorTypes.NETWORK_ERROR:
        console.warn('[HLS] Fatal network error — attempting recovery');
        hlsInstance.startLoad();
        break;
      case Hls.ErrorTypes.MEDIA_ERROR:
        console.warn('[HLS] Fatal media error — attempting recovery');
        hlsInstance.recoverMediaError();
        break;
      default:
        console.error('[HLS] Fatal error, cannot recover:', data);
        break;
    }
  });
};

const initPlayer = () => {
  if (!videoRef.value) return;

  isHlsSupported.value = Hls.isSupported();

  if (Hls.isSupported()) {
    hls = new Hls(hlsConfig());
    setupHlsErrorRecovery(hls);

    hls.loadSource(props.src);
    hls.attachMedia(videoRef.value);
    
    hls.on(Hls.Events.MANIFEST_PARSED, () => {
      videoRef.value?.play().catch(() => {});
      isPaused.value = false;
      
      const levels = hls!.levels.map((level, idx) => ({
        index: idx,
        height: level.height,
        label: `${level.height}p`,
        value: level.height.toString()
      }));
      levels.sort((a, b) => b.height - a.height);
      qualityLevels.value = levels;
      currentQuality.value = -1;  // Adaptive

      // Extract Audio Tracks from HLS.js (populated from EXT-X-MEDIA in master)
      if (hls!.audioTracks && hls!.audioTracks.length > 1) {
        audioTracks.value = hls!.audioTracks.map((track) => ({
          index: track.id,
          title: track.name || track.lang || `Track ${track.id + 1}`,
          language: track.lang,
          channels: 2
        }));
        currentAudioTrack.value = hls!.audioTrack;
      }
    });

  } else if (videoRef.value.canPlayType('application/vnd.apple.mpegurl')) {
    videoRef.value.src = props.src;
    videoRef.value.addEventListener('loadedmetadata', () => {
      videoRef.value?.play().catch(() => {});
      isPaused.value = false;
      duration.value = videoRef.value?.duration || 0;

      // Extract Audio Tracks natively in Safari/iOS
      const nativeAudioTracks = (videoRef.value as any).audioTracks;
      if (nativeAudioTracks && nativeAudioTracks.length > 0) {
        const list = [];
        for (let i = 0; i < nativeAudioTracks.length; i++) {
          const track = nativeAudioTracks[i];
          list.push({
            index: i,
            title: track.label || track.language || `Track ${i + 1}`,
            language: track.language,
            channels: 2
          });
          if (track.enabled) {
            currentAudioTrack.value = i;
          }
        }
        audioTracks.value = list;
      }
    });
    
    qualityLevels.value = [
      { index: 0, height: 1080, label: '1080p', value: '1080p' },
      { index: 1, height: 720, label: '720p', value: '720p' },
      { index: 2, height: 480, label: '480p', value: '480p' },
      { index: 3, height: 360, label: '360p', value: '360p' },
      { index: 4, height: 240, label: '240p', value: '240p' },
    ];
    currentQuality.value = 'auto';
  }
};

const changeQuality = (val: any) => {
  if (!videoRef.value) return;
  const time = videoRef.value.currentTime;
  const playing = !videoRef.value.paused;
  currentQuality.value = val;

  if (isHlsSupported.value && hls) {
    isLoading.value = true;
    hls.destroy();

    // Recreate Hls instance with the forced startLevel
    const config = hlsConfig();
    config.startLevel = val;
    if (val !== -1) {
      config.capLevelToPlayerSize = false;
    }
    hls = new Hls(config);
    setupHlsErrorRecovery(hls);

    hls.loadSource(props.src);
    hls.attachMedia(videoRef.value);

    hls.on(Hls.Events.MANIFEST_PARSED, () => {
      if (videoRef.value) {
        videoRef.value.currentTime = time;
        if (playing) {
          videoRef.value.play().catch(() => {});
        }

        // Restore active audio track
        if (currentAudioTrack.value !== -1 && hls && hls.audioTracks && hls.audioTracks.length > 1) {
          hls.audioTrack = currentAudioTrack.value;
        }

        // Restore active subtitle track
        if (currentSubtitleTrack.value !== -1) {
          const track = subtitleTracks.value.find((t: any) => t.index === currentSubtitleTrack.value);
          if (track) {
            changeSubtitleTrack(currentSubtitleTrack.value, track);
          }
        }
      }

      // Re-map qualityLevels and audioTracks
      if (!hls) return;
      const levels = hls.levels.map((level, idx) => ({
        index: idx,
        height: level.height,
        label: `${level.height}p`,
        value: level.height.toString()
      }));
      levels.sort((a, b) => b.height - a.height);
      qualityLevels.value = levels;

      if (hls.audioTracks && hls.audioTracks.length > 1) {
        audioTracks.value = hls.audioTracks.map((track) => ({
          index: track.id,
          title: track.name || track.lang || `Track ${track.id + 1}`,
          language: track.lang,
          channels: 2
        }));
        currentAudioTrack.value = hls.audioTrack;
      }
    });

  } else {
    let newSrc = props.src;
    if (val !== 'auto') {
      newSrc = props.src.replace('master.m3u8', `${val}/playlist.m3u8`);
    }
    videoRef.value.src = newSrc;
    videoRef.value.load();
    videoRef.value.currentTime = time;
    if (playing) videoRef.value.play().catch(() => {});
  }
  closeAllMenus();
};

const changeAudioTrack = (track: any) => {
  if (!videoRef.value) return;
  currentAudioTrack.value = track.index;

  if (isHlsSupported.value && hls) {
    // Switch audio instantly and natively in Hls.js
    hls.audioTrack = track.index;
    console.log("Hls.js switched audio track to index:", track.index);
  } else {
    // Native HTML5 audio track switching (Safari / iOS)
    const nativeAudioTracks = (videoRef.value as any).audioTracks;
    if (nativeAudioTracks) {
      for (let i = 0; i < nativeAudioTracks.length; i++) {
        nativeAudioTracks[i].enabled = (i === track.index);
      }
      console.log("Native Safari switched audio track to index:", track.index);
    }
  }
  closeAllMenus();
};

const changeSubtitleTrack = (trackIndex: number, track: any | null) => {
  if (!videoRef.value) return;
  currentSubtitleTrack.value = trackIndex;

  // Remove all existing <track> elements
  const existingTracks = videoRef.value.querySelectorAll('track');
  existingTracks.forEach(t => t.remove());

  if (trackIndex !== -1 && track !== null) {
    const trackEl = document.createElement('track');
    trackEl.kind = 'subtitles';
    trackEl.label = track.title || track.language || `Sub ${trackIndex + 1}`;
    trackEl.srclang = track.language || 'und';
    trackEl.src = `${BASE_URL}/api/v1/stream/${props.mediaId}/subtitle/${track.index}.vtt`;
    trackEl.default = true;
    
    trackEl.onload = () => {
      if (videoRef.value && videoRef.value.textTracks.length > 0) {
        for (let i = 0; i < videoRef.value.textTracks.length; i++) {
          videoRef.value.textTracks[i].mode = 'showing';
        }
      }
    };

    videoRef.value.appendChild(trackEl);
    
    // Fallback immediate mode trigger
    if (videoRef.value.textTracks.length > 0) {
      videoRef.value.textTracks[videoRef.value.textTracks.length - 1].mode = 'showing';
    }
  }
  closeAllMenus();
};

const onCanPlay = () => {
  isLoading.value = false;
  if (videoRef.value) {
    duration.value = videoRef.value.duration;
  }
  if (videoRef.value && !initializedTime) {
    initializedTime = true;
    const savedTime = continueWatchingStore.getProgress(props.mediaId);
    if (savedTime > 0 && savedTime < (videoRef.value.duration - 10)) {
      videoRef.value.currentTime = savedTime;
      currentTime.value = savedTime;
    }
  }
};

const onTimeUpdate = () => {
  if (videoRef.value && !isSeeking.value) {
    currentTime.value = videoRef.value.currentTime;
    continueWatchingStore.saveProgress(props.mediaId, currentTime.value);
  }
  updateBuffer();
};

const updateBuffer = () => {
  if (videoRef.value && videoRef.value.buffered.length > 0 && duration.value > 0) {
    const buffered = videoRef.value.buffered;
    let currentBufferEnd = 0;
    const time = currentTime.value;
    for (let i = 0; i < buffered.length; i++) {
      if (buffered.start(i) <= time && time <= buffered.end(i)) {
        currentBufferEnd = buffered.end(i);
        break;
      }
    }
    bufferPercent.value = (currentBufferEnd / duration.value) * 100;
  }
};

const onWaiting = () => { isLoading.value = true; };
const onPlaying = () => { isLoading.value = false; isPaused.value = false; };

const togglePlay = () => {
  if (!videoRef.value) return;

  if (!isIOS.value && videoRef.value.volume > 0) {
    // Just a placeholder if we ever need to resume audio context
  }

  if (videoRef.value.paused) {
    videoRef.value.play().catch(() => {});
    isPaused.value = false;
  } else {
    videoRef.value.pause();
    isPaused.value = true;
  }
  triggerShowControls();
};

const onSeekInput = (e: Event) => {
  isSeeking.value = true;
  currentTime.value = parseFloat((e.target as HTMLInputElement).value);
};

const onSeekChange = (e: Event) => {
  if (videoRef.value) {
    const val = parseFloat((e.target as HTMLInputElement).value);
    videoRef.value.currentTime = val;
    currentTime.value = val;
  }
  isSeeking.value = false;
};

const skip = (seconds: number) => {
  if (videoRef.value) {
    let targetTime = videoRef.value.currentTime + seconds;
    if (targetTime < 0) targetTime = 0;
    if (targetTime > duration.value) targetTime = duration.value;
    videoRef.value.currentTime = targetTime;
    currentTime.value = targetTime;
  }
  triggerShowControls();
};

const handleVideoTouch = (e: TouchEvent) => {
  const now = Date.now();
  const diff = now - lastTouchTime;
  
  if (diff < 300) {
    const rect = (e.currentTarget as HTMLElement).getBoundingClientRect();
    const touchX = e.touches[0].clientX - rect.left;
    const width = rect.width;
    
    if (touchX < width * 0.4) {
      skip(-10);
      showSkipBackAnim.value = true;
      setTimeout(() => showSkipBackAnim.value = false, 500);
    } else if (touchX > width * 0.6) {
      skip(10);
      showSkipForwardAnim.value = true;
      setTimeout(() => showSkipForwardAnim.value = false, 500);
    } else {
      toggleFullscreen();
    }
    e.preventDefault();
  } else {
    if (!showControls.value) {
      triggerShowControls();
    } else {
      togglePlay();
    }
  }
  lastTouchTime = now;
};

const toggleFullscreen = () => {
  const container = containerRef.value;
  if (!container) return;

  if (!document.fullscreenElement && !(document as any).webkitFullscreenElement && !container.classList.contains('fake-fullscreen')) {
    if (isIOS.value) {
      // iOS native fullscreen strips custom UI. Use CSS fixed positioning instead.
      container.classList.add('fake-fullscreen');
      isFullscreen.value = true;
      return;
    }

    if (container.requestFullscreen) {
      container.requestFullscreen().catch(err => {
        console.error("Fullscreen request failed:", err);
      });
    } else if ((container as any).webkitRequestFullscreen) {
      (container as any).webkitRequestFullscreen();
    } else if (videoRef.value && (videoRef.value as any).webkitEnterFullscreen) {
      (videoRef.value as any).webkitEnterFullscreen();
    }
  } else {
    if (container.classList.contains('fake-fullscreen')) {
      container.classList.remove('fake-fullscreen');
      isFullscreen.value = false;
      return;
    }

    if (document.exitFullscreen) {
      document.exitFullscreen();
    } else if ((document as any).webkitExitFullscreen) {
      (document as any).webkitExitFullscreen();
    }
  }
};

const handleFullscreenChange = () => {
  isFullscreen.value = !!(document.fullscreenElement || (document as any).webkitFullscreenElement);
  closeAllMenus();
};

const triggerShowControls = () => {
  showControls.value = true;
  if (hideControlsTimeout) clearTimeout(hideControlsTimeout);
  if (!isPaused.value) {
    hideControlsTimeout = window.setTimeout(() => {
      showControls.value = false;
      closeAllMenus();
    }, 3000);
  }
};

// Close settings when clicking outside
const handleOutsideClick = () => {
  closeAllMenus();
};

const formatTime = (seconds: number) => {
  if (isNaN(seconds) || seconds === Infinity) return "0:00";
  const hrs = Math.floor(seconds / 3600);
  const mins = Math.floor((seconds % 3600) / 60);
  const secs = Math.floor(seconds % 60);
  const paddedSecs = secs.toString().padStart(2, '0');
  if (hrs > 0) {
    const paddedMins = mins.toString().padStart(2, '0');
    return `${hrs}:${paddedMins}:${paddedSecs}`;
  }
  return `${mins}:${paddedSecs}`;
};

const goBack = () => { router.back(); };

const handleKeyDown = (e: KeyboardEvent) => {
  if (e.code === 'Space') { e.preventDefault(); togglePlay(); }
  else if (e.code === 'ArrowLeft') { e.preventDefault(); skip(-10); }
  else if (e.code === 'ArrowRight') { e.preventDefault(); skip(10); }
  else if (e.code === 'KeyF') { e.preventDefault(); toggleFullscreen(); }
  else if (e.code === 'KeyM') { e.preventDefault(); toggleMute(); }
  else if (e.code === 'Escape') { closeAllMenus(); }
};

onMounted(() => {
  initPlayer();
  document.addEventListener('fullscreenchange', handleFullscreenChange);
  document.addEventListener('webkitfullscreenchange', handleFullscreenChange);
  window.addEventListener('keydown', handleKeyDown);
  document.addEventListener('click', handleOutsideClick, true);
  triggerShowControls();
});

onUnmounted(() => {
  if (hls) hls.destroy();
  document.removeEventListener('fullscreenchange', handleFullscreenChange);
  document.removeEventListener('webkitfullscreenchange', handleFullscreenChange);
  window.removeEventListener('keydown', handleKeyDown);
  document.removeEventListener('click', handleOutsideClick, true);
  if (hideControlsTimeout) clearTimeout(hideControlsTimeout);
});
</script>

<style scoped>
.player-container {
  width: 100vw;
  height: 100vh;
  background: #000;
  position: relative;
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
  user-select: none;
  font-family: 'Outfit', 'Inter', sans-serif;
}

.fake-fullscreen {
  position: fixed !important;
  top: 0 !important;
  left: 0 !important;
  width: 100vw !important;
  height: 100vh !important;
  z-index: 9999999 !important;
  margin: 0 !important;
  padding: 0 !important;
}

.hide-cursor { cursor: none; }

.player {
  width: 100%;
  height: 100%;
  object-fit: contain;
}

/* Gradients */
.overlay-top, .overlay-bottom {
  position: absolute;
  left: 0;
  right: 0;
  height: 180px;
  pointer-events: none;
  transition: opacity 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  opacity: 0;
  z-index: 10;
}
.overlay-top { top: 0; background: linear-gradient(to bottom, rgba(0,0,0,0.85) 0%, rgba(0,0,0,0) 100%); }
.overlay-bottom { bottom: 0; background: linear-gradient(to top, rgba(0,0,0,0.92) 0%, rgba(0,0,0,0) 100%); }
.overlay-top.visible, .overlay-bottom.visible { opacity: 1; }

/* Back button */
.back-btn {
  position: absolute;
  top: 40px;
  left: 40px;
  z-index: 100;
  color: white;
  background: rgba(255, 255, 255, 0.08);
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 50%;
  width: 48px;
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s ease;
  cursor: pointer;
  opacity: 0;
  pointer-events: none;
}
.back-btn.visible { opacity: 1; pointer-events: auto; }
.back-btn:hover { background: rgba(255, 255, 255, 0.2); transform: scale(1.05); }

/* Loading */
.loader-container {
  position: absolute;
  z-index: 20;
  display: flex;
  align-items: center;
  justify-content: center;
  pointer-events: none;
}
.spinner {
  width: 64px;
  height: 64px;
  color: #7c3aed;
  animation: spin 1s linear infinite;
  filter: drop-shadow(0 0 12px rgba(124, 58, 237, 0.6));
}
@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }

/* Skip animations */
.skip-anim {
  position: absolute;
  top: 0;
  bottom: 0;
  width: 40%;
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 15;
  pointer-events: none;
  background: rgba(255, 255, 255, 0.04);
  animation: fadeOut 0.5s ease-out forwards;
}
.skip-anim.back { left: 0; border-radius: 0 100px 100px 0; }
.skip-anim.forward { right: 0; border-radius: 100px 0 0 100px; }
.skip-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  background: rgba(0, 0, 0, 0.65);
  padding: 16px 24px;
  border-radius: 50%;
  color: white;
}
.skip-icon { font-size: 20px; font-weight: bold; }
.skip-text { font-size: 14px; margin-top: 4px; font-weight: 500; }
@keyframes fadeOut { 0% { opacity: 1; } 100% { opacity: 0; } }

/* Controls overlay */
.controls-overlay {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  padding: 20px 40px 30px;
  z-index: 50;
  transition: opacity 0.3s cubic-bezier(0.4, 0, 0.2, 1), transform 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  opacity: 0;
  pointer-events: none;
  transform: translateY(10px);
}
.controls-overlay.visible { opacity: 1; pointer-events: auto; transform: translateY(0); }

/* Timeline */
.timeline-container {
  position: relative;
  height: 5px;
  width: 100%;
  margin-bottom: 18px;
  cursor: pointer;
  border-radius: 3px;
  transition: height 0.15s ease;
}
.timeline-container:hover { height: 8px; }
.timeline-track {
  position: absolute;
  left: 0; right: 0; top: 0; bottom: 0;
  background: rgba(255, 255, 255, 0.18);
  border-radius: 3px;
}
.timeline-buffer {
  position: absolute;
  left: 0; top: 0; bottom: 0;
  background: rgba(255, 255, 255, 0.35);
  border-radius: 3px;
  transition: width 0.2s ease;
}
.timeline-progress {
  position: absolute;
  left: 0; top: 0; bottom: 0;
  background: linear-gradient(to right, #7c3aed, #a78bfa);
  border-radius: 3px;
  box-shadow: 0 0 10px rgba(124, 58, 237, 0.55);
}
.timeline-slider {
  position: absolute;
  left: 0; right: 0;
  top: -10px; bottom: -10px;
  width: 100%;
  opacity: 0;
  cursor: pointer;
  margin: 0;
}

/* Controls row */
.controls-row { display: flex; align-items: center; justify-content: space-between; }
.controls-row button { outline: none; }
.controls-left, .controls-right { display: flex; align-items: center; gap: 12px; }

.control-btn {
  background: none;
  border: none;
  color: white;
  cursor: pointer;
  padding: 8px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.2s, transform 0.1s;
}
.control-btn:hover { background: rgba(255, 255, 255, 0.1); transform: scale(1.08); }
.control-btn:active { transform: scale(0.95); }
.icon { width: 24px; height: 24px; }

.skip-btn { font-size: 13px; font-weight: 600; color: #e0e0e0; padding: 4px 8px; border-radius: 4px; }
.skip-btn:hover { background: rgba(255, 255, 255, 0.12); color: white; }

/* Volume */
.volume-control-wrapper { display: flex; align-items: center; gap: 8px; }
.volume-slider-container {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 0;
  opacity: 0;
  overflow: hidden;
  transition: width 0.3s ease, opacity 0.3s ease;
}
.volume-control-wrapper:hover .volume-slider-container { width: 170px; opacity: 1; }
.volume-slider {
  -webkit-appearance: none; appearance: none;
  width: 100px; height: 4px;
  background: rgba(255,255,255,0.2);
  border-radius: 2px;
  outline: none;
  cursor: pointer;
}
.volume-slider::-webkit-slider-runnable-track {
  width: 100%; height: 4px;
  background: linear-gradient(to right, white var(--val, 100%), rgba(255,255,255,0.2) var(--val, 100%));
  border-radius: 2px;
}
.volume-slider::-webkit-slider-thumb {
  -webkit-appearance: none;
  height: 13px; width: 13px;
  border-radius: 50%;
  background: white;
  cursor: pointer;
  margin-top: -4.5px;
  transition: transform 0.1s;
  box-shadow: 0 0 6px rgba(0,0,0,0.5);
}
.volume-slider::-webkit-slider-thumb:hover { transform: scale(1.2); }
.volume-text { font-size: 12px; font-weight: 500; color: #ccc; min-width: 35px; }

/* Responsive Mobile Rules */
@media (max-width: 768px) {
  .controls-overlay {
    padding: 15px 20px 20px;
  }
  .controls-left, .controls-right {
    gap: 4px;
  }
  .skip-btn {
    display: none; /* Hide skip buttons on mobile to save space, rely on double tap */
  }
  .volume-control-wrapper:hover .volume-slider-container {
    width: 80px; /* Shorter volume slider on mobile */
  }
  .time-display {
    font-size: 12px;
    margin-left: 4px;
  }
  .control-btn {
    padding: 6px;
  }
  .icon {
    width: 20px;
    height: 20px;
  }
  .settings-menu {
    width: 160px;
  }
  .menu-item {
    padding: 8px 12px;
    font-size: 12px;
  }
}
@media (max-width: 480px) {
  .volume-control-wrapper {
    display: none; /* Hide volume control entirely on very small screens, use device buttons */
  }
}

/* Time display */
.time-display { font-size: 14px; color: #d0d0d0; font-weight: 400; }

/* Settings wrapper */
.settings-wrapper { position: relative; }
.rotate { transform: rotate(45deg); }
.quality-badge {
  font-size: 10px;
  background: rgba(124, 58, 237, 0.35);
  color: #c4b5fd;
  padding: 2px 6px;
  border-radius: 10px;
  margin-left: 6px;
  font-weight: 600;
}

/* Settings Menu Portal — renders at body level via <Teleport> so it is
   never clipped by the player stacking context, even in fullscreen */
</style>

<!-- Global (non-scoped) styles for the portal settings menu and track badges -->
<style>
.settings-menu {
  position: absolute;
  bottom: 100%;
  right: 0;
  margin-bottom: 12px;
  background: rgba(10, 8, 20, 0.92);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border: 1px solid rgba(124, 58, 237, 0.25);
  border-radius: 12px;
  padding: 6px 0 8px;
  width: 190px;
  box-shadow: 0 8px 32px rgba(0,0,0,0.7), 0 0 0 1px rgba(124,58,237,0.15);
  animation: fadeInUp 0.18s cubic-bezier(0.4, 0, 0.2, 1);
  font-family: 'Outfit', 'Inter', sans-serif;
  z-index: 99999;
}

@keyframes fadeInUp {
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: translateY(0); }
}

.settings-tabs {
  display: flex;
  border-bottom: 1px solid rgba(255,255,255,0.08);
  padding: 0 8px;
  margin-bottom: 4px;
}

.settings-tab {
  flex: 1;
  background: none;
  border: none;
  color: rgba(255,255,255,0.45);
  font-size: 12px;
  font-weight: 600;
  font-family: 'Outfit', 'Inter', sans-serif;
  padding: 8px 4px;
  cursor: pointer;
  letter-spacing: 0.3px;
  border-bottom: 2px solid transparent;
  transition: color 0.2s, border-color 0.2s;
}

.settings-tab.active {
  color: #a78bfa;
  border-bottom-color: #7c3aed;
}

.settings-tab:hover:not(.active) { color: rgba(255,255,255,0.75); }

.menu-item {
  width: 100%;
  background: none;
  border: none;
  color: #d0d0d0;
  padding: 9px 16px;
  text-align: left;
  font-size: 13px;
  font-family: 'Outfit', 'Inter', sans-serif;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: space-between;
  transition: background 0.15s, color 0.15s;
}

.menu-item:hover { background: rgba(124, 58, 237, 0.15); color: white; }

.menu-item.active {
  color: #a78bfa;
  font-weight: 600;
}

.menu-item.active::after { content: '✓'; font-weight: bold; color: #7c3aed; }

.track-badge {
  font-size: 10px;
  background: rgba(124, 58, 237, 0.2);
  color: #c4b5fd;
  padding: 2px 6px;
  border-radius: 8px;
  font-weight: 600;
}

.menu-title {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 1px;
  color: rgba(255, 255, 255, 0.4);
  padding: 6px 16px 8px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
  margin-bottom: 4px;
  font-weight: 700;
}

.menu-no-tracks {
  padding: 12px 16px;
  font-size: 13px;
  color: rgba(255, 255, 255, 0.35);
  font-style: italic;
  text-align: center;
}

.active-btn {
  color: #a78bfa !important;
  filter: drop-shadow(0 0 4px rgba(124, 58, 237, 0.6));
}
</style>
