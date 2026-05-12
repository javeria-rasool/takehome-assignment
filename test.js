const { JSDOM } = require('jsdom');
const dom = new JSDOM(`<!DOCTYPE html>${require('fs').readFileSync('index.html', 'utf8')}`, { runScripts: 'dangerously' });
const { window } = dom;
const { document } = window;

// Set localStorage mock
window.localStorage = {
  store: {},
  getItem(k) { return this.store[k] || null },
  setItem(k, v) { this.store[k] = v },
  removeItem(k) { delete this.store[k] },
  clear() { this.store = {} }
};

// Import the app script
const appScript = document.currentScript;
const appScriptContent = appScript.textContent;

// Evaluate the app script in the JSDOM context
eval(appScriptContent);

// Export the todos array
export default window.todos;
