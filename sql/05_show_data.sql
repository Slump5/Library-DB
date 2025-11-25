-- Shows each table population
SELECT COUNT(*) AS students   FROM Students;
SELECT COUNT(*) AS books      FROM Books;
SELECT COUNT(*) AS librarians FROM Librarians;
SELECT COUNT(*) AS loans      FROM Loans;
SELECT COUNT(*) AS fines      FROM Fines;

-- Shows each table's data
SELECT * FROM Students   ORDER BY student_id;
SELECT * FROM Books      ORDER BY book_id;
SELECT * FROM Librarians ORDER BY librarian_id;
SELECT * FROM Loans      ORDER BY loan_id;
SELECT * FROM Fines      ORDER BY fine_id;