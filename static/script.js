// --- Utilities ---------------------------------------------------------------

function el(tag, attrs = {}, children = []) {
  const node = document.createElement(tag);
  Object.entries(attrs).forEach(([k, v]) => {
    if (k === "style" && typeof v === "object") Object.assign(node.style, v);
    else if (k in node) node[k] = v;
    else node.setAttribute(k, v);
  });
  [].concat(children).forEach((c) =>
    node.appendChild(typeof c === "string" ? document.createTextNode(c) : c)
  );
  return node;
}

function escapeHtml(s) {
  return String(s)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

// --- DOM references ----------------------------------------------------------
const addForm = document.getElementById("addForm");
const searchForm = document.getElementById("searchForm");
const searchInput = document.getElementById("searchInput");

const titleInput  = document.getElementById("bookTitle");
const yearInput   = document.getElementById("publicationYear");
const authorInput = document.getElementById("authorName");
const imageInput  = document.getElementById("imageUrl");

const grid = document.getElementById("booksGrid");
const emptyState = document.getElementById("emptyState");

// --- Rendering ---------------------------------------------------------------

function renderGrid(books) {
  grid.innerHTML = "";
  if (!books || books.length === 0) {
    emptyState.classList.remove("d-none");
    return;
  }
  emptyState.classList.add("d-none");

  books.forEach((b) => {
    const title = escapeHtml(b.title ?? "");
    const author = escapeHtml(b.author ?? "");
    const year = b.publication_year ? String(b.publication_year) : "";
    const img = b.image_url || "";

    const meta = [author ? `by ${author}` : "", year ? `• ${escapeHtml(year)}` : ""]
      .filter(Boolean)
      .join(" ");

    const card = `
      <div class="book-card h-100">
        <img class="book-cover"
             src="${img}"
             alt="Cover for ${title}"
             onerror="this.src='https://via.placeholder.com/300x400?text=No+Image';">
        <div class="book-body">
          <div class="book-title">${title}</div>
          <div class="book-author">${meta}</div>
        </div>
      </div>
    `;

    const col = document.createElement("div");
    col.className = "book-column";
    col.innerHTML = card;
    grid.appendChild(col);
  });
}

// --- API calls ---------------------------------------------------------------

async function fetchBooks(q = "") {
  try {
    const url = q ? `/api/books?q=${encodeURIComponent(q)}` : "/api/books";
    const r = await fetch(url);
    if (!r.ok) throw new Error(`GET ${url} -> ${r.status}`);
    const payload = await r.json();
    const items = Array.isArray(payload) ? payload : (payload.books || []);
    renderGrid(items);
  } catch (err) {
    console.error("Error fetching books:", err);
    alert("Failed to load books. Make sure the server is running.");
  }
}

async function postNewBook(bookData) {
  const r = await fetch("/api/add_book", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(bookData),
  });
  if (!r.ok) {
    const e = await r.json().catch(() => ({}));
    throw new Error(e.error || "Failed to add book");
  }
  return r.json();
}

// --- Handlers ---------------------------------------------------------------

async function handleAddBook(e) {
  e.preventDefault();

  const title = titleInput.value.trim();
  const publication_year = yearInput.value.trim();
  const author = authorInput.value.trim();
  const image_url = imageInput.value.trim();

  if (!title) return alert("Title is required");

  const bookData = { title, publication_year, author, image_url };

  try {
    await postNewBook(bookData);
    titleInput.value = yearInput.value = authorInput.value = imageInput.value = "";

    const modalEl = document.getElementById("addModal");
    if (modalEl && typeof bootstrap !== "undefined") {
      const modal = bootstrap.Modal.getInstance(modalEl) || new bootstrap.Modal(modalEl);
      modal.hide();
    }

    await fetchBooks("");
  } catch (err) {
    console.error(err);
    alert("Error adding book");
  }
}

async function handleSearch(e) {
  e.preventDefault();
  const q = (searchInput?.value || "").trim();
  await fetchBooks(q);
}

// --- Initialization ----------------------------------------------------------

document.addEventListener("DOMContentLoaded", () => {
  if (addForm) addForm.addEventListener("submit", handleAddBook);
  if (searchForm) searchForm.addEventListener("submit", handleSearch);
  fetchBooks("");
});
