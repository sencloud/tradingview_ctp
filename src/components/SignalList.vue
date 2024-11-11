<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { TradingSignal } from '../types/signal';
import axios from 'axios';
import { ElMessage } from 'element-plus';
import TradingLog from './TradingLog.vue';

const signals = ref<TradingSignal[]>([]);
const loading = ref(false);
const accountInfo = ref({
  balance: 0,
  equity: 0,
  profit: 0,
});

const fetchSignals = async () => {
  loading.value = true;
  try {
    const response = await axios.get('http://127.0.0.1/api/signals');
    signals.value = response.data.data;
  } catch (error) {
    ElMessage.error('获取信号数据失败');
    console.error('获取信号错误:', error);
  } finally {
    loading.value = false;
  }
};

const fetchAccountInfo = async () => {
  try {
    const response = await axios.get('http://127.0.0.1/api/account');
    accountInfo.value = response.data.data;
  } catch (error) {
    ElMessage.error('获取账户数据失败');
    console.error('获取账户数据错误:', error);
  }
};

onMounted(() => {
  fetchSignals();
  fetchAccountInfo();
});
</script>

<template>
  <div class="signal-list">
    <div class="account-info">
      <el-row :gutter="20">
        <el-col :span="8">
          <el-card shadow="hover">
            <template #header>账户余额</template>
            <span class="account-value">¥{{ accountInfo.balance.toFixed(2) }}</span>
          </el-card>
        </el-col>
        <el-col :span="8">
          <el-card shadow="hover">
            <template #header>账户净值</template>
            <span class="account-value">¥{{ accountInfo.equity.toFixed(2) }}</span>
          </el-card>
        </el-col>
        <el-col :span="8">
          <el-card shadow="hover">
            <template #header>浮动盈亏</template>
            <span class="account-value" :class="{ 'profit': accountInfo.profit > 0, 'loss': accountInfo.profit < 0 }">
              ¥{{ accountInfo.profit.toFixed(2) }}
            </span>
          </el-card>
        </el-col>
      </el-row>
    </div>
    
    <h2>交易信号列表</h2>
    <el-table v-loading="loading" :data="signals" style="width: 100%">
      <el-table-column prop="timestamp" label="时间" min-width="180" align="center">
        <template #default="{ row }">
          {{ new Date(new Date(row.timestamp).getTime() + 8 * 60 * 60 * 1000).toLocaleString() }}
        </template>
      </el-table-column>
      <el-table-column prop="symbol" label="交易品种" min-width="120" align="center" />
      <el-table-column prop="action" label="操作" min-width="100" align="center">
        <template #default="{ row }">
          <el-tag :type="row.action === 'BUY' ? 'success' : 'danger'">
            {{ row.action === 'BUY' ? '买入' : '卖出' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="price" label="价格" min-width="120" align="center" />
      <el-table-column prop="strategy" label="策略" min-width="150" align="center" />
      <el-table-column prop="processed" label="状态" min-width="120" align="center">
        <template #default="{ row }">
          <el-tag :type="row.processed ? 'success' : 'warning'">
            {{ row.processed ? '已处理' : '待处理' }}
          </el-tag>
        </template>
      </el-table-column>
    </el-table>
    
    <TradingLog />
  </div>
</template>

<style scoped>
.signal-list {
  padding: 20px;
  text-align: center;
}

h2 {
  text-align: center;
}

.account-info {
  margin-bottom: 20px;
}

.account-value {
  font-size: 24px;
  font-weight: bold;
}

.profit {
  color: #67C23A;
}

.loss {
  color: #F56C6C;
}
</style>