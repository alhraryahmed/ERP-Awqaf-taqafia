/* =========================
   TAQ IT - CORE ENGINE
   app.js
   Main System Controller
   ========================= */


/* =========================
   GLOBAL APP OBJECT
========================= */

window.TAQ = {
  version: "1.0.0",
  modules: {},
  state: {},
  events: {},
};


/* =========================
   STATE MANAGEMENT
========================= */

TAQ.state = {
  currentPage: null,
  sidebarCollapsed: false,
  user: null,
};


/* =========================
   EVENT SYSTEM (Simple Pub/Sub)
========================= */

TAQ.events = {
  events: {},

  on(event, callback) {
    if (!this.events[event]) {
      this.events[event] = [];
    }
    this.events[event].push(callback);
  },

  emit(event, data) {
    if (this.events[event]) {
      this.events[event].forEach(cb => cb(data));
    }
  }
};


/* =========================
   MODULE REGISTRY
========================= */

TAQ.registerModule = function(name, module) {
  this.modules[name] = module;
};


/* =========================
   DOM READY INIT
========================= */

document.addEventListener("DOMContentLoaded", function () {
  TAQ.init();
});


/* =========================
   INIT SYSTEM
========================= */

TAQ.init = function () {

  console.log("TAQ SYSTEM INITIALIZING...");

  this.initSidebar();
  this.initWorkspace();
  this.initForms();
  this.initLists();

  console.log("TAQ SYSTEM READY ✔");
};


/* =========================
   SIDEBAR INIT
========================= */

TAQ.initSidebar = function () {
  if (this.modules.sidebar && this.modules.sidebar.init) {
    this.modules.sidebar.init();
  }
};


/* =========================
   WORKSPACE INIT
========================= */

TAQ.initWorkspace = function () {
  if (this.modules.workspace && this.modules.workspace.init) {
    this.modules.workspace.init();
  }
};


/* =========================
   FORMS INIT
========================= */

TAQ.initForms = function () {
  if (this.modules.forms && this.modules.forms.init) {
    this.modules.forms.init();
  }
};


/* =========================
   LIST INIT
========================= */

TAQ.initLists = function () {
  if (this.modules.list && this.modules.list.init) {
    this.modules.list.init();
  }
};


/* =========================
   SIDEBAR TOGGLE (GLOBAL)
========================= */

TAQ.toggleSidebar = function () {
  const sidebar = document.querySelector(".sidebar");

  if (!sidebar) return;

  sidebar.classList.toggle("collapsed");

  this.state.sidebarCollapsed = sidebar.classList.contains("collapsed");

  this.events.emit("sidebar:toggle", this.state.sidebarCollapsed);
};


/* =========================
   PAGE ROUTER (Simple)
========================= */

TAQ.navigate = function (page) {
  this.state.currentPage = page;

  console.log("Navigating to:", page);

  this.events.emit("route:change", page);
};


/* =========================
   THEME HELPERS (Future)
========================= */

TAQ.setTheme = function (theme) {
  document.documentElement.setAttribute("data-theme", theme);
};