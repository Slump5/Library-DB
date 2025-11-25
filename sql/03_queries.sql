.headers on
.mode column

-- Q1: JOIN — list active loans (not returned)
SELECT L.loan_id, S.name AS student, B.title AS book, L.borrowed_on, L.due_on, LB.name AS librarian
FROM Loans L
JOIN Students   S  ON S.student_id    = L.student_id
JOIN Books      B  ON B.book_id       = L.book_id
LEFT JOIN Librarians LB ON LB.librarian_id = L.checked_out_by
WHERE L.returned_on IS NULL
ORDER BY L.due_on;

-- Q2: Aggregation — books per category
SELECT category, COUNT(*) AS num_books
FROM Books
GROUP BY category
ORDER BY num_books DESC, category;

-- Q3: Aggregation + HAVING — students with 2+ total loans
SELECT S.student_id, S.name, COUNT(*) AS loans_count
FROM Loans L
JOIN Students S ON S.student_id = L.student_id
GROUP BY S.student_id, S.name
HAVING COUNT(*) >= 2
ORDER BY loans_count DESC, S.name;

-- Q4: SUM of unpaid fines per student
SELECT S.student_id, S.name,
       ROUND(COALESCE(SUM(CASE WHEN F.status='unpaid' THEN F.amount END),0),2) AS total_unpaid
FROM Students S
LEFT JOIN Loans L ON L.student_id = S.student_id
LEFT JOIN Fines F ON F.loan_id = L.loan_id
GROUP BY S.student_id, S.name
ORDER BY total_unpaid DESC, S.name;

-- Q5: Librarian productivity — loans processed per librarian
SELECT LB.librarian_id, LB.name, LB.shift, COUNT(L.loan_id) AS loans_processed
FROM Librarians LB
LEFT JOIN Loans L ON L.checked_out_by = LB.librarian_id
GROUP BY LB.librarian_id, LB.name, LB.shift
ORDER BY loans_processed DESC, LB.name;

-- Q6a (DML - Update): show one unpaid fine we'll update
SELECT 'BEFORE UPDATE' AS stage, fine_id, status
FROM Fines
WHERE status='unpaid'
ORDER BY fine_id
LIMIT 1;

-- Q6b (DML - Update): UPDATE a fine -> RETURNING shows the changed row
UPDATE Fines
SET status='paid'
WHERE fine_id = (SELECT fine_id FROM Fines WHERE status='unpaid' LIMIT 1)
RETURNING 'UPDATED' AS stage, fine_id, status;

-- Q7a (DML - Insert): show first active loan (not yet returned)
SELECT 'BEFORE RETURN' AS stage, loan_id, borrowed_on, due_on, returned_on
FROM Loans
WHERE returned_on IS NULL
LIMIT 1;

-- Q7b (DML - Insert): UPDATE the loan to returned today -> RETURNING shows the updated loan
UPDATE Loans
SET returned_on = date('now','localtime')
WHERE loan_id = (SELECT loan_id FROM Loans WHERE returned_on IS NULL LIMIT 1)
RETURNING 'UPDATED LOAN' AS stage, loan_id, borrowed_on, due_on, returned_on;

-- Q7c (DML - Insert): INSERT a late fee IF the return was after due date -> RETURNING shows the new fine
INSERT INTO Fines(loan_id, amount, issued_on, reason, status)
SELECT loan_id, 7.50, date('now','localtime'), 'Manual late fee', 'unpaid'
FROM Loans
WHERE loan_id = (SELECT loan_id FROM Loans ORDER BY loan_id DESC LIMIT 1)
  AND returned_on > due_on
RETURNING 'INSERTED FINE' AS stage, fine_id, loan_id, amount, status;




