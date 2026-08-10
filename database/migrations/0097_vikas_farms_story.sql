-- The public farm profile consumes summary/body/methods from story_json.
UPDATE farms
SET story_json = json_object(
      'summary', 'Vikas Farms is True Grit''s farm partner for traditional wheat, pulses, seeds and cold-pressed oils.',
      'body', 'Vikas Farms grows and handles the traditional ingredients in True Grit''s catalogue with careful crop selection, patient small-batch work and practical traceability from the field to the packed food. The range brings together distinctive wheat varieties, pulses, seeds and oils chosen for everyday Indian kitchens.',
      'methods', json('["Organic cultivation with careful crop and soil management","Small-batch milling, roasting and cold pressing","Traditional grain and oilseed handling with batch traceability"]')
    ),
    updated_at = '2026-08-09T12:00:00Z',
    updated_by = 'usr_catalogue_system'
WHERE id = 'farm_vikas';
