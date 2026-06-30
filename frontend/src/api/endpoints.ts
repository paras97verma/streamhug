import { apiClient } from './client';
import type { LibraryResponse, SearchResponse, MediaDetailResponse, HealthResponse, Media, Season, Episode } from '../types/media';

const API_URL = import.meta.env.VITE_API_URL || '/api/v1';

// ── Response Mapper to Standardize Backend Schema to Frontend Schema ───────

function mapBackendTechnicalInfo(rawInfo: any) {
  if (!rawInfo) return null;
  return {
    video_codec: rawInfo.video_codec || null,
    audio_codec: rawInfo.audio_codec || null,
    resolution: (rawInfo.width && rawInfo.height) ? `${rawInfo.width}x${rawInfo.height}` : null,
    duration_seconds: rawInfo.duration_seconds || null,
    bitrate_kbps: rawInfo.bitrate_kbps || null,
    audio_tracks: rawInfo.audio_tracks || [],
    subtitle_tracks: rawInfo.subtitle_tracks || [],
  };
}

function mapBackendEpisode(rawEp: any): Episode {
  const filename = rawEp.file_path ? rawEp.file_path.split('/').pop() || '' : '';
  return {
    id: rawEp.media_id,
    season_number: rawEp.season_number,
    episode_number: rawEp.episode_number,
    title: rawEp.title,
    filename: filename,
    relative_path: rawEp.file_path || '',
    technical_info: mapBackendTechnicalInfo(rawEp.technical_info),
    date_added: new Date().toISOString(),
  };
}

function mapBackendSeason(rawSeason: any): Season {
  return {
    season_number: rawSeason.season_number,
    episodes: (rawSeason.episodes || []).map(mapBackendEpisode),
  };
}

function mapBackendMedia(rawMedia: any): Media {
  const typeMap: Record<string, 'movie' | 'tv' | 'anime'> = {
    'movie': 'movie',
    'tv_show': 'tv',
    'anime': 'anime',
  };
  
  const filename = rawMedia.file_path ? rawMedia.file_path.split('/').pop() || '' : '';
  
  return {
    id: rawMedia.media_id,
    type: typeMap[rawMedia.media_type] || 'movie',
    title: rawMedia.title,
    year: rawMedia.year || null,
    category: rawMedia.media_type,
    filename: filename,
    relative_path: rawMedia.file_path || '',
    technical_info: mapBackendTechnicalInfo(rawMedia.technical_info),
    date_added: new Date().toISOString(),
    seasons: rawMedia.seasons ? rawMedia.seasons.map(mapBackendSeason) : null,
  };
}

export const api = {
  async getHealth(): Promise<HealthResponse> {
    const { data } = await apiClient.get<HealthResponse>('/health');
    return data;
  },

  async getLibrary(): Promise<LibraryResponse> {
    const { data } = await apiClient.get<any>('/library');
    
    // Transform library contents
    const library = {
      movies: (data.library?.movies || []).map(mapBackendMedia),
      tv_shows: (data.library?.tv_shows || []).map(mapBackendMedia),
      anime: (data.library?.anime || []).map(mapBackendMedia),
    };
    
    return {
      library,
      summary: data.summary || { movies: 0, tv_shows: 0, anime: 0, total: 0 },
    };
  },

  async searchMedia(query: string): Promise<SearchResponse> {
    const { data } = await apiClient.get<any>('/search', {
      params: { q: query },
    });
    
    const results = (data.results || []).map(mapBackendMedia);
    return {
      query: data.query || query,
      results,
      total: data.total || results.length,
    };
  },

  async getMediaDetail(mediaId: string): Promise<MediaDetailResponse> {
    const { data } = await apiClient.get<any>(`/movie/${mediaId}`);
    return {
      media: mapBackendMedia(data.media),
    };
  },

  async getBackendName(): Promise<{ name: string }> {
    const { data } = await apiClient.get<{ name: string }>('/name');
    return data;
  },

  async saveBackendName(name: string): Promise<{ name: string }> {
    const { data } = await apiClient.post<{ name: string }>('/name', { name });
    return data;
  },

  async signin(payload: any): Promise<any> {
    const { data } = await apiClient.post<any>('/auth/signin', payload);
    return data;
  },

  async signup(payload: any): Promise<any> {
    const { data } = await apiClient.post<any>('/auth/signup', payload);
    return data;
  },

  async getMe(): Promise<any> {
    const { data } = await apiClient.get<any>('/auth/me');
    return data;
  },

  async refreshToken(payload: any): Promise<any> {
    const { data } = await apiClient.post<any>('/auth/refresh', payload);
    return data;
  },

  getPosterUrl(mediaId: string): string {
    return `${API_URL}/poster/${mediaId}`;
  },

  getBannerUrl(mediaId: string): string {
    return `${API_URL}/banner/${mediaId}`;
  },

  getStreamUrl(mediaId: string): string {
    return `${API_URL}/stream/${mediaId}/master.m3u8`;
  },

  getMediaUrl(mediaId: string): string {
    return `${API_URL}/movie/${mediaId}`;
  },
};
