// HydroGrid 2.0 Client API Module
const cache = new Map();
let activeAbortControllers = new Map();

export async function fetchApi(endpoint, options = {}, useCache = true) {
  const cacheKey = endpoint + JSON.stringify(options);
  if (useCache && cache.has(cacheKey)) {
    return cache.get(cacheKey);
  }

  // Cancel prior in-flight request on same endpoint if needed
  if (activeAbortControllers.has(endpoint)) {
    activeAbortControllers.get(endpoint).abort();
  }
  const controller = new AbortController();
  activeAbortControllers.set(endpoint, controller);

  try {
    const res = await fetch(endpoint, {
      cache: 'no-cache',
      ...options,
      signal: controller.signal,
      headers: {
        'Accept': 'application/json',
        'Content-Type': 'application/json',
        ...(options.headers || {})
      }
    });

    if (!res.ok) {
      throw new Error(`API error ${res.status}: ${res.statusText}`);
    }

    const data = await res.json();
    if (useCache) {
      cache.set(cacheKey, data);
    }
    return data;
  } catch (err) {
    if (err.name === 'AbortError') {
      console.log(`Fetch aborted: ${endpoint}`);
      throw err;
    }
    console.error(`Fetch failure [${endpoint}]:`, err);
    throw err;
  } finally {
    if (activeAbortControllers.get(endpoint) === controller) {
      activeAbortControllers.delete(endpoint);
    }
  }
}

export function clearApiCache() {
  cache.clear();
}

