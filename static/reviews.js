const $ = (id) => document.getElementById(id);

// Helpers
function fmtDate(iso) {
  try { return new Date(iso).toLocaleString(); } catch { return iso || ""; }
}
function setVisible(node, show) {
  node.classList.toggle("d-none", !show);
}
function escapeHtml(s) {
  return String(s)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

// ---- Add Review (by title, case-insensitive in backend) ----
const addForm = $("addReviewForm");
const addMsg  = $("addReviewMsg");

$("clearAddForm").onclick = () => {
  $("revBookTitle").value = "";
  $("revReviewer").value = "";
  $("revRating").value = "5";
  $("revText").value = "";
};

addForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const book_title = $("revBookTitle").value.trim();
  const reviewer   = $("revReviewer").value.trim();
  const rating     = parseInt($("revRating").value, 10);
  const text       = $("revText").value.trim();

  if (!book_title || !reviewer || !rating) {
    alert("Please fill book title, reviewer, and rating.");
    return;
  }

  try {
    const r = await fetch("/api/reviews", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({ book_title, reviewer, rating, text })
    });
    if (!r.ok) throw new Error(await r.text());

    setVisible(addMsg, true);
    setTimeout(() => setVisible(addMsg, false), 1500);

    // Refresh list/avg if same title is loaded
    const current = $("listBookTitle").value.trim();
    if (current && current.toLowerCase() === book_title.toLowerCase()) {
      await loadReviewsByTitle(book_title);
      await showAverageByTitle(book_title);
    }

    addForm.reset();
    $("revRating").value = "5";
  } catch (err) {
    console.error(err);
    alert("Failed to add review.");
  }
});

// ---- Load Reviews (by title) ----
const listContainer = $("reviewsList");
const emptyState = $("reviewsEmpty");
const avgWrap = $("avgWrap");
const avgValue = $("avgValue");
const avgCount = $("avgCount");

async function loadReviewsByTitle(title) {
  listContainer.innerHTML = "";
  setVisible(emptyState, false);

  const r = await fetch(`/api/reviews?title=${encodeURIComponent(title)}`);
  const data = await r.json();
  const items = data.reviews || [];

  if (!items.length) {
    setVisible(emptyState, true);
    return;
  }

  items.forEach((rev) => {
    const row = document.createElement("div");
    row.className = "border rounded p-3 bg-white";

    row.innerHTML = `
      <div class="d-flex justify-content-between align-items-start">
        <div>
          <div class="fw-bold">${escapeHtml(rev.reviewer || "Anonymous")}</div>
          <div class="text-muted small">Rating: ${rev.rating ?? "-"} • ${fmtDate(rev.created_at)}</div>
        </div>
        ${rev._id ? `<button class="btn btn-sm btn-outline-danger" data-id="${rev._id}">Delete</button>` : ""}
      </div>
      <div class="mt-2">${escapeHtml(rev.text || "")}</div>
    `;
    listContainer.appendChild(row);

    const delBtn = row.querySelector("button[data-id]");
    if (delBtn) {
      delBtn.onclick = async () => {
        if (!confirm("Delete this review?")) return;
        const r = await fetch(`/api/reviews/${delBtn.dataset.id}`, { method: "DELETE" });
        if (r.ok) {
          row.remove();
          if (!listContainer.children.length) setVisible(emptyState, true);
          await showAverageByTitle(title);
        }
      };
    }
  });
}

async function showAverageByTitle(title) {
  try {
    const r = await fetch(`/api/reviews/avg?title=${encodeURIComponent(title)}`);
    if (!r.ok) throw new Error(await r.text());
    const d = await r.json();
    avgValue.textContent = d.avg_rating == null ? "—" : Number(d.avg_rating).toFixed(2);
    avgCount.textContent = d.count ?? 0;
    setVisible(avgWrap, true);
  } catch {
    setVisible(avgWrap, false);
  }
}

// Buttons
$("btnLoadReviews").onclick = async () => {
  const title = $("listBookTitle").value.trim();
  if (!title) return alert("Enter a Book Title.");
  await loadReviewsByTitle(title);
  await showAverageByTitle(title);
};

$("btnShowAvg").onclick = async () => {
  const title = $("listBookTitle").value.trim();
  if (!title) return alert("Enter a Book Title.");
  await showAverageByTitle(title);
};

$("btnTopRated").onclick = async () => {
  const r = await fetch("/api/reviews/top?limit=3&min_reviews=1");
  const arr = await r.json();
  if (!Array.isArray(arr) || arr.length === 0) return alert("No rated books yet.");

  const lines = arr.map(x =>
    `${x.title || `Book ${x.book_id}`}: ★${x.avg_rating} (${x.count} review${x.count !== 1 ? "s" : ""})`
  ).join("\n");

  alert("📚 Top 3 Highest-Rated Books:\n\n" + lines);
};




