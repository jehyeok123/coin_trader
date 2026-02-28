import { Routes, Route } from 'react-router-dom'
import { PriceProvider } from './contexts/PriceContext'
import Layout from './components/Layout/Layout'
import Dashboard from './components/Dashboard/Dashboard'
import TradeHistory from './components/Trading/TradeHistory'
import CoinChart from './components/Charts/CoinChart'
import RuleEditor from './components/Rules/RuleEditor'
import SignalFeed from './components/Signals/SignalFeed'
import SettingsPage from './components/Settings/Settings'

function App() {
  return (
    <PriceProvider>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<Dashboard />} />
          <Route path="chart" element={<CoinChart />} />
          <Route path="chart/:symbol" element={<CoinChart />} />
          <Route path="trades" element={<TradeHistory />} />
          <Route path="rules" element={<RuleEditor />} />
          <Route path="signals" element={<SignalFeed />} />
          <Route path="settings" element={<SettingsPage />} />
        </Route>
      </Routes>
    </PriceProvider>
  )
}

export default App
