from flask import Flask, jsonify, render_template, request
import sqlite3
import os
import time, traceback
from datetime import datetime, timezone
from datetime import datetime
from pymongo import MongoClient

try:
    from bson.objectid import ObjectId  # installed with pymongo
except Exception:
    ObjectId = None  # type: ignore

app = Flask(__name__)

# ----------------------------- SQLite (Books) ------------------------------

DATABASE = os.path.join(os.path.dirname(__file__), "library.db")

def ensure_books_schema():
    """Ensure Books table exists and includes author and image_url columns."""
    conn = sqlite3.connect(DATABASE)
    try:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS Books(
                book_id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                publication_year TEXT,
                author TEXT,
                image_url TEXT
            )
        """)
        # Add columns if an older DB is missing them
        try:
            cur.execute("ALTER TABLE Books ADD COLUMN author TEXT")
        except sqlite3.OperationalError:
            pass
        try:
            cur.execute("ALTER TABLE Books ADD COLUMN image_url TEXT")
        except sqlite3.OperationalError:
            pass
        conn.commit()
    finally:
        conn.close()

ensure_books_schema()

# Helper: resolve book_id from a (case-insensitive) title
def _book_id_from_title_ci(title: str):
    """
    Return the first book_id that matches the title (case-insensitive).
    Tries exact, then partial LIKE, then a punctuation-agnostic contains.
    """
    if not title:
        return None
    conn = sqlite3.connect(DATABASE)
    try:
        cur = conn.cursor()
        # Exact (case-insensitive)
        cur.execute("SELECT book_id FROM Books WHERE lower(title)=lower(?) LIMIT 1", (title,))
        row = cur.fetchone()
        if row:
            return str(row[0])

        # Partial LIKE
        cur.execute(
            "SELECT book_id FROM Books WHERE lower(title) LIKE lower(?) ORDER BY title COLLATE NOCASE LIMIT 1",
            (f"%{title}%",),
        )
        row = cur.fetchone()
        if row:
            return str(row[0])

        # Fallback: ignore punctuation/spacing
        import re
        norm = re.sub(r"[^a-z0-9]", "", title.lower())
        cur.execute("SELECT book_id, title FROM Books")
        for bid, t in cur.fetchall():
            tnorm = re.sub(r"[^a-z0-9]", "", (t or "").lower())
            if norm and norm in tnorm:
                return str(bid)
        return None
    finally:
        conn.close()

# -------------------- MongoDB Logging Integration --------------------
def log_to_mongo(func_name, status="success", delta_t=None, message=None):
    """Store a log entry in MongoDB (logs collection) with debug output."""
    try:
        print(f"[DEBUG] log_to_mongo called for {func_name} ({status})")
        if _mongo_db is None:
            print("[DEBUG] _mongo_db is None → MongoDB connection not available.")
            return

        logs = _mongo_db["logs"]
        log_entry = {
            "function_name": func_name,
            "status": status,
            "execution_time": delta_t,
            "message": message,
            "created_at": datetime.now(timezone.utc)
        }

        # Try insert and confirm visually in terminal
        result = logs.insert_one(log_entry)
        print(f"[DEBUG] Log inserted with _id: {result.inserted_id}")

    except Exception as e:
        print(f"[Logging error] {e}")


def log_time(func):
    """Decorator to measure execution time and store logs."""
    def wrapper(*args, **kwargs):
        print(f"[DEBUG] log_time wrapper triggered for {func.__name__}")
        start = time.time()
        try:
            result = func(*args, **kwargs)
            duration = round(time.time() - start, 4)
            print(f"[DEBUG] Function {func.__name__} executed in {duration}s")
            log_to_mongo(func.__name__, "success", duration)
            return result
        except Exception as e:
            print(f"[DEBUG] Exception in {func.__name__}: {e}")
            log_to_mongo(func.__name__, "error", None, str(e))
            traceback.print_exc()
            return jsonify({"error": str(e)}), 500
    wrapper.__name__ = func.__name__
    return wrapper




# ------------------------------- Books API ----------------------------------

@app.route('/api/books', methods=['GET'])
@log_time
def get_all_books():
    """
    Optional search: /api/books?q=term
    Matches title OR author (case-insensitive).
    """
    q = (request.args.get("q") or "").strip().lower()
    try:
        conn = sqlite3.connect(DATABASE)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        if q:
            cursor.execute(
                """
                SELECT book_id, title, publication_year,
                       COALESCE(author,'') AS author, COALESCE(image_url,'') AS image_url
                FROM Books
                WHERE lower(title) LIKE ? OR lower(author) LIKE ?
                ORDER BY title COLLATE NOCASE
                """,
                (f"%{q}%", f"%{q}%"),
            )
        else:
            cursor.execute(
                """
                SELECT book_id, title, publication_year,
                       COALESCE(author,'') AS author, COALESCE(image_url,'') AS image_url
                FROM Books
                ORDER BY title COLLATE NOCASE
                """
            )

        rows = cursor.fetchall()
        conn.close()

        return jsonify({
            'books': [
                {
                    'book_id': r['book_id'],
                    'title': r['title'],
                    'publication_year': r['publication_year'],
                    'author': r['author'],
                    'image_url': r['image_url']
                } for r in rows
            ]
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/books', methods=['POST'])
@log_time
def add_book_v2():
    """
    JSON: { "title", "author", "image_url", "publication_year" }
    """
    try:
        data = request.get_json(silent=True) or {}
        title = (data.get('title') or "").strip()
        author = (data.get('author') or "").strip()
        image_url = (data.get('image_url') or "").strip()
        publication_year = (data.get('publication_year') or "").strip()

        if not title or not author or not image_url:
            return jsonify({'error': 'title, author, and image_url are required'}), 400

        conn = sqlite3.connect(DATABASE)
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO Books (title, publication_year, author, image_url) VALUES (?, ?, ?, ?)",
            (title, publication_year or None, author, image_url)
        )
        conn.commit()
        conn.close()

        return jsonify({'message': 'Book added successfully'}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/seed', methods=['POST'])
def seed_books():
    """
    Bulk insert: list of {title, author, image_url, publication_year}
    """
    try:
        items = request.get_json(silent=True) or []
        if not isinstance(items, list):
            return jsonify({'error': 'Expected a JSON list of book objects'}), 400

        conn = sqlite3.connect(DATABASE)
        cur = conn.cursor()
        inserted = 0
        for b in items:
            title = (b.get('title') or "").strip()
            author = (b.get('author') or "").strip()
            image_url = (b.get('image_url') or "").strip()
            publication_year = (b.get('publication_year') or "").strip()
            if title and author and image_url:
                cur.execute(
                    "INSERT INTO Books (title, publication_year, author, image_url) VALUES (?, ?, ?, ?)",
                    (title, publication_year or None, author, image_url)
                )
                inserted += 1
        conn.commit()
        conn.close()
        return jsonify({'ok': True, 'inserted': inserted}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# Legacy add route kept for backward compatibility (used by older JS)
@app.route('/api/add_book', methods=['POST'])
def add_book():
    try:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()

        data = request.get_json(silent=True) or request.form
        title = (data.get('title') or "").strip()
        publication_year = (data.get('publication_year') or "").strip()
        author = (data.get('author') or "").strip()
        image_url = (data.get('image_url') or "").strip()

        if not title:
            conn.close()
            return jsonify({'error': 'Title is required'}), 400

        cursor.execute(
            "INSERT INTO Books (title, publication_year, author, image_url) VALUES (?, ?, ?, ?)",
            (title, publication_year or None, author or None, image_url or None)
        )
        conn.commit()
        conn.close()

        return jsonify({'message': 'Book added successfully'}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/authors', methods=['GET'])
def get_all_authors():
    try:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM Authors")
        authors = cursor.fetchall()
        conn.close()
        return jsonify(authors)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ----------------------------- MongoDB (Reviews) -----------------------------

MONGODB_URI = "mongodb+srv://admin:Sweets001@cluster0.gxnm1c9.mongodb.net/"
MONGO_DBNAME = "library"


try:
    _mongo_client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
    _mongo_db = _mongo_client[MONGO_DBNAME]
    _reviews = _mongo_db["reviews"]
except Exception as e:
    print("MongoDB connection failed:", e)
    _mongo_client = None
    _mongo_db = None
    _reviews = None

def ensure_mongo_indexes():
    try:
        if _reviews is not None:
            _reviews.create_index([("book_id", 1), ("created_at", -1)])
            _reviews.create_index([("rating", -1)])
    except Exception as e:
        print("Index error:", e)

ensure_mongo_indexes()

def _oid(s):
    if ObjectId is None:
        return None
    try:
        return ObjectId(s)
    except Exception:
        return None

def _string_id(doc):
    d = dict(doc)
    if "_id" in d:
        d["_id"] = str(d["_id"])
    return d


# ------------------------------ Reviews API ----------------------------------

@app.route('/api/reviews', methods=['GET'])
@log_time
def mongo_get_reviews():
    """
    GET /api/reviews?book_id=123
    GET /api/reviews?title=Clean%20Code   (case-insensitive)
    """
    try:
        if _reviews is None:
            return jsonify({"error": "MongoDB not available"}), 500

        book_id = (request.args.get('book_id') or "").strip()
        title = (request.args.get('title') or "").strip()
        if not book_id and title:
            book_id = _book_id_from_title_ci(title) or ""

        limit = min(int(request.args.get("limit", 50)), 200)
        query = {}
        if book_id:
            query["book_id"] = str(book_id)

        cur = _reviews.find(query).sort("created_at", -1).limit(limit)
        items = [_string_id(x) for x in cur]
        return jsonify({"reviews": items}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/reviews', methods=['POST'])
@log_time
def mongo_add_review():
    """
    Accepts either:
      { book_id, reviewer, rating, text }
    or
      { book_title, reviewer, rating, text }  # resolves to book_id server-side
    """
    try:
        if _reviews is None:
            return jsonify({"error": "MongoDB not available"}), 500

        data = request.get_json(silent=True) or {}
        raw_id = str((data.get("book_id") or "")).strip()
        title = (data.get("book_title") or "").strip()

        if not raw_id and title:
            raw_id = _book_id_from_title_ci(title) or ""

        reviewer = (data.get("reviewer") or "").strip()
        text = (data.get("text") or "").strip()
        rating = data.get("rating")

        if not raw_id or not reviewer or rating is None:
            return jsonify({"error": "book_title/book_id, reviewer, and rating are required"}), 400
        try:
            rating = int(rating)
        except Exception:
            return jsonify({"error": "rating must be an integer"}), 400
        if rating < 1 or rating > 5:
            return jsonify({"error": "rating must be between 1 and 5"}), 400

        doc = {
            "book_id": str(raw_id),
            "reviewer": reviewer,
            "text": text,
            "rating": rating,
            "created_at": datetime.utcnow(),
        }
        res = _reviews.insert_one(doc)
        doc["_id"] = str(res.inserted_id)
        return jsonify({"ok": True, "review": doc}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/reviews/<rid>', methods=['DELETE'])
def mongo_delete_review(rid):
    try:
        if _reviews is None:
            return jsonify({"error": "MongoDB not available"}), 500
        oid = _oid(rid)
        if oid is None:
            return jsonify({"error": "invalid review id"}), 400
        _reviews.delete_one({"_id": oid})
        return jsonify({"ok": True}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ---------------- MongoDB Aggregations ----------------

@app.route('/api/reviews/avg', methods=['GET'])
@log_time
def mongo_avg_for_book():
    """
    GET /api/reviews/avg?book_id=123
    GET /api/reviews/avg?title=Clean%20Code
    """
    try:
        if _reviews is None:
            return jsonify({"error": "MongoDB not available"}), 500

        book_id = (request.args.get('book_id') or "").strip()
        title = (request.args.get('title') or "").strip()
        if not book_id and title:
            book_id = _book_id_from_title_ci(title) or ""

        if not book_id:
            return jsonify({"error": "book_id or title required"}), 400

        pipeline = [
            {"$match": {"book_id": str(book_id)}},
            {"$group": {"_id": "$book_id", "avg": {"$avg": "$rating"}, "count": {"$count": {}}}}
        ]
        agg = list(_reviews.aggregate(pipeline))
        if not agg:
            return jsonify({"book_id": str(book_id), "avg_rating": None, "count": 0}), 200

        out = {"book_id": agg[0]["_id"], "avg_rating": round(float(agg[0]["avg"]), 2), "count": agg[0]["count"]}
        return jsonify(out), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/reviews/top', methods=['GET'])
def mongo_top_rated():
    """
    Returns top-rated books with average ratings and review counts,
    including titles from the SQLite Books table.
    """
    try:
        if _reviews is None:
            return jsonify({"error": "MongoDB not available"}), 500

        limit = max(1, min(int(request.args.get("limit", 3)), 50))
        min_reviews = max(1, int(request.args.get("min_reviews", 1)))

        # Aggregate in MongoDB
        pipeline = [
            {"$group": {"_id": "$book_id", "avg": {"$avg": "$rating"}, "count": {"$count": {}}}},
            {"$match": {"count": {"$gte": min_reviews}}},
            {"$sort": {"avg": -1, "count": -1}},
            {"$limit": limit}
        ]
        rows = list(_reviews.aggregate(pipeline))

        # Fetch corresponding titles from SQLite
        conn = sqlite3.connect(DATABASE)
        cur = conn.cursor()
        out = []
        for r in rows:
            book_id = r["_id"]
            cur.execute("SELECT title FROM Books WHERE book_id = ?", (book_id,))
            title_row = cur.fetchone()
            title = title_row[0] if title_row else f"Book {book_id}"
            out.append({
                "book_id": book_id,
                "title": title,
                "avg_rating": round(float(r["avg"]), 2),
                "count": r["count"]
            })
        conn.close()
        return jsonify(out), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500



# ------------------------------- HTML pages ----------------------------------

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/reviews.html')
def reviews_page():
    return render_template('reviews.html')

if __name__ == '__main__':
    app.run()


