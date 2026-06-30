import axios from 'axios';

const API_URL = import.meta.env.VITE_API_URL || '/api/v1';

export const apiClient = axios.create({
  baseURL: API_URL,
  timeout: 10000,
});

apiClient.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('streamhug_access_token');
    if (token) {
      config.headers = config.headers || {};
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    console.error('API Error:', error);
    if (error.response && error.response.status === 401) {
      const token = localStorage.getItem('streamhug_access_token');
      if (token) {
        localStorage.removeItem('streamhug_access_token');
        localStorage.removeItem('streamhug_refresh_token');
        localStorage.removeItem('streamhug_user_name');
        localStorage.removeItem('streamhug_user_email');
        window.location.reload();
      }
    }
    return Promise.reject(error);
  }
);
