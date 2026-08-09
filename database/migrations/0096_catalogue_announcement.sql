-- Keep the site-wide announcement aligned with the replacement catalogue.
UPDATE announcements
SET message = 'Explore True Grit''s complete organic catalogue — traditional grains, pulses, seeds and oils.',
    destination_path = '/shop',
    active = 1,
    updated_at = '2026-08-09T12:00:00Z'
WHERE country = 'global';
