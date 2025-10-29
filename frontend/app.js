const uploadForm = document.getElementById("upload-form");
const fileInput = document.getElementById("file-input");
const uploadStatus = document.getElementById("upload-status");

const queryForm = document.getElementById("query-form");
const queryText = document.getElementById("query-text");
const queryResultsInput = document.getElementById("query-results");
const queryStatus = document.getElementById("query-status");
const resultsContainer = document.getElementById("results-container");
const resultsList = document.getElementById("results-list");

const API_BASE = window.location.origin;

function setUploadLoading(isLoading) {
  uploadForm.querySelector("button").disabled = isLoading;
  uploadStatus.textContent = isLoading ? "Uploading and processing..." : "";
}

function setQueryLoading(isLoading) {
  queryForm.querySelector("button").disabled = isLoading;
  queryStatus.textContent = isLoading ? "Searching..." : "";
}

uploadForm?.addEventListener("submit", async (event) => {
  event.preventDefault();

  if (!fileInput.files.length) {
    uploadStatus.textContent = "Select one or more files to ingest.";
    return;
  }

  const formData = new FormData();
  for (const file of fileInput.files) {
    formData.append("files", file);
  }

  try {
    setUploadLoading(true);
    const response = await fetch(`${API_BASE}/ingest`, {
      method: "POST",
      body: formData,
    });

    if (!response.ok) {
      const detail = await response.json().catch(() => ({}));
      throw new Error(detail.detail || "Upload failed");
    }

    const data = await response.json();
    uploadStatus.textContent = `Ingested ${data.chunks_created} chunks from ${data.documents_ingested} document(s).`;
    fileInput.value = "";
  } catch (error) {
    console.error(error);
    uploadStatus.textContent = `Error: ${error.message}`;
  } finally {
    setUploadLoading(false);
  }
});

queryForm?.addEventListener("submit", async (event) => {
  event.preventDefault();

  const query = queryText.value.trim();
  if (!query) {
    queryStatus.textContent = "Enter a search term to continue.";
    return;
  }

  const nResults = Number.parseInt(queryResultsInput.value, 10) || 5;

  try {
    setQueryLoading(true);
    const response = await fetch(`${API_BASE}/query`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query, n_results: nResults }),
    });

    if (!response.ok) {
      const detail = await response.json().catch(() => ({}));
      throw new Error(detail.detail || "Search failed");
    }

    const data = await response.json();
    const results = data.results || [];

    if (!results.length) {
      queryStatus.textContent = "No matches yet. Ingest documents and try again.";
      resultsContainer.hidden = true;
      resultsList.innerHTML = "";
      return;
    }

    queryStatus.textContent = `Found ${results.length} match(es).`;
    resultsContainer.hidden = false;
    resultsList.innerHTML = "";

    for (const result of results) {
      const listItem = document.createElement("li");

      const excerpt = document.createElement("p");
      excerpt.textContent = result.document;
      listItem.appendChild(excerpt);

      const metadata = document.createElement("p");
      metadata.className = "result-metadata";
      const source = result.metadata?.source || "Unknown source";
      const chunkIndex = result.metadata?.chunk_index ?? "-";
      const distance =
        typeof result.distance === "number"
          ? result.distance.toFixed(4)
          : "n/a";
      metadata.textContent = `Source: ${source} • Chunk #${chunkIndex} • Distance: ${distance}`;
      listItem.appendChild(metadata);

      resultsList.appendChild(listItem);
    }
  } catch (error) {
    console.error(error);
    queryStatus.textContent = `Error: ${error.message}`;
    resultsContainer.hidden = true;
    resultsList.innerHTML = "";
  } finally {
    setQueryLoading(false);
  }
});
