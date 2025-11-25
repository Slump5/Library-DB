PRAGMA foreign_keys = ON;

-- Reset (child → parent to satisfy FKs)
DELETE FROM Fines;
DELETE FROM Loans;
DELETE FROM Librarians;
DELETE FROM Books;
DELETE FROM Students;

-- ---------- Students (10) ----------
WITH RECURSIVE n(i) AS (
  SELECT 1 UNION ALL SELECT i+1 FROM n WHERE i<10
)
INSERT INTO Students(name, major, email, year_of_study)
SELECT
  'Student '||i,
  CASE i%4 WHEN 0 THEN 'CS' WHEN 1 THEN 'Math' WHEN 2 THEN 'Physics' ELSE 'Biology' END,
  'student'||i||'@univ.edu',
  1 + (i%4)
FROM n;

-- ---------- Books (12) ----------
INSERT INTO Books(title, author, category, publication_year, image_url)
SELECT * FROM (VALUES
 ('Data Structures in Practice','A. Knuth','CS',2015,'https://blocks.astratic.com/img/general-img-landscape.png'),
 ('Linear Algebra Basics','C. Lewis','Math',2012,'https://blocks.astratic.com/img/general-img-landscape.png'),
 ('Modern Physics','R. Feyn','Physics',2018,'https://blocks.astratic.com/img/general-img-landscape.png'),
 ('Cell Biology Essentials','M. Ross','Biology',2016,'https://blocks.astratic.com/img/general-img-landscape.png'),
 ('Database Systems','R. Ram','CS',2020,'https://blocks.astratic.com/img/general-img-landscape.png'),
 ('Discrete Math','G. Rosen','Math',2019,'https://blocks.astratic.com/img/general-img-landscape.png'),
 ('Quantum Intro','D. Bell','Physics',2021,'https://blocks.astratic.com/img/general-img-landscape.png'),
 ('Genetics 101','S. Noble','Biology',2013,'https://blocks.astratic.com/img/general-img-landscape.png'),
 ('Operating Systems','A. Tan','CS',2018,'https://blocks.astratic.com/img/general-img-landscape.png'),
 ('Calculus Made Clear','J. Thompson','Math',2017,'https://blocks.astratic.com/img/general-img-landscape.png'),
 ('Thermodynamics','L. Maxwell','Physics',2014,'https://blocks.astratic.com/img/general-img-landscape.png'),
 ('Microbiology','H. Peters','Biology',2022,'https://blocks.astratic.com/img/general-img-landscape.png')
);

-- ---------- Librarians (10) ----------
WITH RECURSIVE m(i) AS (
  SELECT 1 UNION ALL SELECT i+1 FROM m WHERE i<10
)
INSERT INTO Librarians(name, email, shift)
SELECT
  'Librarian '||i,
  'lib'||i||'@univ.edu',
  CASE WHEN i%2=0 THEN 'evening' ELSE 'morning' END
FROM m;

-- ---------- Loans (12; half returned; includes checked_out_by) ----------
WITH RECURSIVE s(i) AS (
  SELECT 1 UNION ALL SELECT i+1 FROM s WHERE i<12
)
INSERT INTO Loans(student_id, book_id, checked_out_by, borrowed_on, due_on, returned_on)
SELECT
  ((i-1) % 10) + 1,   -- students 1..10
  ((i-1) % 12) + 1,   -- books    1..12
  ((i-1) % 10) + 1,   -- librarians 1..10
  date('now', printf('-%d day', 25 - i)),
  date('now', printf('-%d day', 17 - i)),
  CASE WHEN i % 2 = 0 THEN date('now', printf('-%d day', 15 - i)) ELSE NULL END
FROM s;

-- ---------- Fines (logic-based first) ----------
-- Unreturned & past due → unpaid fine
INSERT INTO Fines(loan_id, amount, issued_on, reason, status)
SELECT loan_id,
       5.00 + (abs(random()) % 500)/100.0,
       date('now'),
       'Overdue (not returned)',
       'unpaid'
FROM Loans
WHERE returned_on IS NULL AND due_on < date('now');

-- Returned late → unpaid fine
INSERT INTO Fines(loan_id, amount, issued_on, reason, status)
SELECT loan_id,
       3.00 + (abs(random()) % 300)/100.0,
       returned_on,
       'Returned late',
       'unpaid'
FROM Loans
WHERE returned_on IS NOT NULL AND returned_on > due_on;

-- ---------- Fines top-up: ensure total fines >= 10 ----------
WITH existing(c) AS (SELECT COUNT(*) FROM Fines),
     need(n) AS (
       SELECT 10 - c FROM existing
     ),
     gen(i) AS (
       SELECT 1 UNION ALL SELECT i+1 FROM gen WHERE i<10
     )
INSERT INTO Fines(loan_id, amount, issued_on, reason, status)
SELECT
  ((i-1) % (SELECT COUNT(*) FROM Loans)) + 1,  -- cycle through existing loans
  2.50 + (abs(random()) % 300)/100.0,
  date('now'),
  'Seed fine '||i,
  'unpaid'
FROM gen, need
WHERE n > 0 AND i <= n;
