-- ========================================================
-- Task 3.3 Database Tools - Card Insights & Transfer Usage SQL Queries
-- Tool: DataGrip / PostgreSQL / SQLite
-- ========================================================

-- 1. Find duplicate cards (grouped by card_number)
SELECT card_number, COUNT(*) as count
FROM cards
GROUP BY card_number
HAVING COUNT(*) > 1;

-- 2. List all active cards
SELECT id, card_number, expire, phone, balance, created_at
FROM cards
WHERE status = 'active'
ORDER BY created_at DESC;

-- 3. Find cards with balance > 1000 UZS
SELECT id, card_number, phone, status, balance
FROM cards
WHERE balance > 1000.00
ORDER BY balance DESC;

-- 4. Find cards with balance < 1000 UZS
SELECT id, card_number, phone, status, balance
FROM cards
WHERE balance < 1000.00
ORDER BY balance ASC;

-- 5. Filter cards by phone starting with +99850
SELECT id, card_number, phone, status, balance
FROM cards
WHERE phone LIKE '+99850%' OR phone LIKE '99850%';

-- ========================================================
-- Transfer Usage Insights
-- ========================================================

-- 6. Count cards used in transfers (as sender or receiver)
SELECT COUNT(DISTINCT card_number) AS cards_used_in_transfers
FROM cards
WHERE card_number IN (
    SELECT sender_card_number FROM transfers
    UNION
    SELECT receiver_card_number FROM transfers
);

-- 7. Count cards not used in any transfer
SELECT COUNT(*) AS cards_not_used_in_transfers
FROM cards
WHERE card_number NOT IN (
    SELECT sender_card_number FROM transfers
    UNION
    SELECT receiver_card_number FROM transfers
);

-- 8. Count unique phones (with cards) that executed transfers as sender
SELECT COUNT(DISTINCT c.phone) AS unique_sender_phones
FROM cards c
JOIN transfers t ON c.card_number = t.sender_card_number
WHERE c.phone IS NOT NULL AND c.phone != '';

-- 9. Detailed summary of transfers with sender and receiver info
SELECT 
    t.ext_id,
    t.sender_card_number,
    t.receiver_card_number,
    t.sending_amount,
    t.currency,
    t.receiving_amount,
    t.state,
    t.created_at,
    t.confirmed_at
FROM transfers t
ORDER BY t.created_at DESC;
