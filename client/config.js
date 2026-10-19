// DroneDrill AI - Client Configuration
// SIH 2026, PS 26247, Team NexxGenX
// Configures API endpoint and current active trainee identifier

const CONFIG = {
  // Use relative path by default or current origin, falling back to localhost:8000
  API_BASE: window.location.origin.includes(":8000") || window.location.origin.includes("127.0.0.1") || window.location.origin.includes("localhost")
    ? window.location.origin
    : "http://127.0.0.1:8000",
  get TRAINEE_ID() {
    return localStorage.getItem("dronedrill_trainee_id") || "demo_trainee_01";
  },
  set TRAINEE_ID(val) {
    if (val) localStorage.setItem("dronedrill_trainee_id", val);
  },
  getActiveTraineeId() {
    return localStorage.getItem("dronedrill_trainee_id") || "demo_trainee_01";
  },
  APP_VERSION: "1.0.0",
};

// Export to window
window.CONFIG = CONFIG;

