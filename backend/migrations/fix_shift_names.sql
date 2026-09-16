-- ==========================================
-- ИСПРАВЛЕНИЕ: пересоздать смены с корректными именами
-- ==========================================
-- Проблема: при применении add_06.sql через `Get-Content | docker exec`
-- кириллица в имени смены ("Смена") была испорчена в "?????".
--
-- Причина: PowerShell с $OutputEncoding = us-ascii заменяет кириллицу
-- на "?" при передаче через pipe.
--
-- Решение: применить файл через `docker cp` + `psql -f`, минуя pipe.
-- ==========================================

DO $$
DECLARE
v_org_id UUID := '00000000-0000-0000-0000-000000000001';
    v_date DATE := '2026-09-01';
    v_end_date DATE := '2026-09-30';
    v_starts_at TIMESTAMPTZ;
    v_ends_at TIMESTAMPTZ;
    v_dow INT;
    v_name VARCHAR(50);
    v_is_working BOOLEAN;
BEGIN
    -- 1. Удаляем старые смены (с испорченными именами)
DELETE FROM shift WHERE organization_id = v_org_id
                    AND starts_at >= '2026-09-01 00:00:00+03'
                    AND starts_at < '2026-10-01 00:00:00+03';

-- 2. Создаём заново с корректными именами
WHILE v_date <= v_end_date LOOP
        v_dow := EXTRACT(DOW FROM v_date);

        v_starts_at := (v_date::text || ' 08:00:00+03')::TIMESTAMPTZ;
        v_ends_at   := (v_date::text || ' 20:00:00+03')::TIMESTAMPTZ;

        v_is_working := (v_dow <> 0 AND v_dow <> 6);
        v_name := 'Смена ' || TO_CHAR(v_date, 'DD.MM.YYYY');

INSERT INTO shift (organization_id, name, starts_at, ends_at, is_working, comment)
VALUES (
           v_org_id,
           v_name,
           v_starts_at,
           v_ends_at,
           v_is_working,
           CASE WHEN v_is_working THEN 'Рабочая смена' ELSE 'Выходной' END
       );

v_date := v_date + 1;
END LOOP;

    RAISE NOTICE 'Пересоздано смен: %',
        (SELECT COUNT(*) FROM shift WHERE organization_id = v_org_id
            AND starts_at >= '2026-09-01 00:00:00+03'
            AND starts_at < '2026-10-01 00:00:00+03');
END $$;

-- ==========================================
-- ПРОВЕРКА
-- ==========================================
SELECT name, LENGTH(name) AS len, OCTET_LENGTH(name) AS bytes,
       ENCODE(name::bytea, 'hex') AS hex
FROM shift
WHERE organization_id = '00000000-0000-0000-0000-000000000001'
  AND starts_at >= '2026-09-16'
  AND starts_at < '2026-09-17';

-- Ожидаемо:
--   name              | len | bytes | hex
-- --------------------+-----+-------+------------------------------------------
--   Смена 16.09.2026  |  17 |    21 | d0a1d0bcd0b5d0bdd0b02031362e30392e32303236
--
-- len=17 (5 кириллических + пробел + 10 цифр)
-- bytes=21 (5×2 + 1 + 10)
-- hex начинается с d0a1 (С в UTF-8)