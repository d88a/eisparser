BEGIN;

WITH old AS (
  SELECT reg_number
  FROM zakupki
  WHERE (
    CASE
      WHEN bid_end_date ~ '^\d{4}-\d{2}-\d{2}$' THEN bid_end_date::date
      WHEN bid_end_date ~ '^\d{2}\.\d{2}\.\d{4}$' THEN to_date(bid_end_date, 'DD.MM.YYYY')
      ELSE NULL
    END
  ) + INTERVAL '10 day' < now()
)
DELETE FROM listings l USING old o WHERE l.zakupka_reg_number = o.reg_number;

WITH old AS (
  SELECT reg_number
  FROM zakupki
  WHERE (
    CASE
      WHEN bid_end_date ~ '^\d{4}-\d{2}-\d{2}$' THEN bid_end_date::date
      WHEN bid_end_date ~ '^\d{2}\.\d{2}\.\d{4}$' THEN to_date(bid_end_date, 'DD.MM.YYYY')
      ELSE NULL
    END
  ) + INTERVAL '10 day' < now()
)
DELETE FROM ai_results a USING old o WHERE a.reg_number = o.reg_number;

WITH old AS (
  SELECT reg_number
  FROM zakupki
  WHERE (
    CASE
      WHEN bid_end_date ~ '^\d{4}-\d{2}-\d{2}$' THEN bid_end_date::date
      WHEN bid_end_date ~ '^\d{2}\.\d{2}\.\d{4}$' THEN to_date(bid_end_date, 'DD.MM.YYYY')
      ELSE NULL
    END
  ) + INTERVAL '10 day' < now()
)
DELETE FROM zakupki z USING old o WHERE z.reg_number = o.reg_number;

COMMIT;
