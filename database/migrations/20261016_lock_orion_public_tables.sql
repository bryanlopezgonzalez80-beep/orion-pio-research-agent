-- Orion production hardening: block direct Supabase API access to private tables.
-- The Orion API connects as postgres (via the Supabase pooler); postgres and
-- service_role were verified to have BYPASSRLS. The public Site uses Orion API,
-- not direct Supabase/PostgREST access, so anon/authenticated need no table grants
-- or policies. With RLS enabled and no policies, those roles fail closed.
REVOKE ALL PRIVILEGES ON TABLE
  public.clients,
  public.generated_assets,
  public.orion_alerts,
  public.orion_collection_items,
  public.orion_collections,
  public.orion_enrichment_queue,
  public.orion_harvest_checkpoints,
  public.orion_search_cache,
  public.orion_search_history,
  public.orion_settings,
  public.orion_source_health,
  public.orion_source_metrics,
  public.paper_external_ids,
  public.papers,
  public.projects,
  public.proposals,
  public.radar_runs,
  public.survey_questions,
  public.survey_responses,
  public.surveys
FROM anon, authenticated;

ALTER TABLE public.clients ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.generated_assets ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.orion_alerts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.orion_collection_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.orion_collections ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.orion_enrichment_queue ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.orion_harvest_checkpoints ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.orion_search_cache ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.orion_search_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.orion_settings ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.orion_source_health ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.orion_source_metrics ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.paper_external_ids ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.papers ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.projects ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.proposals ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.radar_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.survey_questions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.survey_responses ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.surveys ENABLE ROW LEVEL SECURITY;

-- Prevent future postgres-owned tables in public from receiving API-role grants.
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
  REVOKE ALL PRIVILEGES ON TABLES FROM anon, authenticated;
