<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue';
import axios from 'axios';
import { ElMessage } from 'element-plus';

const logs = ref<string[]>([]);
const loading = ref(false);
let pollingInterval: number | null = null;

const fetchLogs = async () => {
  loading.value = true;
  try {
    const response = await axios.get('http://127.0.0.1/api/logs');
    logs.value = response.data.logs;
  } catch (error) {
    ElMessage.error('获取日志失败');
    console.error('获取日志错误:', error);
  } finally {
    loading.value = false;
  }
};

onMounted(() => {
  fetchLogs();
  // 每5秒更新一次日志
  pollingInterval = setInterval(fetchLogs, 5000);
});

onUnmounted(() => {
  if (pollingInterval) {
    clearInterval(pollingInterval);
  }
});
</script>

<template>
  <div class="trading-log">
    <h2 class="log-title">交易日志</h2>
    <div class="log-container" v-loading="loading">
      <div v-for="(log, index) in logs" :key="index" class="log-entry">
        {{ log }}
      </div>
    </div>
  </div>
</template>

<style scoped>
.trading-log {
  padding: 20px;
  margin-top: 20px;
}

.log-title {
  text-align: center;
}

.log-container {
  height: 300px;
  overflow-y: auto;
  background-color: #1e1e1e;
  color: #fff;
  padding: 10px;
  border-radius: 4px;
  font-family: monospace;
  text-align: left;
}

.log-entry {
  padding: 2px 0;
  border-bottom: 1px solid #333;
  white-space: pre-wrap;
  word-break: break-all;
  text-align: left;
  padding-left: 10px;
}
</style> 