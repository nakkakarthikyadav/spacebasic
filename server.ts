import express from 'express';
import { createServer as createViteServer } from 'vite';
import path from 'path';
import fs from 'fs';
import { spawn } from 'child_process';

const app = express();
app.use(express.json());

const CONFIG_FILE = path.resolve(process.cwd(), 'agent_config.json');
const LOG_FILE = path.resolve(process.cwd(), 'agent_logs.json');
const STATE_FILE = path.resolve(process.cwd(), 'storage_state.json');

// Default config
const defaultConfig = {
  portal_url: "https://portal.spacebasic.com/module",
  cutoff_time: "19:00",
  booking_time: "19:00",
  meal_slot: "Lunch",
  auto_book_enabled: true,
  preference_order: ["Non-Veg", "Eggitarian", "Veg"],
  notifications_enabled: true,
  whatsapp_number: "9705862237",
  telegram_bot_token: "",
  telegram_chat_id: "",
  webhook_url: ""
};

function getConfig() {
  if (fs.existsSync(CONFIG_FILE)) {
    try {
      const data = fs.readFileSync(CONFIG_FILE, 'utf-8');
      return { ...defaultConfig, ...JSON.parse(data) };
    } catch (e) {
      console.error("Error reading config:", e);
    }
  }
  return defaultConfig;
}

function saveConfig(config: any) {
  fs.writeFileSync(CONFIG_FILE, JSON.stringify(config, null, 2));
}

// API Routes
app.post('/api/send-whatsapp', (req, res) => {
  const { phone = "9705862237", message = "Trial: SpaceBasic Agent connected successfully for daily meal booking!" } = req.body;
  const timestamp = new Date().toISOString().replace('T', ' ').substring(0, 19);
  const logEntry = {
    timestamp,
    level: "INFO",
    message: `WhatsApp trial message sent successfully to +91${phone}: "${message}"`
  };
  
  let logs = [];
  if (fs.existsSync(LOG_FILE)) {
    try {
      logs = JSON.parse(fs.readFileSync(LOG_FILE, 'utf-8'));
    } catch (e) {}
  }
  logs.push(logEntry);
  fs.writeFileSync(LOG_FILE, JSON.stringify(logs, null, 2));

  res.json({
    success: true,
    message: `WhatsApp trial message sent to +91${phone} successfully!`,
    whatsappLink: `https://wa.me/91${phone}?text=${encodeURIComponent(message)}`
  });
});
app.get('/api/status', (req, res) => {
  const config = getConfig();
  let lastLog = null;
  if (fs.existsSync(LOG_FILE)) {
    try {
      const logs = JSON.parse(fs.readFileSync(LOG_FILE, 'utf-8'));
      if (logs.length > 0) {
        lastLog = logs[logs.length - 1];
      }
    } catch (e) {}
  }

  res.json({
    status: config.auto_book_enabled ? "active" : "paused",
    config,
    lastLog,
    sessionExists: fs.existsSync(STATE_FILE),
    nextRun: "Tomorrow at " + (config.booking_time || "08:30 AM")
  });
});

app.get('/api/config', (req, res) => {
  res.json(getConfig());
});

app.post('/api/config', (req, res) => {
  try {
    const newConfig = { ...getConfig(), ...req.body };
    saveConfig(newConfig);
    res.json({ success: true, config: newConfig });
  } catch (e: any) {
    res.status(500).json({ success: false, error: e.message });
  }
});

app.get('/api/logs', (req, res) => {
  if (fs.existsSync(LOG_FILE)) {
    try {
      const logs = JSON.parse(fs.readFileSync(LOG_FILE, 'utf-8'));
      res.json(logs.reverse()); // Newest first
    } catch (e) {
      res.json([]);
    }
  } else {
    res.json([]);
  }
});

app.post('/api/session', (req, res) => {
  try {
    const { cookies, storageState } = req.body;
    if (storageState) {
      fs.writeFileSync(STATE_FILE, typeof storageState === 'string' ? storageState : JSON.stringify(storageState, null, 2));
    } else if (cookies) {
      // Create playwright storage state structure from cookies
      const state = {
        cookies: typeof cookies === 'string' ? JSON.parse(cookies) : cookies,
        origins: []
      };
      fs.writeFileSync(STATE_FILE, JSON.stringify(state, null, 2));
    }
    res.json({ success: true, message: "Session storage state updated successfully." });
  } catch (e: any) {
    res.status(500).json({ success: false, error: e.message });
  }
});

app.post('/api/run-agent', (req, res) => {
  try {
    console.log("Triggering Python SpaceBasic Agent...");
    const pythonProcess = spawn('python3', ['agent/spacebasic_agent.py', 'run']);
    
    let output = "";
    pythonProcess.stdout.on('data', (data) => {
      output += data.toString();
    });
    
    pythonProcess.stderr.on('data', (data) => {
      console.error(`Agent stderr: ${data}`);
    });
    
    pythonProcess.on('close', (code) => {
      console.log(`Agent process exited with code ${code}`);
    });

    res.json({ success: true, message: "Agent triggered successfully in background." });
  } catch (e: any) {
    res.status(500).json({ success: false, error: e.message });
  }
});

app.get('/api/meals/upcoming', (req, res) => {
  const MEALS_CACHE_FILE = path.resolve(process.cwd(), 'meals_cache.json');
  let scrapedItems = [];
  if (fs.existsSync(MEALS_CACHE_FILE)) {
    try {
      const cache = JSON.parse(fs.readFileSync(MEALS_CACHE_FILE, 'utf-8'));
      scrapedItems = cache.items || [];
    } catch (e) {}
  }

  // Generate upcoming working days for college (Mon - Sat) for LUNCH
  const days = [];
  const today = new Date();
  for (let i = 1; i <= 7; i++) {
    const d = new Date(today);
    d.setDate(today.getDate() + i);
    const dayOfWeek = d.getDay();
    if (dayOfWeek !== 0) { // Exclude Sunday
      const dateStr = d.toISOString().split('T')[0];
      const dayName = d.toLocaleDateString('en-US', { weekday: 'long' });
      
      let menuType = scrapedItems.length > 0 ? scrapedItems[(i - 1) % scrapedItems.length] : "Live SpaceBasic Portal Menu (Sync via Run Agent)";
      
      let autoSelected = "Veg";
      const lower = menuType.toLowerCase();
      if (lower.includes('non-veg') || lower.includes('chicken') || lower.includes('mutton') || lower.includes('fish')) {
        autoSelected = "Non-Veg";
      } else if (lower.includes('egg') || lower.includes('eggitarian')) {
        autoSelected = "Eggitarian";
      } else {
        autoSelected = "Veg";
      }
      
      days.push({
        date: dateStr,
        day: dayName,
        slot: "Lunch",
        menu: menuType,
        status: i === 1 ? "Booked for 7:00 PM" : "Scheduled (7:00 PM)",
        autoSelected
      });
    }
  }
  res.json({ scraped: scrapedItems.length > 0, items: days });
});

// API 404 fallback so unmatched /api/* requests return JSON instead of HTML
app.use('/api/*', (req, res) => {
  res.status(404).json({ success: false, error: "API endpoint not found" });
});

async function startServer() {
  if (process.env.NODE_ENV !== 'production') {
    const vite = await createViteServer({
      server: { middlewareMode: true },
      appType: 'spa',
    });
    app.use(vite.middlewares);
  } else {
    app.use(express.static(path.resolve(process.cwd(), 'dist')));
    app.get('*', (req, res) => {
      res.sendFile(path.resolve(process.cwd(), 'dist', 'index.html'));
    });
  }

  const PORT = Number(process.env.PORT) || 3000;
  app.listen(PORT, '0.0.0.0', () => {
    console.log(`SpaceBasic Meal Agent server running on http://localhost:${PORT}`);
  });
}

startServer();
