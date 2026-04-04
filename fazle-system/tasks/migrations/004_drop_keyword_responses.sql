-- ============================================================
-- Fazle Cleanup Migration — 004
-- Drops the legacy keyword auto-reply table.
-- Safe to run multiple times.
-- ============================================================

DROP TABLE IF EXISTS fazle_keyword_responses CASCADE;