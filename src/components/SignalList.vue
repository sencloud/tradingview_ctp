<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { TradingSignal } from '../types/signal';
import axios from 'axios';
import { ElMessage } from 'element-plus';

const signals = ref<TradingSignal[]>([]);
const loading = ref(false);

const fetchSignals = async () => {
  loading.value = true;
  try {
    const response = await axios.get('http://127.0.0.1:5000/api/signals');
    signals.value = response.data.data;
  } catch (error) {
    ElMessage.error('获取信号数据失败');
    console.error('获取信号错误:', error);
  } finally {
    loading.value = false;
  }
};

onMounted(() => {
  fetchSignals();
});
</script>

<template>
  <div class="signal-list">
    <h2>交易信号列表</h2>
    <el-table v-loading="loading" :data="signals" style="width: 100%">
      <el-table-column prop="timestamp" label="时间" width="180">
        <template #default="{ row }">
          {{ new Date(new Date(row.timestamp).getTime() + 8 * 60 * 60 * 1000).toLocaleString() }}
        </template>
      </el-table-column>
      <el-table-column prop="symbol" label="交易品种" width="120" />
      <el-table-column prop="action" label="操作" width="100">
        <template #default="{ row }">
          <el-tag :type="row.action === 'BUY' ? 'success' : 'danger'">
            {{ row.action === 'BUY' ? '买入' : '卖出' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="price" label="价格" width="120" />
      <el-table-column prop="strategy" label="策略" width="150" />
      <el-table-column prop="processed" label="状态" width="120">
        <template #default="{ row }">
          <el-tag :type="row.processed ? 'success' : 'warning'">
            {{ row.processed ? '已处理' : '待处理' }}
          </el-tag>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>

<style scoped>
.signal-list {
  padding: 20px;
}
</style>