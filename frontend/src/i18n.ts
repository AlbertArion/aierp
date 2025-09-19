import { createI18n } from 'vue-i18n'

const messages = {
  zh: {
    brand: 'AI ERP',
    menu: { integration: '数据集成', predict: '指标预测', orders: '订单协同', rules: '流程规则' },
    actions: { search: '搜索', update: '提交修改', analyze: '解析' }
  },
  en: {
    brand: 'AI ERP',
    menu: { integration: 'Integration', predict: 'Prediction', orders: 'Orders', rules: 'Rules' },
    actions: { search: 'Search', update: 'Update', analyze: 'Analyze' }
  }
}

export default createI18n({
  legacy: false,
  locale: 'zh',
  fallbackLocale: 'en',
  messages
})


