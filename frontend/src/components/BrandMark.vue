<script setup lang="ts">
withDefaults(
  defineProps<{
    size?: number
  }>(),
  {
    size: 36,
  },
)
</script>

<template>
  <span
    class="brand-mark"
    :style="{ width: `${size}px`, height: `${size}px` }"
    aria-hidden="true"
  >
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7">
      <path
        d="M12 3.25 19 6v5.1c0 4.5-2.9 7.5-7 9.15-4.1-1.65-7-4.65-7-9.15V6l7-2.75Z"
        stroke-linejoin="round"
      />
      <path d="m9.4 11.8-2.1 2.1 2.1 2.1M14.6 11.8l2.1 2.1-2.1 2.1" stroke-linecap="round" stroke-linejoin="round" />
    </svg>
  </span>
</template>

<style scoped>
.brand-mark {
  display: inline-flex;
  flex: none;
  align-items: center;
  justify-content: center;
  color: #fff;
  background: linear-gradient(135deg, #6366f1 0%, #4338ca 55%, #312e81 100%);
  border: 1px solid rgb(255 255 255 / 18%);
  border-radius: 11px;
  box-shadow: 0 8px 20px rgb(49 46 129 / 38%);
}

.brand-mark svg {
  width: 62%;
  height: 62%;
}
</style>
