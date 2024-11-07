export interface TradingSignal {
  id?: number;
  symbol: string;
  action: 'BUY' | 'SELL';
  price: number;
  timestamp: string;
  processed: boolean;
  strategy: string;
}

export interface SignalResponse {
  success: boolean;
  message: string;
  data?: TradingSignal[];
}