PRAGMA foreign_keys = ON;

-- Students
CREATE TABLE IF NOT EXISTS Students (
  student_id     INTEGER PRIMARY KEY,
  name           TEXT    NOT NULL,
  major          TEXT,
  email          TEXT    NOT NULL UNIQUE,
  year_of_study  INTEGER CHECK (year_of_study BETWEEN 1 AND 8)
);


-- Books
CREATE TABLE IF NOT EXISTS Books (
  book_id           INTEGER PRIMARY KEY,
  title             TEXT NOT NULL,
  author            TEXT NOT NULL,
  category          TEXT,
  publication_year  INTEGER CHECK (publication_year BETWEEN 1400 AND 2100),
  image_url         TEXT               -- Added for Flask UI (book covers)
);


-- Librarians
CREATE TABLE IF NOT EXISTS Librarians (
  librarian_id  INTEGER PRIMARY KEY,
  name          TEXT NOT NULL,
  email         TEXT NOT NULL UNIQUE,
  shift         TEXT NOT NULL CHECK (shift IN ('morning','evening'))
);


-- Loans
CREATE TABLE IF NOT EXISTS Loans (
  loan_id        INTEGER PRIMARY KEY,
  student_id     INTEGER NOT NULL REFERENCES Students(student_id)   ON DELETE CASCADE,
  book_id        INTEGER NOT NULL REFERENCES Books(book_id)         ON DELETE CASCADE,
  checked_out_by INTEGER     REFERENCES Librarians(librarian_id)    ON DELETE SET NULL,
  borrowed_on    DATE    NOT NULL DEFAULT (date('now')),
  due_on         DATE    NOT NULL,
  returned_on    DATE,
  CHECK (due_on >= borrowed_on)
);

CREATE INDEX IF NOT EXISTS idx_loans_book_return ON Loans(book_id, returned_on);
CREATE INDEX IF NOT EXISTS idx_loans_student ON Loans(student_id);
CREATE INDEX IF NOT EXISTS idx_loans_librarian ON Loans(checked_out_by);


-- Fines
CREATE TABLE IF NOT EXISTS Fines (
  fine_id    INTEGER PRIMARY KEY,
  loan_id    INTEGER NOT NULL REFERENCES Loans(loan_id) ON DELETE CASCADE,
  amount     NUMERIC NOT NULL CHECK (amount >= 0),
  issued_on  DATE    NOT NULL DEFAULT (date('now')),
  reason     TEXT,
  status     TEXT    NOT NULL DEFAULT 'unpaid' CHECK (status IN ('unpaid','paid','waived'))
);


-- Trigger: Prevent double checkout of same book
CREATE TRIGGER IF NOT EXISTS trg_block_double_checkout
BEFORE INSERT ON Loans
FOR EACH ROW
BEGIN
  SELECT CASE WHEN EXISTS (
    SELECT 1 FROM Loans
    WHERE book_id = NEW.book_id
      AND returned_on IS NULL
  )
  THEN RAISE(ABORT, 'Book is already on loan')
  END;
END;
