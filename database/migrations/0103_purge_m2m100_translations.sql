-- 0103_purge_m2m100_translations: delete every machine translation produced by
-- `@cf/meta/m2m100-1.2b`, so the affected locales fall back to English.
--
-- WHAT WENT WRONG. `backfill-entity-translations.mjs` and
-- `backfill-page-translations.mjs` sent most locales through M2M100-1.2B, a
-- small 2020-era translation model, and wrote whatever came back with no
-- quality check. Verified live on www.truegritin.com on 2026-08-16:
--
--   /category/daliya            -> "डैडी - टॉयलेट"            ("Daddy - Toilet")
--   /product/kathiya-wheat-flour-> "_KKathiya ग्रीनहाउस"       ("...greenhouse")
--   /recipes/suji-upma          -> "Suji Upma रस्सी"           ("...rope")
--   /recipes/til-ladoo          -> "रसोई के लिए रसोई के लिए..." ("kitchen for kitchen...")
--   /recipes/whole-masoor-curry-2 -> "... - ट्रिब्रेंड"        (brand mangled)
--
-- Until migration 0102's companion locale fix, every visitor on an Indian IP
-- was served this by default, whatever their browser asked for.
--
-- WHY DELETE RATHER THAN REPAIR. The mechanical damage (decoder loops, chewed
-- brand placeholders) is detectable and now blocked at write time by
-- `scripts/lib/translation-quality.mjs`. The wrong-sense damage is not: "Daliya"
-- to "Daddy - Toilet" is fluent, correctly scripted and the right length. There
-- is no way to tell a good M2M100 row from a bad one without re-translating it,
-- so the whole generation goes. An English page is always readable; a page
-- offering "Daddy - Toilet" in the grains aisle is not.
--
-- WHAT SURVIVES. Rows with `auto_translated = 0` are human-entered or
-- human-reviewed and are never touched. Locales listed below went through the
-- instruction-following model rather than M2M100 -- M2M100 rejected these
-- language codes outright, which is why they were routed away from it -- so
-- their rows are left in place.
--
-- AFTER THIS. Re-run the backfill to regenerate. It now defaults every locale
-- to `@cf/meta/llama-3.3-70b-instruct-fp8-fast` with a food glossary, and
-- refuses to cache anything that fails the quality gate:
--   node scripts/backfill-entity-translations.mjs --locales=hi,bn,ta,mr --types=product
PRAGMA foreign_keys = ON;

DELETE FROM entity_translations
WHERE auto_translated = 1
  AND locale NOT IN (
    'as', 'kok', 'sat', 'ks', 'eu', 'doi', 'mai', 'sa', 'brx', 'te',
    'tk', 'mni', 'ky', 'tg', 'mt', 'rw', 'ny', 'ug'
  );

DELETE FROM page_content_translations
WHERE auto_translated = 1
  AND locale NOT IN (
    'as', 'kok', 'sat', 'ks', 'eu', 'doi', 'mai', 'sa', 'brx', 'te',
    'tk', 'mni', 'ky', 'tg', 'mt', 'rw', 'ny', 'ug'
  );
