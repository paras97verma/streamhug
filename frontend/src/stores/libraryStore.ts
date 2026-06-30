import { defineStore } from 'pinia';
import { api } from '../api/endpoints';
import type { Library, LibrarySummary } from '../types/media';

interface LibraryState {
  library: Library | null;
  summary: LibrarySummary | null;
  isLoading: boolean;
  error: string | null;
}

export const useLibraryStore = defineStore('library', {
  state: (): LibraryState => ({
    library: null,
    summary: null,
    isLoading: false,
    error: null,
  }),
  
  actions: {
    async fetchLibrary() {
      // Allow re-fetching even if library exists to support hot reloading
      this.isLoading = true;
      this.error = null;
      try {
        const data = await api.getLibrary();
        this.library = data.library;
        this.summary = data.summary;
      } catch (err: any) {
        this.error = err?.response?.data?.detail || 'Failed to fetch library';
      } finally {
        this.isLoading = false;
      }
    },
    
    initSSE() {
      const sseUrl = import.meta.env.VITE_API_URL 
        ? `${import.meta.env.VITE_API_URL}/events` 
        : '/api/v1/events';
        
      const eventSource = new EventSource(sseUrl);
      
      eventSource.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.event === 'library_updated') {
            console.log('Library updated on backend, refreshing UI...');
            // Refetch library without clearing existing state (to prevent full UI flicker)
            this.fetchLibrary();
          }
        } catch (e) {
          // ignore parsing errors
        }
      };
      
      eventSource.onerror = (error) => {
        console.error('SSE Error:', error);
      };
    }
  }
});
