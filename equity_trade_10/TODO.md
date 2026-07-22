# Task: Fix autocomplete click/navigation

## Plan
Replace inline `onclick`/`onmouseenter` handlers on autocomplete dropdown items with **event delegation** to fix click/navigation issues.

## Files to Edit
1. **templates/dashboard.html** — 2 autocomplete instances (Dashboard Search + Watchlist Add Stock)
2. **templates/chart.html** — 1 autocomplete instance (Chart Stock Search)
3. **templates/watchlist_detail.html** — 1 autocomplete instance (Watchlist Add Stock)

## Progress

- [x] Analyze codebase and create plan
- [x] Edit templates/dashboard.html - Dashboard Search dropdown
- [x] Edit templates/dashboard.html - Watchlist Add Stock dropdown  
- [x] Edit templates/chart.html - Chart Search dropdown
- [x] Edit templates/watchlist_detail.html - Add Stock dropdown
- [x] Fix: Watchlist Add Stock event delegation — listeners were attached to stale DOM reference. Moved into `setupWlDropdownEvents()` and called from `initWlAutocomplete()` so they bind to the fresh `#wlSearchDropdown` element created by `selectWatchlist()`.
- [x] All edits completed successfully

