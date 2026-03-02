## 2024-05-24 - Async API Calls
**Learning:** In the AI service, there were several synchronous calls to Gemini and Firestore made sequentially. Using `await genai.embed_content_async` instead of `genai.embed_content` and `asyncio.gather` for independent context fetching drastically reduces TTFB latency.
**Action:** Always check if multiple independent async operations can be run concurrently using `asyncio.gather` to reduce overall response time.
