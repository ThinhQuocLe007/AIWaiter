<template>
  <div class="skeleton-card">
    <div class="skeleton-image shimmer"></div>
    <div class="skeleton-body">
      <div class="skeleton-line shimmer" style="width: 70%"></div>
      <div class="skeleton-line shimmer" style="width: 90%"></div>
      <div class="skeleton-footer">
        <div class="skeleton-line shimmer" style="width: 40%; height: 1.25rem"></div>
        <div class="skeleton-pill shimmer"></div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts"></script>

<style scoped>
.skeleton-card {
  background: var(--color-surface);
  border-radius: var(--radius-md);
  overflow: hidden;
  height: 280px;
  display: flex;
  flex-direction: column;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}

.skeleton-image {
  width: 100%;
  height: 140px;
}

.skeleton-body {
  padding: 0.75rem;
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.skeleton-line {
  height: 0.875rem;
  border-radius: var(--radius-sm);
}

.skeleton-footer {
  margin-top: auto;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.skeleton-pill {
  width: 44px;
  height: 44px;
  border-radius: var(--radius-full);
}

.shimmer {
  background: linear-gradient(
    90deg,
    #ececec 25%,
    #f5f5f5 50%,
    #ececec 75%
  );
  background-size: 200% 100%;
  animation: shimmer 1.4s ease-in-out infinite;
}

@keyframes shimmer {
  0% {
    background-position: 200% 0;
  }
  100% {
    background-position: -200% 0;
  }
}
</style>
