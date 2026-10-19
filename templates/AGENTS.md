# Project agent contract

Before making changes, inspect the actual project and choose the smallest relevant KStack skill set. Prefer tested implementations over broad rewrites. Maintain current behaviour unless deliberately changing it; state risk, failure paths and test criteria. Use local verification when GitHub Actions is unavailable, and distinguish actual test results from missing environmental acceptance. Push/merge only when explicitly authorised and after required checks.

Project-specific build, test and deploy commands go **below** this paragraph. No global skill overrides a project's security restrictions.
