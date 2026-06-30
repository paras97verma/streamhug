<template>
  <div class="app-container">
    <!-- Neumorphic Welcome Screen -->
    <transition name="fade">
      <div v-if="!userStore.isAuthorized" class="welcome-overlay">
        <!-- Ambient background orbs -->
        <div class="bg-orb orb-1"></div>
        <div class="bg-orb orb-2"></div>
        <div class="bg-orb orb-3"></div>

        <div class="welcome-panel">
          <!-- Logo -->
          <div class="welcome-logo">
            <span class="logo-icon">◈</span>
            <span class="logo-text">{{ userStore.appName }}</span>
          </div>
          <p class="logo-tagline">Your private streaming universe</p>

          <!-- Auth section with tabbed interface -->
          <div class="auth-section">
            <div class="auth-tabs neu-inset">
              <button 
                type="button" 
                :class="['tab-btn', { active: authMode === 'signin' }]" 
                @click="setAuthMode('signin')"
              >
                Sign In
              </button>
              <button 
                type="button" 
                :class="['tab-btn', { active: authMode === 'signup' }]" 
                @click="setAuthMode('signup')"
              >
                Sign Up
              </button>
            </div>

            <h1 class="welcome-heading">
              {{ authMode === 'signin' ? 'Welcome Back' : 'Create Account' }}
            </h1>

            <form @submit.prevent="handleSubmit" class="auth-form">
              <!-- Error Banner -->
              <transition name="fade">
                <div v-if="errorMessage" class="error-banner">
                  <span class="error-icon">⚠️</span>
                  <span class="error-text">{{ errorMessage }}</span>
                </div>
              </transition>

              <!-- Name Input (Sign Up Only) -->
              <div v-if="authMode === 'signup'" class="input-field">
                <label class="input-label">Name</label>
                <div class="input-wrapper neu-inset">
                  <input 
                    type="text" 
                    v-model="authForm.name" 
                    placeholder="Your display name" 
                    class="auth-input"
                    maxlength="50"
                    required
                    autocomplete="name"
                  />
                </div>
              </div>

              <!-- Email Input -->
              <div class="input-field">
                <label class="input-label">Email Address</label>
                <div class="input-wrapper neu-inset">
                  <input 
                    type="email" 
                    v-model="authForm.email" 
                    placeholder="you@example.com" 
                    class="auth-input"
                    required
                    autocomplete="email"
                  />
                </div>
              </div>

              <!-- Password Input -->
              <div class="input-field">
                <label class="input-label">Password</label>
                <div class="input-wrapper neu-inset">
                  <input 
                    type="password" 
                    v-model="authForm.password" 
                    placeholder="••••••••" 
                    class="auth-input"
                    minlength="8"
                    required
                    autocomplete="current-password"
                  />
                </div>
              </div>

              <!-- Confirm Password Input (Sign Up Only) -->
              <div v-if="authMode === 'signup'" class="input-field">
                <label class="input-label">Confirm Password</label>
                <div class="input-wrapper neu-inset">
                  <input 
                    type="password" 
                    v-model="authForm.confirmPassword" 
                    placeholder="••••••••" 
                    class="auth-input"
                    minlength="8"
                    required
                    autocomplete="new-password"
                  />
                </div>
              </div>

              <!-- Submit Button -->
              <button type="submit" class="submit-btn neu-btn-accent" :disabled="isLoading">
                <span v-if="isLoading">{{ authMode === 'signin' ? 'Signing In...' : 'Registering...' }}</span>
                <span v-else>{{ authMode === 'signin' ? 'Sign In →' : 'Sign Up →' }}</span>
              </button>
            </form>
          </div>
        </div>
      </div>
    </transition>

    <!-- Main App -->
    <template v-if="userStore.isAuthorized">
      <Navbar v-if="requiresLayout" />
      <main :class="{ 'with-navbar': requiresLayout }">
        <router-view v-slot="{ Component }">
          <transition name="fade" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </main>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, reactive } from 'vue';
import { useRoute } from 'vue-router';
import Navbar from '@/components/layout/Navbar.vue';
import { useLibraryStore } from '@/stores/libraryStore';
import { useUserStore } from '@/stores/userStore';

const route = useRoute();
const libraryStore = useLibraryStore();
const userStore = useUserStore();

const authMode = ref<'signin' | 'signup'>('signin');
const isLoading = ref(false);
const errorMessage = ref('');

const authForm = reactive({
  name: '',
  email: '',
  password: '',
  confirmPassword: '',
});

const requiresLayout = computed(() => route.meta.requiresLayout !== false);

const setAuthMode = (mode: 'signin' | 'signup') => {
  authMode.value = mode;
  errorMessage.value = '';
};

const handleSubmit = async () => {
  errorMessage.value = '';
  isLoading.value = true;

  try {
    if (authMode.value === 'signup') {
      if (authForm.password !== authForm.confirmPassword) {
        throw new Error('Passwords do not match');
      }
      await userStore.register(authForm.name, authForm.email, authForm.password);
    } else {
      await userStore.login(authForm.email, authForm.password);
    }
  } catch (err: any) {
    errorMessage.value = err.response?.data?.detail || err.message || 'An error occurred. Please try again.';
  } finally {
    isLoading.value = false;
  }
};

onMounted(async () => {
  libraryStore.initSSE();
  await userStore.checkAuth();
});
</script>

<style scoped>
.app-container {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  background-color: var(--neu-base);
  color: var(--text-primary);
}

main { flex: 1; }

/* ── Welcome Overlay ─────────────────────────────────────────────────── */
.welcome-overlay {
  position: fixed;
  inset: 0;
  background: var(--neu-base);
  z-index: 999;
  display: flex;
  justify-content: center;
  align-items: center;
  padding: 20px;
  overflow: hidden;
}

/* Ambient background orbs */
.bg-orb {
  position: absolute;
  border-radius: 50%;
  filter: blur(80px);
  pointer-events: none;
  opacity: 0.12;
}
.orb-1 {
  width: 500px; height: 500px;
  background: radial-gradient(circle, #7c3aed, transparent 70%);
  top: -150px; left: -100px;
  animation: floatOrb 8s ease-in-out infinite alternate;
}
.orb-2 {
  width: 400px; height: 400px;
  background: radial-gradient(circle, #4f46e5, transparent 70%);
  bottom: -100px; right: -80px;
  animation: floatOrb 10s ease-in-out infinite alternate-reverse;
}
.orb-3 {
  width: 300px; height: 300px;
  background: radial-gradient(circle, #7c3aed, transparent 70%);
  top: 50%; left: 50%; transform: translate(-50%, -50%);
  animation: floatOrb 6s ease-in-out infinite alternate;
}

@keyframes floatOrb {
  0%   { transform: translate(0, 0); }
  100% { transform: translate(30px, 20px); }
}

.welcome-panel {
  width: 100%;
  max-width: 420px;
  background: var(--neu-base);
  box-shadow: var(--shadow-outset);
  border: 1px solid var(--neu-border);
  border-radius: var(--radius-xl);
  padding: 40px 32px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 1.2rem;
  position: relative;
  z-index: 1;
  animation: panelIn 0.5s cubic-bezier(0.34, 1.56, 0.64, 1);
}

@keyframes panelIn {
  from { opacity: 0; transform: translateY(30px) scale(0.96); }
  to   { opacity: 1; transform: translateY(0) scale(1); }
}

/* Logo */
.welcome-logo {
  display: flex;
  align-items: center;
  gap: 10px;
}
.logo-icon {
  font-size: 2rem;
  color: var(--accent-light);
  filter: drop-shadow(0 0 8px var(--accent-glow));
  animation: glowPulse 3s ease-in-out infinite;
}
.logo-text {
  font-size: 1.9rem;
  font-weight: 800;
  letter-spacing: 1px;
  background: linear-gradient(135deg, #a78bfa 0%, #7c3aed 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}
.logo-tagline {
  font-size: 0.82rem;
  color: var(--text-muted);
  letter-spacing: 0.5px;
  margin-top: -12px;
  margin-bottom: 0.5rem;
}

/* Auth section */
.auth-section {
  width: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 1rem;
}

.auth-tabs {
  display: flex;
  width: 100%;
  padding: 4px;
  border-radius: var(--radius-md);
  margin-bottom: 0.2rem;
}

.tab-btn {
  flex: 1;
  padding: 10px;
  border-radius: var(--radius-sm);
  font-size: 0.9rem;
  font-weight: 600;
  color: var(--text-secondary);
  transition: all var(--transition-fast);
}

.tab-btn.active {
  background: var(--neu-base);
  box-shadow: var(--shadow-btn);
  color: var(--accent-light);
}

.welcome-heading {
  font-size: 1.5rem;
  font-weight: 800;
  text-align: center;
  color: var(--text-primary);
  margin-bottom: 0.2rem;
  letter-spacing: -0.5px;
}

.auth-form {
  display: flex;
  flex-direction: column;
  gap: 0.8rem;
  width: 100%;
}

.error-banner {
  display: flex;
  align-items: center;
  gap: 10px;
  background: rgba(239, 68, 68, 0.08);
  border: 1px solid rgba(239, 68, 68, 0.2);
  padding: 10px 14px;
  border-radius: var(--radius-sm);
  color: #f87171;
  font-size: 0.82rem;
  font-weight: 500;
  line-height: 1.4;
}

.input-field {
  display: flex;
  flex-direction: column;
  gap: 4px;
  width: 100%;
}

.input-label {
  font-size: 0.78rem;
  font-weight: 600;
  color: var(--text-secondary);
  padding-left: 4px;
}

.input-wrapper {
  border-radius: var(--radius-md);
  padding: 2px;
}

.auth-input {
  width: 100%;
  padding: 12px 14px;
  background: transparent;
  border: none;
  color: var(--text-primary);
  font-size: 0.9rem;
  font-family: var(--font-family);
  font-weight: 500;
  outline: none;
  letter-spacing: 0.5px;
}

.auth-input::placeholder {
  color: var(--text-muted);
}

.submit-btn {
  padding: 14px;
  border-radius: var(--radius-md);
  font-size: 0.95rem;
  font-weight: 700;
  width: 100%;
  letter-spacing: 0.5px;
  transition: all var(--transition-fast);
  margin-top: 0.5rem;
}

.submit-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

/* Page transitions */
.fade-enter-active, .fade-leave-active { transition: opacity 0.3s ease; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
</style>
