# Scraper Health Monitoring — Strategic Plan
<!-- Chat · 2026-03-19 -->
<!-- Handoff: drop this file in project root, open Claude Code -->

## Goal

Detectar degradación o rotura de scrapers (JobSpy, ATS, WTTJ) antes de que el usuario note ausencia de jobs en el digest. Diagnosticar la causa (0 results, HTTP error, schema drift, low yield) y alertar por tres canales: PostHog, GHA annotations, email directo.

## Decisions

| # | What | Choice | Trade-off |
|---|------|--------|-----------|
| D1 | Thresholds | Fijos por source en constantes Python | Sin adaptación automática a tendencias; suficiente para 4 usuarios |
| D2 | Granularidad | Per-source (linkedin, indeed, glassdoor, greenhouse, lever, ashby, wttj), evaluado AGREGADO across profiles | No per-query; un perfil de nicho con 0 LinkedIn es normal, TODOS con 0 LinkedIn es rotura |
| D3 | Schema drift detection | Field completeness % + median description length por source | No detecta cambios semánticos, pero cubre tanto campos missing como stubs ("See full description on LinkedIn") |
| D4 | Email alert | Reutilizar notifier.py con template separado (no mezclar con digest) | Un email más; pero el digest no debe contaminarse con alertas ops |
| D5 | GHA alert | Annotations warning per-profile; exit 1 solo al FINAL del workflow si ALL sources critical para ALL profiles | Nunca interrumpe perfiles pendientes; acumula reports |
| D6 | Dónde vive la lógica | Nuevo módulo `agent/scraper_health.py` | Separado de pipeline.py para no inflarlo más (ya 500 líneas) |
| D7 | Cuándo se evalúa | Dos fases: (1) per-profile post-scrape: recolectar ScraperMeta + emitir PostHog event, (2) post-loop agregado: evaluar across profiles para email + GHA annotation | Per-profile data para diagnóstico fino; alertas solo con evidencia cross-profile para evitar false positives de nicho |

## Scope

### MVP

- Cada scraper retorna metadata estructurada junto a los jobs: count, errors (lista de strings), HTTP status codes, duración
- `scraper_health.py` recibe metadata de todos los scrapers, evalúa thresholds, genera un HealthReport
- HealthReport contiene: per-source status (ok/warning/critical), diagnostic category (zero_results, http_error, low_count, schema_drift, timeout), field completeness por source, median_description_chars por source
- Schema drift: para cada source, % de jobs con description no vacía, % con location no vacía, % con company no vacía. Si < 50% en campo crítico → schema_drift warning. Adicionalmente, median description length < 100 chars → schema_drift warning (detecta stubs)
- Health evaluation en dos fases: (1) per-profile: recolectar ScraperMeta + emitir PostHog `scraper_health_check` con datos crudos por source, (2) post-loop: agregar reports across profiles, emitir PostHog `scraper_health_report` agregado, decidir email + GHA annotations
- Lógica de alerting agregado: source es critical solo si fue critical (0 jobs o 100% error) para TODOS los perfiles que la usan. Si solo falla para un perfil → warning en PostHog, no email
- GHA: si alguna source es critical agregado → `::warning` annotation. Si TODAS critical agregado → exit 1. Exit solo al final del workflow, nunca dentro del loop de perfiles
- Email: si alguna source es critical agregado → email a ADMIN_EMAIL con diagnóstico (reutilizar SMTP de notifier.py). Best-effort: si SMTP falla, log error pero no bloquear pipeline
- Thresholds configurables como dict en scraper_health.py: `{"linkedin": {"min_jobs": 3, "min_description_pct": 0.5, "min_median_desc_chars": 100}, ...}`
- Firma de scrapers: las funciones existentes NO cambian firma. Nueva función wrapper o ScraperMeta se recolecta en `_scrape_all` midiendo los resultados post-llamada (count, field stats). Errores capturados del try/except existente se pasan al health checker

### Post-MVP

- Rolling average 7d en DB para thresholds adaptativos
- Auto-disable de source rota (skip scraper, anotar en digest que falta una fuente)
- Dashboard de salud de scrapers en web UI
- Alertas de recuperación (source que vuelve a funcionar)

### Out

- Anomaly detection estadístico
- Auto-retry con backoff
- Monitoreo per-company en ATS watchlist
- Tests e2e contra scrapers reales (dependen de servicios externos)

## Acceptance Criteria

1. Given LinkedIn devuelve 0 jobs para TODOS los perfiles activos, when post-loop health aggregation evalúa, then PostHog recibe `scraper_health_report` con linkedin.status=critical y linkedin.diagnostic=zero_results, GHA muestra warning annotation, email enviado a admin
2. Given LinkedIn devuelve 0 jobs para 1 perfil pero >0 para otros, when post-loop health aggregation evalúa, then linkedin.status=ok agregado, PostHog per-profile muestra warning, NO email enviado
3. Given WTTJ devuelve 20 jobs pero median description length < 100 chars, when health check evalúa, then wttj.diagnostic=schema_drift con wttj.median_desc_chars reportado
4. Given ATS scraper lanza ConnectionError, when pipeline continúa, then greenhouse.diagnostic=http_error con el mensaje de error capturado en ScraperMeta
5. Given todos los scrapers devuelven jobs sobre threshold para todos los perfiles, when health check evalúa, then no se envía email ni annotation warning
6. Given todos los scrapers son critical agregado, when workflow termina, then GHA exit code 1 (al final, no dentro del loop)
7. Given un source está en warning pero no critical, when pipeline completa, then PostHog event registra el warning pero no se envía email
8. Given SMTP falla al enviar alerta, when health alerting ejecuta, then error se logea con structlog pero pipeline no falla

## Boundaries

- Modules touched: `agent/scraper.py` (NO signature change), `agent/ats_scraper.py` (NO signature change), `agent/wttj_scraper.py` (NO signature change), `agent/pipeline.py` (recolectar metadata en _scrape_all + invocar health post-loop), `agent/notifier.py` (nueva función alert email), `agent/models.py` (ScraperMeta dataclass), `.github/workflows/jobagent_daily.yml` (post-loop health + exit logic)
- Invariants to respect: zero-import api↔agent, scraper try/except no debe dejar de capturar errores (backward compat), pipeline sigue funcionando si health module falla, firmas de scrapers existentes NO cambian
- Dual-copies in scope: ninguna (todo en agent/)
- New invariants introduced: `_scrape_all` construye ScraperMeta midiendo resultados post-llamada (count de jobs retornados, field stats sobre RawJob list, errores capturados del except). `run_watchlist_scraper` sigue retornando `(list[RawJob], int)`. Health alerting (email + GHA) NUNCA falla el pipeline; solo PostHog + structlog

## Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| Email alerts ruidosos por variación normal de yield | M | Alerting agregado cross-profile elimina false positives de nicho; thresholds conservadores iniciales (min 3 no 5) |
| JobSpy upstream cambia API interna | H | Exactamente lo que este sistema detecta; pero el fix sigue siendo manual |
| Health check adds latency to pipeline | L | Field stats son O(n) sobre lista ya en memoria; negligible vs scraping/scoring |
| GHA post-loop health necesita persistir reports entre profile iterations | M | Escribir JSON por perfil en directorio temporal; leer todos al final |

## Open Questions

- ¿`notifier.py` ya tiene una función genérica de envío SMTP o está acoplada al digest template? (Code debe verificar)
- ¿Existe un ADMIN_EMAIL en env vars o hay que añadirlo?
- ¿El loop de perfiles en GHA es bash inline o invoca `main.py` que retorna? Code debe determinar la mejor forma de persistir health reports entre iteraciones (fichero JSON temporal vs stdout parsing)
