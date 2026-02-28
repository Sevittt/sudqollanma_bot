# Antigravity Task Plan: Official Firebase Vector Search Integration

## Context & Objective
We are integrating the official Firebase Extension `firestore-vector-search` into our Clean Architecture Flutter app (`education_app`) and Python Aiogram bot (`sudqollanma_bot`).
The extension is already installed on Firebase. It listens to the `search_index` collection, automatically generates embeddings from the `input` field using Vertex AI/Gemini, and exposes a callable cloud function for querying.

## Phase 1: Flutter App - Data Sync (Admin Side)
**Goal:** Keep the `search_index` collection strictly synchronized with our domain entities (Articles, Videos, Systems, FAQs).

**Tasks for AI:**
1. Create a `SearchIndexModel` (Domain/Data layer) with fields:
   - `original_id` (String)
   - `type` (String: 'article', 'video', 'system', 'faq')
   - `title` (String)
   - `input` (String: the concatenated raw text content for the LLM to embed)
2. Locate the Admin Repositories/UseCases where content is created or updated (e.g., `article_repository_impl.dart`, `video_repository_impl.dart`).
3. Inject logic to simultaneously write/update a document in `FirebaseFirestore.instance.collection('search_index')` matching the `original_id` whenever an item is saved.

## Phase 2: Flutter App - Global Search using Extension (Client Side)
**Goal:** Query the extension's provided Cloud Function from the Flutter app.

**Tasks for AI:**
1. Open `lib/features/search/data/datasources/search_remote_datasource.dart`.
2. Implement the search method using `cloud_functions` package.
3. Call the extension's function exactly like this:
   ```dart
   final callable = FirebaseFunctions.instance.httpsCallable('ext-firestore-vector-search-queryCallable');
   final result = await callable.call({
     'query': userQuery,
     'limit': 5,
   });
   // The extension typically returns a list of matched document IDs or documents in result.data