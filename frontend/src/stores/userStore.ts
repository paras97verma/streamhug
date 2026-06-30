import { defineStore } from 'pinia';
import { api } from '@/api/endpoints';

export const useUserStore = defineStore('user', {
  state: () => ({
    name: localStorage.getItem('streamhug_user_name') || '',
    email: localStorage.getItem('streamhug_user_email') || '',
    token: localStorage.getItem('streamhug_access_token') || '',
    refreshToken: localStorage.getItem('streamhug_refresh_token') || '',
    isAuthorized: !!localStorage.getItem('streamhug_access_token'),
  }),

  getters: {
    appName(): string {
      return 'StreamHug';
    },
    avatarInitial(): string {
      return this.name ? this.name.charAt(0).toUpperCase() : 'S';
    }
  },

  actions: {
    setName(newName: string) {
      const cleanName = newName.trim();
      if (!cleanName) return;
      
      this.name = cleanName;
      localStorage.setItem('streamhug_user_name', cleanName);
    },

    async login(email: string, password: string) {
      try {
        const response = await api.signin({ email, password });
        this.name = response.user.name;
        this.email = response.user.email;
        this.token = response.tokens.access_token;
        this.refreshToken = response.tokens.refresh_token;
        this.isAuthorized = true;

        localStorage.setItem('streamhug_user_name', response.user.name);
        localStorage.setItem('streamhug_user_email', response.user.email);
        localStorage.setItem('streamhug_access_token', response.tokens.access_token);
        localStorage.setItem('streamhug_refresh_token', response.tokens.refresh_token);
      } catch (error) {
        console.error('Login failed:', error);
        throw error;
      }
    },

    async register(name: string, email: string, password: string) {
      try {
        await api.signup({ name, email, password });
        // Auto-login since verification is bypassed
        await this.login(email, password);
      } catch (error) {
        console.error('Registration failed:', error);
        throw error;
      }
    },

    async checkAuth() {
      if (!this.token) {
        this.logout();
        return;
      }
      try {
        const response = await api.getMe();
        if (response.user) {
          this.name = response.user.name;
          this.email = response.user.email;
          this.isAuthorized = true;
          localStorage.setItem('streamhug_user_name', response.user.name);
          localStorage.setItem('streamhug_user_email', response.user.email);
        }
      } catch (error) {
        console.warn('Initial token validation failed, attempting refresh...', error);
        if (this.refreshToken) {
          try {
            const refreshResponse = await api.refreshToken({ refresh_token: this.refreshToken });
            this.name = refreshResponse.user.name;
            this.email = refreshResponse.user.email;
            this.token = refreshResponse.tokens.access_token;
            this.refreshToken = refreshResponse.tokens.refresh_token;
            this.isAuthorized = true;

            localStorage.setItem('streamhug_user_name', refreshResponse.user.name);
            localStorage.setItem('streamhug_user_email', refreshResponse.user.email);
            localStorage.setItem('streamhug_access_token', refreshResponse.tokens.access_token);
            localStorage.setItem('streamhug_refresh_token', refreshResponse.tokens.refresh_token);
          } catch (refreshErr) {
            console.error('Token refresh failed:', refreshErr);
            this.logout();
          }
        } else {
          this.logout();
        }
      }
    },

    logout() {
      this.name = '';
      this.email = '';
      this.token = '';
      this.refreshToken = '';
      this.isAuthorized = false;
      localStorage.removeItem('streamhug_user_name');
      localStorage.removeItem('streamhug_user_email');
      localStorage.removeItem('streamhug_access_token');
      localStorage.removeItem('streamhug_refresh_token');
    }
  }
});
