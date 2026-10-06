// webllm_worker.js
// Dedicated Web Worker running on a background thread for WebLLM
// Offloads tensor operations and model execution to keep the UI smooth and responsive.

import { WebWorkerMLCEngineHandler } from "https://cdn.jsdelivr.net/npm/@mlc-ai/web-llm/+esm";

// Initialize the MLC handler inside this worker thread
const handler = new WebWorkerMLCEngineHandler();

// Forward all incoming messages to WebWorkerMLCEngineHandler
self.onmessage = (msg) => {
    handler.onmessage(msg);
};
