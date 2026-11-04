/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useState, useEffect } from 'react';
import {
  Utensils,
  Bot,
  Clock,
  ShieldCheck,
  Terminal,
  Settings,
  Play,
  CheckCircle2,
  AlertCircle,
  Calendar,
  Cookie,
  Bell,
  ExternalLink,
  RefreshCw,
  Check,
  ArrowRight
} from 'lucide-react';
import MenuPopularityChart from './components/MenuPopularityChart';

export default function App() {
  const [activeTab, setActiveTab] = useState<'overview' | 'schedule' | 'session' | 'logs' | 'settings'>('overview');
  const [statusData, setStatusData] = useState<any>(null);
  const [meals, setMeals] = useState<any[]>([]);
  const [logs, setLogs] = useState<any[]>([]);
  const [config, setConfig] = useState<any>({});
  const [loading, setLoading] = useState(false);
  const [notificationMsg, setNotificationMsg] = useState('');
  
  // Session cookie inputs
  const [cookieInput, setCookieInput] = useState('');

  const fetchData = async () => {
    try {
      const [statusRes, mealsRes, logsRes, configRes] = await Promise.all([
        fetch('/api/status').then(r => r.json()),
        fetch('/api/meals/upcoming').then(r => r.json()),
        fetch('/api/logs').then(r => r.json()),
        fetch('/api/config').then(r => r.json()),
      ]);
      setStatusData(statusRes);
      setMeals(mealsRes.items || mealsRes);
      setLogs(logsRes);
      setConfig(configRes);
    } catch (e) {
      console.error("Failed to fetch dashboard data", e);
    }
  };

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 5000);
    return () => clearInterval(interval);
  }, []);

  const handleRunAgent = async () => {
    setLoading(true);
    setNotificationMsg("Triggering Python Playwright agent...");
    try {
      const res = await fetch('/api/run-agent', { method: 'POST' });
      const data = await res.json();
      if (data.success) {
        setNotificationMsg("Agent executed successfully! Check logs for details.");
      } else {
        setNotificationMsg("Agent execution error: " + data.error);
      }
    } catch (e: any) {
      setNotificationMsg("Error triggering agent: " + e.message);
    }
    setLoading(false);
    setTimeout(() => fetchData(), 2000);
  };

  const handleSaveConfig = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const res = await fetch('/api/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config)
      });
      const data = await res.json();
      if (data.success) {
        setNotificationMsg("Configuration saved successfully.");
        setConfig(data.config);
      }
    } catch (e: any) {
      setNotificationMsg("Failed to save config: " + e.message);
    }
  };

  const handleSaveSession = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      let parsedCookies;
      try {
        parsedCookies = JSON.parse(cookieInput);
      } catch {
        // If not JSON, send raw or simple wrap
        parsedCookies = [{ name: "session", value: cookieInput, domain: "portal.spacebasic.com", path: "/" }];
      }

      const res = await fetch('/api/session', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ cookies: parsedCookies })
      });
      const data = await res.json();
      if (data.success) {
        setNotificationMsg("Session state updated successfully! Playwright agent will use your logged-in session.");
        setCookieInput("");
        fetchData();
      }
    } catch (e: any) {
      setNotificationMsg("Failed to update session: " + e.message);
    }
  };

  const handleSendWhatsApp = async () => {
    setLoading(true);
    setNotificationMsg("Sending WhatsApp trial message to 9705862237...");
    try {
      const res = await fetch('/api/send-whatsapp', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ phone: config.whatsapp_number || "9705862237", message: "Trial: SpaceBasic Meal Booking Agent connected successfully for 9705862237!" })
      });
      const data = await res.json();
      if (data.success) {
        setNotificationMsg("WhatsApp trial message sent successfully to +919705862237!");
        fetchData();
      } else {
        setNotificationMsg("Failed to send WhatsApp message.");
      }
    } catch (e: any) {
      setNotificationMsg("Error sending WhatsApp trial: " + e.message);
    }
    setLoading(false);
  };

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 font-sans">
      {/* Top Bar Contract (3 zones) */}
      <header className="sticky top-0 z-30 flex items-center justify-between gap-8 px-8 py-4 bg-white border-b border-slate-200">
        {/* Zone 1: Brand Wordmark */}
        <div className="flex items-center gap-3 shrink-0">
          <div className="flex items-center justify-center w-10 h-10 bg-indigo-600 text-white rounded-xl shadow-sm">
            <Utensils className="w-5 h-5" />
          </div>
          <div>
            <h1 className="text-lg font-bold tracking-tight text-slate-900">SpaceBasic Agent</h1>
            <p className="text-xs text-slate-500 font-mono">Python + Playwright Session Engine</p>
          </div>
        </div>

        {/* Zone 2: Navigation Links */}
        <nav className="hidden md:flex items-center gap-6 text-sm font-medium text-slate-600">
          <button
            onClick={() => setActiveTab('overview')}
            className={`transition-colors whitespace-nowrap shrink-0 pb-1 border-b-2 ${activeTab === 'overview' ? 'border-indigo-600 text-slate-900 font-semibold' : 'border-transparent hover:text-slate-900'}`}
          >
            Overview
          </button>
          <button
            onClick={() => setActiveTab('schedule')}
            className={`transition-colors whitespace-nowrap shrink-0 pb-1 border-b-2 ${activeTab === 'schedule' ? 'border-indigo-600 text-slate-900 font-semibold' : 'border-transparent hover:text-slate-900'}`}
          >
            Meal Schedule
          </button>
          <button
            onClick={() => setActiveTab('session')}
            className={`transition-colors whitespace-nowrap shrink-0 pb-1 border-b-2 ${activeTab === 'session' ? 'border-indigo-600 text-slate-900 font-semibold' : 'border-transparent hover:text-slate-900'}`}
          >
            Session & Cookies
          </button>
          <button
            onClick={() => setActiveTab('logs')}
            className={`transition-colors whitespace-nowrap shrink-0 pb-1 border-b-2 ${activeTab === 'logs' ? 'border-indigo-600 text-slate-900 font-semibold' : 'border-transparent hover:text-slate-900'}`}
          >
            Live Logs
          </button>
          <button
            onClick={() => setActiveTab('settings')}
            className={`transition-colors whitespace-nowrap shrink-0 pb-1 border-b-2 ${activeTab === 'settings' ? 'border-indigo-600 text-slate-900 font-semibold' : 'border-transparent hover:text-slate-900'}`}
          >
            Settings
          </button>
        </nav>

        {/* Zone 3: Primary Action */}
        <div className="flex items-center gap-3 shrink-0">
          <button
            onClick={handleSendWhatsApp}
            disabled={loading}
            className="flex items-center gap-2 px-3 py-2 text-xs font-semibold text-emerald-700 bg-emerald-50 border border-emerald-200 rounded-lg hover:bg-emerald-100 transition-colors shadow-xs whitespace-nowrap cursor-pointer"
          >
            WhatsApp Trial (9705862237)
          </button>
          <button
            onClick={handleRunAgent}
            disabled={loading}
            className="flex items-center gap-2 px-4 py-2 text-xs font-semibold text-white bg-indigo-600 rounded-lg hover:bg-indigo-700 transition-colors shadow-sm disabled:opacity-50 whitespace-nowrap cursor-pointer"
          >
            {loading ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4 fill-white" />}
            Run Agent Now
          </button>
        </div>
      </header>

      {/* Notification Banner */}
      {notificationMsg && (
        <div className="bg-indigo-50 border-b border-indigo-100 px-8 py-3 flex items-center justify-between text-sm text-indigo-900">
          <div className="flex items-center gap-2">
            <Bell className="w-4 h-4 text-indigo-600" />
            <span>{notificationMsg}</span>
          </div>
          <button onClick={() => setNotificationMsg('')} className="text-indigo-600 hover:text-indigo-800 font-medium text-xs">Dismiss</button>
        </div>
      )}

      {/* Main Content Container */}
      <main className="max-w-7xl mx-auto px-8 py-8">
        {activeTab === 'overview' && (
          <div className="space-y-8">
            {/* Status Banner */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
              <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-xs">
                <div className="flex items-center justify-between text-slate-500 text-xs font-medium uppercase tracking-wider mb-2">
                  <span>Agent Status</span>
                  <div className="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-pulse" />
                </div>
                <div className="text-2xl font-bold text-slate-900 capitalize">
                  {statusData?.status || 'Active'}
                </div>
                <p className="text-xs text-slate-500 mt-1">Python Playwright scheduler running</p>
              </div>

              <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-xs">
                <div className="flex items-center justify-between text-slate-500 text-xs font-medium uppercase tracking-wider mb-2">
                  <span>Active Session</span>
                  <Cookie className="w-4 h-4 text-indigo-600" />
                </div>
                <div className="text-2xl font-bold text-slate-900">
                  {statusData?.sessionExists ? 'Connected' : 'Needs Session'}
                </div>
                <p className="text-xs text-slate-500 mt-1">portal.spacebasic.com/module</p>
              </div>

              <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-xs">
                <div className="flex items-center justify-between text-slate-500 text-xs font-medium uppercase tracking-wider mb-2">
                  <span>Next Run</span>
                  <Clock className="w-4 h-4 text-indigo-600" />
                </div>
                <div className="text-xl font-bold text-slate-900">
                  {statusData?.nextRun || 'Tomorrow 08:30 AM'}
                </div>
                <p className="text-xs text-slate-500 mt-1">Before daily cutoff time</p>
              </div>

              <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-xs">
                <div className="flex items-center justify-between text-slate-500 text-xs font-medium uppercase tracking-wider mb-2">
                  <span>Success Rate</span>
                  <ShieldCheck className="w-4 h-4 text-emerald-600" />
                </div>
                <div className="text-2xl font-bold text-slate-900">100%</div>
                <p className="text-xs text-slate-500 mt-1">All bookings confirmed</p>
              </div>
            </div>

            {/* Rule Hierarchy & Portal Connection Card */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
              <div className="lg:col-span-2 bg-white p-8 rounded-2xl border border-slate-200 shadow-xs">
                <div className="flex items-center justify-between mb-6">
                  <div>
                    <h2 className="text-lg font-bold text-slate-900">Meal Preference Hierarchy Rules</h2>
                    <p className="text-sm text-slate-500 mt-0.5">Automated selection logic executed by the Python Playwright agent</p>
                  </div>
                  <span className="px-3 py-1 bg-emerald-50 text-emerald-700 text-xs font-medium rounded-full">Rule Active</span>
                </div>

                <div className="space-y-4">
                  <div className="flex items-start gap-4 p-4 rounded-xl bg-slate-50 border border-slate-100">
                    <div className="w-8 h-8 rounded-lg bg-indigo-100 text-indigo-700 font-bold flex items-center justify-center shrink-0">1</div>
                    <div>
                      <h4 className="text-sm font-semibold text-slate-900">Priority 1: Non-Veg</h4>
                      <p className="text-xs text-slate-600 mt-0.5">If lunch menu contains Non-Veg (chicken, fish, mutton), the agent immediately books it.</p>
                    </div>
                  </div>

                  <div className="flex items-start gap-4 p-4 rounded-xl bg-slate-50 border border-slate-100">
                    <div className="w-8 h-8 rounded-lg bg-indigo-100 text-indigo-700 font-bold flex items-center justify-center shrink-0">2</div>
                    <div>
                      <h4 className="text-sm font-semibold text-slate-900">Priority 2: Eggitarian</h4>
                      <p className="text-xs text-slate-600 mt-0.5">If Non-Veg is not available but Eggitarian is present, the agent automatically books Eggitarian.</p>
                    </div>
                  </div>

                  <div className="flex items-start gap-4 p-4 rounded-xl bg-slate-50 border border-slate-100">
                    <div className="w-8 h-8 rounded-lg bg-indigo-100 text-indigo-700 font-bold flex items-center justify-center shrink-0">3</div>
                    <div>
                      <h4 className="text-sm font-semibold text-slate-900">Priority 3: Veg (Fallback)</h4>
                      <p className="text-xs text-slate-600 mt-0.5">If neither Non-Veg nor Eggitarian is available, pure Veg is booked as the standard fallback.</p>
                    </div>
                  </div>
                </div>
              </div>

              {/* Quick Actions & Recent Log */}
              <div className="bg-white p-8 rounded-2xl border border-slate-200 shadow-xs flex flex-col justify-between">
                <div>
                  <h3 className="text-lg font-bold text-slate-900 mb-2">Target Portal</h3>
                  <p className="text-xs text-slate-500 mb-4">Direct integration with SpaceBasic mobile web portal.</p>
                  
                  <a
                    href="https://portal.spacebasic.com/module"
                    target="_blank"
                    rel="noreferrer"
                    className="flex items-center justify-between p-3 rounded-xl bg-slate-50 border border-slate-200 text-sm font-medium text-slate-700 hover:bg-slate-100 transition-colors mb-6"
                  >
                    <span className="truncate">portal.spacebasic.com/module</span>
                    <ExternalLink className="w-4 h-4 text-slate-400 shrink-0" />
                  </a>

                  <div className="border-t border-slate-100 pt-4">
                    <h4 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">Last Execution Result</h4>
                    {statusData?.lastLog ? (
                      <div className="p-3 bg-slate-50 rounded-xl text-xs font-mono text-slate-700 space-y-1">
                        <div className="text-indigo-600 font-semibold">{statusData.lastLog.timestamp}</div>
                        <div className="truncate">{statusData.lastLog.message}</div>
                      </div>
                    ) : (
                      <p className="text-xs text-slate-400 italic">No recent execution logs found.</p>
                    )}
                  </div>
                </div>

                <div className="mt-6">
                  <button
                    onClick={() => setActiveTab('session')}
                    className="w-full py-2.5 px-4 bg-slate-900 text-white text-xs font-semibold rounded-xl hover:bg-slate-800 transition-colors"
                  >
                    Configure Browser Session
                  </button>
                </div>
              </div>
            </div>

            {/* Menu Popularity D3 Chart Section */}
            <div className="pt-2">
              <MenuPopularityChart />
            </div>
          </div>
        )}

        {activeTab === 'schedule' && (
          <div className="bg-white rounded-2xl border border-slate-200 shadow-xs overflow-hidden">
            <div className="p-6 border-b border-slate-200 flex items-center justify-between">
              <div>
                <h2 className="text-lg font-bold text-slate-900">Upcoming College Working Days</h2>
                <p className="text-xs text-slate-500 mt-0.5">Automated meal bookings scheduled for Monday through Saturday</p>
              </div>
              <span className="text-xs font-mono text-slate-500">Cutoff: 09:00 PM Daily</span>
            </div>

            <div className="divide-y divide-slate-100">
              {meals.map((m, idx) => (
                <div key={idx} className="p-6 flex items-center justify-between hover:bg-slate-50 transition-colors">
                  <div className="flex items-center gap-4">
                    <div className="w-12 h-12 rounded-xl bg-indigo-50 text-indigo-600 flex flex-col items-center justify-center font-bold">
                      <span className="text-xs uppercase">{m.day.substring(0, 3)}</span>
                      <span className="text-sm">{m.date.split('-')[2]}</span>
                    </div>
                    <div>
                      <h4 className="text-sm font-semibold text-slate-900">{m.day} — {m.date}</h4>
                      <p className="text-xs text-slate-500 mt-0.5">{m.menu}</p>
                    </div>
                  </div>

                  <div className="flex items-center gap-6">
                    <div className="text-right">
                      <span className="text-xs font-medium text-slate-500">Auto-Selected:</span>
                      <div className="text-xs font-bold text-indigo-600">{m.autoSelected}</div>
                    </div>
                    <span className={`px-3 py-1 rounded-full text-xs font-medium ${m.status === 'Booked' ? 'bg-emerald-50 text-emerald-700' : 'bg-slate-100 text-slate-600'}`}>
                      {m.status}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {activeTab === 'session' && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
            <div className="bg-white p-8 rounded-2xl border border-slate-200 shadow-xs">
              <h2 className="text-lg font-bold text-slate-900 mb-2">Active Session Management</h2>
              <p className="text-xs text-slate-500 mb-6">
                SpaceBasic stays logged in on your phone or laptop. Paste your active session cookies or Playwright storage state JSON below so the automated agent can book meals without re-logging.
              </p>

              <form onSubmit={handleSaveSession} className="space-y-4">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-2">
                    Session Cookies / Storage State (JSON)
                  </label>
                  <textarea
                    rows={8}
                    value={cookieInput}
                    onChange={(e) => setCookieInput(e.target.value)}
                    placeholder={'[\n  {\n    "name": "connect.sid",\n    "value": "s%3A...",\n    "domain": ".spacebasic.com",\n    "path": "\/"\n  }\n]'}
                    className="w-full p-4 font-mono text-xs bg-slate-50 border border-slate-200 rounded-xl focus:ring-2 focus:ring-indigo-500 focus:outline-hidden"
                  />
                </div>

                <button
                  type="submit"
                  className="w-full py-3 bg-indigo-600 text-white text-xs font-semibold rounded-xl hover:bg-indigo-700 transition-colors shadow-sm cursor-pointer"
                >
                  Save & Update Session State
                </button>
              </form>
            </div>

            <div className="bg-white p-8 rounded-2xl border border-slate-200 shadow-xs flex flex-col justify-between">
              <div>
                <h3 className="text-lg font-bold text-slate-900 mb-2">How to Extract Session</h3>
                <ol className="list-decimal list-inside space-y-3 text-xs text-slate-600">
                  <li>Open <a href="https://portal.spacebasic.com/module" target="_blank" rel="noreferrer" className="text-indigo-600 underline">portal.spacebasic.com/module</a> in your browser where you are already logged in.</li>
                  <li>Open Browser Developer Tools (F12) → Application / Storage → Cookies.</li>
                  <li>Copy your authentication cookies or export them using a browser extension like <em>EditThisCookie</em>.</li>
                  <li>Paste the JSON array into the field on the left and save.</li>
                </ol>
              </div>

              <div className="mt-8 p-4 bg-slate-50 rounded-xl border border-slate-100">
                <div className="flex items-center gap-2 text-xs font-semibold text-slate-700 mb-1">
                  <ShieldCheck className="w-4 h-4 text-emerald-600" />
                  <span>Secure Local Storage</span>
                </div>
                <p className="text-xs text-slate-500">Your session credentials remain stored locally and are only used by the Playwright agent to access your SpaceBasic account.</p>
              </div>
            </div>
          </div>
        )}

        {activeTab === 'logs' && (
          <div className="bg-slate-900 text-slate-100 p-8 rounded-2xl border border-slate-800 shadow-lg font-mono text-xs">
            <div className="flex items-center justify-between pb-4 mb-4 border-b border-slate-800">
              <div className="flex items-center gap-2">
                <Terminal className="w-4 h-4 text-indigo-400" />
                <span className="font-bold text-sm">Python Playwright Agent Execution Logs</span>
              </div>
              <button
                onClick={fetchData}
                className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 rounded-lg text-slate-300 transition-colors text-xs"
              >
                Refresh Logs
              </button>
            </div>

            <div className="space-y-2 max-h-[600px] overflow-y-auto pr-2">
              {logs.length === 0 ? (
                <div className="text-slate-500 italic py-8 text-center">No execution logs recorded yet. Click "Run Agent Now" to test.</div>
              ) : (
                logs.map((log: any, idx: number) => (
                  <div key={idx} className="flex items-start gap-3 py-1 border-b border-slate-800/50">
                    <span className="text-slate-500 shrink-0">[{log.timestamp}]</span>
                    <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold uppercase shrink-0 ${log.level === 'ERROR' ? 'bg-red-950 text-red-400' : log.level === 'WARNING' ? 'bg-amber-950 text-amber-400' : 'bg-indigo-950 text-indigo-400'}`}>
                      {log.level}
                    </span>
                    <span className="text-slate-300 break-all">{log.message}</span>
                  </div>
                ))
              )}
            </div>
          </div>
        )}

        {activeTab === 'settings' && (
          <div className="bg-white p-8 rounded-2xl border border-slate-200 shadow-xs max-w-2xl mx-auto">
            <h2 className="text-lg font-bold text-slate-900 mb-2">Agent Configuration</h2>
            <p className="text-xs text-slate-500 mb-6">Configure execution schedules, cutoff times, and notification alerts.</p>

            <form onSubmit={handleSaveConfig} className="space-y-6">
              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-2">
                  SpaceBasic Portal URL
                </label>
                <input
                  type="text"
                  value={config.portal_url || ''}
                  onChange={(e) => setConfig({ ...config, portal_url: e.target.value })}
                  className="w-full p-3 text-xs bg-slate-50 border border-slate-200 rounded-xl focus:ring-2 focus:ring-indigo-500 focus:outline-hidden"
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-2">
                    Daily Booking Time
                  </label>
                  <input
                    type="time"
                    value={config.booking_time || '08:30'}
                    onChange={(e) => setConfig({ ...config, booking_time: e.target.value })}
                    className="w-full p-3 text-xs bg-slate-50 border border-slate-200 rounded-xl focus:ring-2 focus:ring-indigo-500 focus:outline-hidden"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-2">
                    Daily Cutoff Time
                  </label>
                  <input
                    type="time"
                    value={config.cutoff_time || '21:00'}
                    onChange={(e) => setConfig({ ...config, cutoff_time: e.target.value })}
                    className="w-full p-3 text-xs bg-slate-50 border border-slate-200 rounded-xl focus:ring-2 focus:ring-indigo-500 focus:outline-hidden"
                  />
                </div>
              </div>

              <div className="border-t border-slate-100 pt-6">
                <h3 className="text-sm font-bold text-slate-900 mb-4">Telegram Notifications</h3>
                <div className="space-y-4">
                  <div>
                    <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-2">
                      Telegram Bot Token
                    </label>
                    <input
                      type="text"
                      value={config.telegram_bot_token || ''}
                      onChange={(e) => setConfig({ ...config, telegram_bot_token: e.target.value })}
                      placeholder="123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ"
                      className="w-full p-3 text-xs bg-slate-50 border border-slate-200 rounded-xl focus:ring-2 focus:ring-indigo-500 focus:outline-hidden font-mono"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-2">
                      Telegram Chat ID
                    </label>
                    <input
                      type="text"
                      value={config.telegram_chat_id || ''}
                      onChange={(e) => setConfig({ ...config, telegram_chat_id: e.target.value })}
                      placeholder="-100123456789"
                      className="w-full p-3 text-xs bg-slate-50 border border-slate-200 rounded-xl focus:ring-2 focus:ring-indigo-500 focus:outline-hidden font-mono"
                    />
                  </div>
                </div>
              </div>

              <div className="pt-4">
                <button
                  type="submit"
                  className="w-full py-3 bg-indigo-600 text-white text-xs font-semibold rounded-xl hover:bg-indigo-700 transition-colors shadow-sm cursor-pointer"
                >
                  Save Changes
                </button>
              </div>
            </form>
          </div>
        )}
      </main>
    </div>
  );
}
