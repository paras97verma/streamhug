import { defineStore } from 'pinia';
import { api } from '../api/endpoints';
import type { Media } from '../types/media';

interface SearchState {
  query: string;
  results: Media[];
  isLoading: boolean;
  error: string | null;
}

export const useSearchStore = defineStore('search', {
  state: (): SearchState => ({
    query: '',
    results: [],
    isLoading: false,
    error: null,
  }),

  actions: {
    async search(query: string) {
      this.query = query;
      if (!query.trim()) {
        this.results = [];
        return;
      }
      this.isLoading = true;
      this.error = null;
      try {
        const data = await api.searchMedia(query);
        this.results = data.results;
      } catch (err: any) {
        this.error = err?.response?.data?.detail || 'Search failed';
        this.results = [];
      } finally {
        this.isLoading = false;
      }
    },
    clearSearch() {
      this.query = '';
      this.results = [];
    }
  }
});
