<template>
  <div class="not-found">
    <h1>404</h1>
    <p>Lost your way?</p>
    <router-link to="/" class="home-btn">Go Home</router-link>
  </div>
</template>

<style scoped>
.not-found {
  height: 100vh;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  background: var(--bg-color);
}
h1 {
  font-size: 6rem;
  margin-bottom: 10px;
  color: var(--brand-color);
}
p {
  font-size: 1.5rem;
  margin-bottom: 30px;
  color: #a3a3a3;
}
.home-btn {
  background-color: white;
  color: black;
  padding: 12px 30px;
  border-radius: 4px;
  font-weight: 700;
  text-decoration: none;
}
</style>
