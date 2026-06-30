<template>
  <div class="skeleton-container" :style="{ width, height, borderRadius: radius }">
    <div class="skeleton"></div>
  </div>
</template>

<script setup lang="ts">
withDefaults(defineProps<{
  width?: string;
  height?: string;
  radius?: string;
}>(), {
  width: '100%',
  height: '100%',
  radius: '4px'
});
</script>

<style scoped>
.skeleton-container {
  overflow: hidden;
  position: relative;
}

.skeleton {
  width: 100%;
  height: 100%;
}
</style>
