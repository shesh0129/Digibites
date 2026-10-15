window.DIGIBITES_ALLERGEN_GUIDANCE = Object.freeze({
  'Peanuts': 'Check for peanuts, peanut butter, groundnuts, sauces, and shared utensils or equipment.',
  'Tree Nuts': 'Check for almonds, cashews, walnuts, and other tree nuts in toppings, baked goods, desserts, and shared equipment.',
  'Dairy / Milk': 'Check for milk, cheese, butter, cream, condensed or evaporated milk, and sauces. Lactose-free products may still contain milk proteins.',
  'Eggs': 'Check for eggs in mayonnaise, batters, pastries, breading, and glazes, and ask about shared cooking surfaces.',
  'Fish': 'Check for fish, fish sauce (patis), stocks, and sauces. Ask staff to verify packaged ingredients and shared preparation.',
  'Shellfish': 'Check for shrimp, crab, squid, oyster, prawns, clams, and seafood sauces. Follow the specific shellfish advice given by your healthcare professional.',
  'Wheat / Gluten': 'Check noodles, bread, flour, wrappers, marinades, and sauces. Some soy sauces contain wheat. Wheat allergy and celiac disease are different; follow your clinician’s advice.',
  'Soy': 'Soy sauce often contains soy, and some varieties also contain wheat. Check the exact label and ask staff about sauces, marinades, tofu, soy milk, and shared utensils.',
  'Sesame': 'Check seeds, tahini, sesame oil, dressings, toppings, and shared utensils or equipment.'
});

window.DIGIBITES_ESCAPE_HTML = function (value) {
  return String(value).replace(/[&<>"']/g, character => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  })[character]);
};