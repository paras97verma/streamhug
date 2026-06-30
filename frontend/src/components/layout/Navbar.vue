<template>
  <nav :class="['navbar', { 'is-scrolled': isScrolled }]">
    <div class="navbar-content">
      <div class="left-section">
        <router-link to="/" class="logo">
          <span class="logo-gem">◈</span>
          {{ userStore.appName }}
        </router-link>
        <ul class="nav-links">
          <li><router-link to="/" class="nav-link">Home</router-link></li>
          <li><a href="#movies" class="nav-link" @click.prevent="scrollTo('movies')">Movies</a></li>
          <li><a href="#tvshows" class="nav-link" @click.prevent="scrollTo('tvshows')">TV Shows</a></li>
          <li><a href="#anime" class="nav-link" @click.prevent="scrollTo('anime')">Anime</a></li>
        </ul>
      </div>
      
      <div class="right-section">
        <SearchBar />
        <div class="avatar-btn" @click="handleLogout" title="Click to change profile">
          <div class="avatar">{{ userStore.avatarInitial }}</div>
        </div>
      </div>
    </div>
  </nav>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue';
import SearchBar from './SearchBar.vue';
import { useUserStore } from '@/stores/userStore';

const isScrolled = ref(false);
const userStore = useUserStore();

const handleScroll = () => { isScrolled.value = window.scrollY > 20; };

const scrollTo = (id: string) => {
  const el = document.getElementById(id);
  if (el) el.scrollIntoView({ behavior: 'smooth' });
};

const handleLogout = () => {
  if (confirm('Log out of StreamHug?')) {
    userStore.logout();
    window.location.reload();
  }
};

onMounted(() => { window.addEventListener('scroll', handleScroll); });
onUnmounted(() => { window.removeEventListener('scroll', handleScroll); });
</script>

<style scoped>
.navbar {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 70px;
  z-index: 100;
  background: transparent;
  transition: background var(--transition-normal), backdrop-filter var(--transition-normal);
}

.navbar.is-scrolled {
  background: rgba(12, 15, 23, 0.82);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border-bottom: 1px solid rgba(255, 255, 255, 0.04);
  box-shadow: 0 4px 24px rgba(0,0,0,0.3);
}

.navbar-content {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 100%;
  padding: 0 5%;
}

.left-section, .right-section { display: flex; align-items: center; gap: 20px; }

/* Logo */
.logo {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 1.35rem;
  font-weight: 800;
  letter-spacing: 0.5px;
  background: linear-gradient(135deg, #a78bfa 0%, #7c3aed 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.logo-gem {
  font-size: 1.4rem;
  -webkit-text-fill-color: #a78bfa;
  filter: drop-shadow(0 0 6px rgba(124, 58, 237, 0.5));
}

/* Nav links */
.nav-links { display: flex; gap: 4px; margin-left: 12px; }

.nav-link {
  color: var(--text-secondary);
  font-size: 0.875rem;
  font-weight: 500;
  padding: 6px 14px;
  border-radius: var(--radius-pill);
  transition: background var(--transition-fast), color var(--transition-fast);
  text-decoration: none;
}

.nav-link:hover { color: var(--text-primary); background: rgba(255,255,255,0.06); }

.nav-link.router-link-active {
  color: var(--accent-light);
  background: var(--accent-subtle);
}

/* Avatar */
.avatar-btn { cursor: pointer; }

.avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: linear-gradient(135deg, var(--accent) 0%, #5b21b6 100%);
  box-shadow: 0 0 0 2px var(--neu-base), 0 0 0 3.5px rgba(124,58,237,0.4);
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  font-size: 0.85rem;
  color: white;
  transition: box-shadow var(--transition-fast), transform var(--transition-fast);
}

.avatar-btn:hover .avatar {
  box-shadow: 0 0 0 2px var(--neu-base), 0 0 0 3.5px rgba(124,58,237,0.7);
  transform: scale(1.05);
}

@media (max-width: 768px) { .nav-links { display: none; } }
</style>
