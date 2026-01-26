<template>
  <div class="menu-item" :class="{ open: isOpen }">
    <!-- 无子菜单的顶级项 -->
    <router-link
      v-if="!menu.children && menu.path"
      :to="menu.path"
      class="flex items-center gap-3 px-6 py-4 cursor-pointer hover:bg-white/5 transition-all no-expand"
      :class="{ 'active-item': currentPath === menu.path }"
    >
      <i :class="['fas', menu.icon, 'w-5 text-center opacity-80']"></i>
      <span class="font-medium">{{ menu.label }}</span>
    </router-link>
    
    <!-- 有子菜单的展开项 -->
    <template v-else>
      <div
        class="flex items-center justify-between px-6 py-4 cursor-pointer hover:bg-white/5 transition-all"
        @click="$emit('toggle', menu.id)"
      >
        <div class="flex items-center gap-3">
          <i :class="['fas', menu.icon, 'w-5 text-center opacity-80']"></i>
          <span class="font-medium">{{ menu.label }}</span>
        </div>
        <i class="fas fa-chevron-down text-xs chevron transition-transform opacity-50"></i>
      </div>
      <div class="menu-content flex flex-col">
        <router-link
          v-for="child in menu.children"
          :key="child.path"
          :to="child.path"
          class="sub-item pl-14 pr-6 py-3 text-sm text-left opacity-70 hover:opacity-100 transition-all"
          :class="{ active: currentPath === child.path }"
        >
          {{ child.label }}
        </router-link>
      </div>
    </template>
  </div>
</template>

<script setup>
defineProps({
  menu: {
    type: Object,
    required: true
  },
  isOpen: {
    type: Boolean,
    default: false
  },
  currentPath: {
    type: String,
    default: ''
  }
})

defineEmits(['toggle'])
</script>

<style scoped>
.menu-content {
  max-height: 0;
  overflow: hidden;
  opacity: 0;
  transform: translateY(-4px);
  transition:
    max-height 0.28s cubic-bezier(0.25, 0.8, 0.25, 1),
    opacity 0.22s ease-out,
    transform 0.28s ease-out;
  background: rgba(0, 0, 0, 0.15);
}

.menu-item.open .menu-content {
  max-height: 500px;
  opacity: 1;
  transform: translateY(0);
}

.menu-item.open .chevron {
  transform: rotate(180deg);
}

.sub-item {
  text-decoration: none;
  color: inherit;
  display: block;
  transform: translateY(2px);
  transition:
    color 0.2s ease-out,
    background-color 0.2s ease-out,
    opacity 0.2s ease-out,
    transform 0.24s ease-out;
}

.menu-item.open .sub-item {
  transform: translateY(0);
}

.sub-item.active {
  background-color: white;
  color: #007857;
  font-weight: 600;
  opacity: 1;
}

.no-expand {
  text-decoration: none;
  color: inherit;
}

.active-item {
  background-color: rgba(255, 255, 255, 0.15);
}
</style>
