<script setup lang="ts">
import SignalList from './components/SignalList.vue'
</script>

<template>
  <el-container>
    <el-header>
      <h2 class="header-title">交易信号监控系统</h2>
    </el-header>
    <el-main>
      <SignalList />
    </el-main>
  </el-container>
</template>

<style>
.el-header {
  background-color: #545c64;
  color: white;
  text-align: center;
  line-height: 60px;
}

.header-title {
  font-size: 1.5rem;
  margin: 0;
  font-weight: 500;
}

.el-main {
  background-color: #f0f2f5;
  min-height: calc(100vh - 60px);
}
</style>