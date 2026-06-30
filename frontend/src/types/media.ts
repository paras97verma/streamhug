export interface AudioTrack {
  index: number;
  language: string;
  title: string;
  codec: string;
  channels: number;
}

export interface SubtitleTrack {
  index: number;
  language: string;
  title: string;
  codec: string;
}

export interface MediaTechnicalInfo {
  video_codec: string | null;
  audio_codec: string | null;
  resolution: string | null;
  duration_seconds: number | null;
  bitrate_kbps: number | null;
  audio_tracks: AudioTrack[];
  subtitle_tracks: SubtitleTrack[];
}

export interface Episode {
  id: string;
  season_number: number;
  episode_number: number;
  title: string;
  filename: string;
  relative_path: string;
  technical_info: MediaTechnicalInfo | null;
  date_added: string;
}

export interface Season {
  season_number: number;
  episodes: Episode[];
}

export interface Media {
  id: string;
  type: 'movie' | 'tv' | 'anime';
  title: string;
  year: number | null;
  category: string;
  filename: string;
  relative_path: string;
  technical_info: MediaTechnicalInfo | null;
  date_added: string;
  seasons: Season[] | null;
}

export interface LibrarySummary {
  movies: number;
  tv_shows: number;
  anime: number;
  total: number;
}

export interface Library {
  movies: Media[];
  tv_shows: Media[];
  anime: Media[];
}

export interface LibraryResponse {
  library: Library;
  summary: LibrarySummary;
}

export interface SearchResponse {
  query: string;
  results: Media[];
  total: number;
}

export interface MediaDetailResponse {
  media: Media;
}

export interface HealthResponse {
  status: string;
  version: string;
  media_count: number;
}
