import { defineStore } from 'pinia';

interface ProgressMap {
  [mediaId: string]: number; // seconds
}

interface ContinueWatchingState {
  progress: ProgressMap;
}

export const useContinueWatchingStore = defineStore('continueWatching', {
  state: (): ContinueWatchingState => {
    let saved: ProgressMap = {};
    try {
      const stored = localStorage.getItem('streamhug_progress');
      if (stored) saved = JSON.parse(stored);
    } catch (e) {
      console.warn('Could not parse saved progress');
    }
    return { progress: saved };
  },

  actions: {
    saveProgress(mediaId: string, seconds: number) {
      // Don't save if progress is less than 5 seconds
      if (seconds < 5) return;
      this.progress[mediaId] = seconds;
      this.persist();
    },
    
    getProgress(mediaId: string): number {
      return this.progress[mediaId] || 0;
    },
    
    clearProgress(mediaId: string) {
      delete this.progress[mediaId];
      this.persist();
    },

    persist() {
      try {
        localStorage.setItem('streamhug_progress', JSON.stringify(this.progress));
      } catch (e) {
        console.warn('Failed to save progress to localStorage');
      }
    }
  }
});
