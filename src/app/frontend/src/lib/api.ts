// Cliente del backend del Centro de Inteligencia.
const BASE = '';

async function jsonFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
    ...init,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`${res.status} ${res.statusText}: ${text}`);
  }
  return res.json() as Promise<T>;
}

// ---- Tipos --------------------------------------------------------------
/** El fabricante que contrata el estudio; lo fija la variable `cliente` del bundle. */
export type AppConfig = {
  cliente: string;
};

export type Kpis = {
  observaciones: number;
  pdv_visitados: number;
  paises: number;
  disponibilidad_pct: number;
  ejecucion_pct: number;
  planograma_pct: number;
  sos_cliente_pct: number;
  quiebres: number;
  promo_pct: number;
  obs_por_min: number;
  window_min: number;
};

export type Visita = {
  visita_id: string;
  store_id: string;
  tienda: string | null;
  sku: string;
  producto: string | null;
  emoji: string | null;
  marca: string;
  fabricante: string;
  categoria: string;
  cadena: string;
  canal: string;
  ciudad: string;
  country_code: string;
  facings: number;
  precio_usd: number | null;
  en_stock: boolean;
  en_promo: boolean;
  planograma_ok: boolean;
  ejecucion_perfecta: boolean;
  share_of_shelf: number;
  confianza_ir: number;
  es_cliente: boolean;
  visit_ts: string;
};

export type TimelinePoint = {
  minute_ts: string;
  observaciones: number;
  disponibilidad_pct: number;
  ejecucion_pct: number;
  por_categoria: Record<
    string,
    { disponibilidad_pct: number; ejecucion_pct: number; observaciones: number }
  >;
};
export type VisitasTimeline = { categorias: string[]; puntos: TimelinePoint[] };

export type SkuCritico = {
  sku: string;
  producto: string | null;
  emoji: string | null;
  marca: string;
  categoria: string;
  subcategoria: string | null;
  observaciones: number;
  quiebres: number;
  pdv_afectados: number;
  disponibilidad_pct: number;
  planograma_pct: number;
  facings_prom: number;
  precio_usd_prom: number;
};

export type CategoriaCorte = {
  categoria: string;
  observaciones: number;
  pdv: number;
  disponibilidad_pct: number;
  ejecucion_pct: number;
  sos_cliente_pct: number;
  quiebres: number;
};

export type PaisCorte = {
  country_code: string;
  pais: string;
  region_dn: string | null;
  observaciones: number;
  pdv: number;
  disponibilidad_pct: number;
  ejecucion_pct: number;
  sos_cliente_pct: number;
  ejecucion_moderno_pct: number;
  ejecucion_tradicional_pct: number;
};

export type EstadoTraslado = 'propuesto' | 'aprobado' | 'descartado' | 'vencido';

/** Un movimiento de mercadería entre dos PDV que el agente propone y un humano aprueba. */
export type Traslado = {
  traslado_id: string;
  sku: string;
  producto: string | null;
  marca: string | null;
  categoria: string | null;
  country_code: string | null;
  origen_id: string;
  origen_nombre: string | null;
  origen_ciudad: string | null;
  origen_lat: number | null;
  origen_lon: number | null;
  destino_id: string;
  destino_nombre: string | null;
  destino_ciudad: string | null;
  destino_lat: number | null;
  destino_lon: number | null;
  distancia_km: number;
  unidades: number;
  venta_recuperada_usd: number;
  costo_logistico_usd: number;
  ganancia_neta_usd: number;
  estado: EstadoTraslado;
  decidido_por: string | null;
  decidido_en: string | null;
  propuesto_en: string | null;
};

export type ResumenTraslados = Record<
  EstadoTraslado,
  {
    traslados: number;
    ganancia_usd: number;
    venta_usd: number;
    unidades: number;
    km_promedio: number;
  }
>;

export type Severity = 'low' | 'medium' | 'high' | 'critical';

export type Recomendacion = {
  id: string;
  agent_name: string;
  severity: Severity;
  title: string;
  analysis: string;
  recommendation: string;
  suggested_action: any;
  supporting_data: any;
  created_at: string;
  status: 'pending' | 'approved' | 'rejected';
  decision: { action: string; actor: string; notes?: string; occurred_at: string } | null;
};

export type BrechaPrecio = {
  sku: string;
  producto: string | null;
  emoji: string | null;
  marca: string;
  categoria: string;
  subcategoria: string;
  country_code: string;
  cadena: string;
  precio_usd: number;
  indice_precio: number;
  en_promo: boolean;
  marca_rival: string | null;
  fabricante_rival: string | null;
  precio_rival_usd: number | null;
};

export type PrecioCategoria = {
  categoria: string;
  indice_cliente: number;
  indice_competencia: number;
  brecha: number;
  promo_cliente_pct: number;
  promo_competencia_pct: number;
  skus_cliente: number;
  observaciones: number;
};

export type PrecioCadena = {
  country_code: string;
  cadena: string;
  indice_cliente: number;
  indice_competencia: number;
  brecha: number;
  skus_cliente: number;
};

export type MetaCategoria = {
  categoria: string;
  observaciones: number;
  obs_cliente: number;
  quiebres: number;
  meta_disponibilidad_pct: number;
  meta_ejecucion_pct: number;
  meta_sos_pct: number;
  disponibilidad_pct: number;
  ejecucion_pct: number;
  sos_pct: number;
  cumplimiento_pct: number;
  cumplimiento_disponibilidad_pct: number;
  cumplimiento_sos_pct: number;
  status: 'above' | 'on' | 'behind';
};

export type SkuOfensor = {
  sku: string;
  producto: string | null;
  emoji: string | null;
  marca: string | null;
  subcategoria: string | null;
  lecturas: number;
  disponibilidad_pct: number;
  planograma_pct: number;
  facings_prom: number;
  pdv_afectados: number;
  precio_sugerido_usd: number;
  brecha_pp: number;
};

export type DiagnosticoCategoria = {
  categoria: string;
  ventana_min: number;
  totales: {
    observaciones: number;
    obs_cliente: number;
    pdv_medidos: number;
    quiebres: number;
    disponibilidad_pct: number;
    ejecucion_pct: number;
    planograma_pct: number;
    sos_pct: number;
    meta_disponibilidad_pct: number;
    meta_ejecucion_pct: number;
    meta_sos_pct: number;
    brecha_ejecucion_pp: number;
    brecha_disponibilidad_pp: number;
    brecha_sos_pp: number;
    cumplimiento_pct: number;
    status: 'above' | 'on' | 'behind';
  };
  senales: {
    skus_caros: number;
    indice_promedio: number;
    posts_negativos: number;
    pdv_con_quiebre: number;
    recs_pendientes: number;
  };
  top_skus: SkuOfensor[];
  recomendaciones_activas: Array<{
    id: string;
    agent_name: string;
    severity: Severity;
    title: string;
    created_at: string;
    decidida: boolean;
  }>;
};

export type ExplainEvent =
  | { type: 'diagnosis'; data: DiagnosticoCategoria }
  | { type: 'delta'; data: { text: string } }
  | { type: 'done'; data: { elapsed_ms: number; model: string } }
  | { type: 'error'; data: { detail: string } };

export type SkuDetalle = {
  sku: string;
  categoria: string;
  producto: {
    nombre: string | null;
    marca: string | null;
    fabricante: string | null;
    subcategoria: string | null;
    presentacion: string | null;
    emoji: string | null;
    contenido_norm: number;
    unidad_norm: string | null;
    precio_sugerido_usd: number;
  };
  anaquel: {
    lecturas?: number;
    pdv?: number;
    disponibilidad_pct?: number;
    planograma_pct?: number;
    promo_pct?: number;
    facings_prom?: number;
    precio_usd_prom?: number;
  };
  serie: Array<{ minute_ts: string | null; disponibilidad_pct: number; lecturas: number }>;
  peores_pdv: Array<{
    store_id: string;
    tienda: string | null;
    cadena: string | null;
    ciudad: string | null;
    country_code: string | null;
    mercaderista: string | null;
    disponibilidad_pct: number;
    lecturas: number;
  }>;
  precio: Array<{
    country_code: string;
    cadena: string;
    precio_usd: number;
    indice_precio: number;
    en_promo: boolean;
  }>;
};

export type Pdv = {
  store_id: string;
  nombre: string;
  canal: string;
  cadena: string;
  formato: string;
  ciudad: string;
  country_code: string;
  latitude: number;
  longitude: number;
  mercaderista: string | null;
  visitas_mes_meta: number;
  observaciones: number;
  ultima_visita: string | null;
  disponibilidad_pct: number | null;
  ejecucion_pct: number | null;
  planograma_pct: number | null;
  sos_pct: number | null;
  quiebres: number;
  /** Ejecución de la mitad reciente de la ventana menos la mitad previa, en pp. */
  tendencia_pp: number | null;
  motivo: MotivoPdv;
  sku_critico: string | null;
  producto_critico: string | null;
  categoria_critica: string | null;
  estado: 'sin_medicion' | 'critico' | 'riesgo' | 'ok';
};

export type MotivoPdv =
  | 'sin_medicion'
  | 'quiebre_y_planograma'
  | 'quiebre'
  | 'planograma'
  | 'en_meta';

export type PdvDetalle = {
  pdv: {
    store_id: string;
    nombre: string;
    canal: string;
    cadena: string;
    formato: string;
    ciudad: string;
    country_code: string;
    mercaderista: string | null;
    visitas_mes_meta: number;
    pais: string | null;
    moneda: string | null;
  };
  por_categoria: Array<{
    categoria: string;
    observaciones: number;
    disponibilidad_pct: number;
    ejecucion_pct: number;
    sos_pct: number;
  }>;
  quiebres: Array<{
    sku: string;
    producto: string | null;
    emoji: string | null;
    marca: string;
    categoria: string;
    planograma_ok: boolean;
    ultima_lectura: string | null;
  }>;
};

export type AccionCampo = {
  store_id: string;
  tienda: string;
  cadena: string;
  canal: string;
  ciudad: string;
  country_code: string;
  mercaderista: string | null;
  sku: string;
  producto: string;
  emoji: string | null;
  marca: string;
  categoria: string;
  tipo_accion: 'reponer' | 'corregir_planograma' | 'ampliar_espacio';
  disponibilidad_pct: number;
  planograma_pct: number;
  facings_prom: number;
  sos_pct: number | null;
  meta_sos_pct: number | null;
  lecturas: number;
  ultima_lectura: string | null;
  impacto_usd: number;
  urgencia: 'alta' | 'media' | 'baja';
};

export type SocialPost = {
  post_id: string;
  platform: string;
  author_handle: string;
  author_followers: number | null;
  content: string;
  marca: string | null;
  fabricante: string | null;
  country_code: string | null;
  sentiment: 'positivo' | 'negativo' | 'neutral';
  sentiment_score: number;
  engagement: number;
  is_viral: boolean;
  posted_at: string;
};

export type ObjetivoCampana = 'amplificar' | 'defender' | 'lanzar';

export type Campana = {
  campana_id: string;
  post_id: string;
  nombre: string;
  marca: string | null;
  fabricante: string | null;
  categoria: string | null;
  country_code: string | null;
  objetivo: ObjetivoCampana;
  plataformas: string[];
  presupuesto_usd: number;
  alcance_estimado: number;
  engagement_base: number;
  engagement_actual?: number;
  estado: string;
  creada_por: string | null;
  creada_en?: string | null;
  contenido?: string | null;
};

export type TermometroMarca = {
  marca: string;
  fabricante: string | null;
  es_cliente: boolean;
  menciones: number;
  score: number;
  negativos_pct: number;
  positivos_pct: number;
  engagement: number;
  virales: number;
};

export type SocialCategoria = {
  categoria: string;
  menciones: number;
  score: number;
  negativos_pct: number;
  engagement: number;
  disponibilidad_pct: number | null;
};

// ---- Lakebase (copiloto de campo) ---------------------------------------
export type LakebaseStatus = {
  configured: boolean;
  host: string | null;
  database: string | null;
  schema: string;
  tables: string[];
  connected_as: string;
  postgres_version: string | null;
  counts: { pdv_perfiles: number; sugerencias_servidas: number };
  ultima_sugerencia_at: string | null;
};

export type PdvPerfil = {
  store_id: string;
  nombre: string;
  canal: string;
  cadena: string;
  formato: string;
  ciudad: string;
  country_code: string;
  pais: string | null;
  mercaderista: string | null;
  visitas_mes_meta: number;
  categorias_prioritarias: string[];
  skus_foco: string[];
  disponibilidad_hist: number;
  ejecucion_hist: number;
  sos_hist: number;
  riesgo_quiebre: number;
  ticket_categoria_usd: number;
  ultima_visita: string | null;
  sugerencias_recientes?: Array<{
    id: number;
    categoria_foco: string | null;
    skus: string[];
    rationale: string | null;
    impacto_usd: number;
    latency_ms: number;
    served_at: string | null;
  }>;
};

export type AccionSugerida = {
  sku: string;
  nombre: string | null;
  marca: string | null;
  fabricante: string | null;
  categoria: string | null;
  subcategoria: string | null;
  presentacion: string | null;
  emoji: string | null;
  precio_usd: number;
  tipo_accion: 'reponer' | 'corregir_planograma' | 'ampliar_espacio';
  impacto_usd: number;
  score: number;
  en_foco: boolean;
};

export type EscenarioVisita = {
  code: 'critico' | 'riesgo' | 'espacio' | 'mantenimiento';
  headline: string;
  narrative: string;
};

export type SugerirResult = {
  ok: boolean;
  sugerencia_id: number;
  served_at: string | null;
  latency_ms: number;
  pdv: PdvPerfil;
  categoria_foco: string | null;
  categoria_source: 'usuario' | 'perfil';
  escenario: EscenarioVisita;
  acciones: AccionSugerida[];
  impacto_usd: number;
  rationale: string;
};

/** servida = el plan llegó al celular y nadie lo tocó todavía. */
export type EstadoSugerencia = 'servida' | 'ejecutada' | 'parcial' | 'omitida';

export type SugerenciaReciente = {
  id: number;
  store_id: string;
  nombre: string;
  canal: string;
  cadena: string;
  ciudad: string;
  categoria_foco: string | null;
  skus: string[];
  impacto_usd: number;
  latency_ms: number;
  served_at: string | null;
  estado: EstadoSugerencia;
  skus_ejecutados: string[];
  impacto_ejecutado_usd: number;
  ejecutado_at: string | null;
  mercaderista: string | null;
};

export type EjecutarResult = {
  ok: boolean;
  id: number;
  estado: EstadoSugerencia;
  skus_ejecutados: string[];
  acciones_totales: number;
  impacto_ejecutado_usd: number;
  impacto_sugerido_usd: number;
  ejecutado_at: string | null;
};

export type FlujoCampo = {
  activo: boolean;
  ritmo_por_min: number;
  servidas: number;
  cerradas: number;
  errores: number;
  ultimo_error: string | null;
  segundos_activo: number;
};

export type SugerenciaDetalle = {
  id: number;
  store_id: string;
  categoria_foco: string | null;
  acciones: AccionSugerida[];
  rationale: string | null;
  impacto_usd: number;
  latency_ms: number;
  served_at: string | null;
  escenario: EscenarioVisita;
  pdv: PdvPerfil;
};

export type LakebaseStats = {
  n: number;
  mean_ms: number;
  p50_ms: number;
  p95_ms: number;
  p99_ms: number;
  min_ms: number;
  max_ms: number;
  last_5min: number;
  window_min?: number;
};

export type LakebaseImpacto = {
  sugerencias_total: number;
  sugerencias_24h: number;
  sugerencias_5min: number;
  pdv_atendidos: number;
  impacto_identificado_usd: number;
  impacto_identificado_24h_usd: number;
  recuperacion_estimada_usd: number;
  recuperacion_base_usd: number;
  uplift_usd: number;
  /** null hasta que se cierre la primera visita: sin dato no se inventa una tasa. */
  tasa_ejecucion_campo_pct: number | null;
  tasa_base_pct: number;
  visitas_cerradas: number;
  visitas_pendientes: number;
  ejecutadas: number;
  parciales: number;
  omitidas: number;
  impacto_ejecutado_usd: number;
  impacto_cerrado_usd: number;
  supuesto: string;
};

// ---- Ciclo de vida de la demo -------------------------------------------
export type DemoJob = { job_id: number; name: string; pause_status: string | null };
export type DemoStatus = {
  running: boolean;
  found: number;
  datagen: DemoJob[];
  agents: DemoJob[];
};
export type DemoActionResult = {
  ok: boolean;
  started?: Array<{ job_id: number; name: string; run_id: number }>;
  paused?: string[];
  wiped?: string[];
  errors: string[];
};

export type TablaVolumen = {
  tabla: string;
  filas: number;
  /** Minutos de ventana viva. null = la tabla solo se puede vaciar entera. */
  ventana_min: number | null;
  columna_tiempo: string | null;
};
export type DemoVolumen = {
  unity_catalog: TablaVolumen[];
  lakebase: TablaVolumen[];
  filas_total: number;
};
export type LimpiezaResult = {
  ok: boolean;
  modo: 'ventana' | 'total';
  detalle: Array<{
    tabla: string;
    modo: string;
    filas_antes?: number | null;
    filas_despues?: number;
    filas_liberadas?: number;
  }>;
  filas_liberadas: number;
  filas_restantes: number | null;
  errors: string[];
};

// ---- Endpoints ----------------------------------------------------------
export const api = {
  config: () => jsonFetch<AppConfig>('/api/config'),
  kpis: (window_min = 15) => jsonFetch<Kpis>(`/api/kpis?window_min=${window_min}`),

  demoStatus: () => jsonFetch<DemoStatus>('/api/demo/status'),
  demoStart: () => jsonFetch<DemoActionResult>('/api/demo/start', { method: 'POST', body: '{}' }),
  demoStop: (wipe = true) =>
    jsonFetch<DemoActionResult>(`/api/demo/stop?wipe=${wipe}`, { method: 'POST', body: '{}' }),
  demoVolumen: () => jsonFetch<DemoVolumen>('/api/demo/volumen'),
  demoLimpiar: (total = false) =>
    jsonFetch<LimpiezaResult>(`/api/demo/limpiar?total=${total}`, { method: 'POST', body: '{}' }),

  visitasRecientes: (limit = 200) => jsonFetch<Visita[]>(`/api/visitas/recent?limit=${limit}`),
  visitasTimeline: (window_min = 30) =>
    jsonFetch<VisitasTimeline>(`/api/visitas/timeline?window_min=${window_min}`),
  skusCriticos: (window_min = 30, limit = 10, categoria?: string) => {
    const p = new URLSearchParams({ window_min: String(window_min), limit: String(limit) });
    if (categoria) p.set('categoria', categoria);
    return jsonFetch<SkuCritico[]>(`/api/visitas/skus-criticos?${p}`);
  },
  visitasPorCategoria: (window_min = 30) =>
    jsonFetch<CategoriaCorte[]>(`/api/visitas/por-categoria?window_min=${window_min}`),
  visitasPorPais: (window_min = 30) =>
    jsonFetch<PaisCorte[]>(`/api/visitas/por-pais?window_min=${window_min}`),

  recomendaciones: (status?: string, limit = 50, agent?: string, acciones?: string) => {
    const qs = new URLSearchParams({ limit: String(limit) });
    if (status) qs.set('status', status);
    if (agent) qs.set('agent', agent);
    if (acciones) qs.set('acciones', acciones);
    return jsonFetch<Recomendacion[]>(`/api/recommendations?${qs}`);
  },
  decidir: (rec_id: string, action: 'APPROVED' | 'REJECTED', notes?: string | null) =>
    jsonFetch<{ ok: boolean }>(`/api/recommendations/${rec_id}/decide`, {
      method: 'POST',
      body: JSON.stringify({ action, notes: notes ?? null }),
    }),

  brechasPrecio: (categoria?: string, umbral = 108) => {
    const p = new URLSearchParams({ umbral: String(umbral) });
    if (categoria) p.set('categoria', categoria);
    return jsonFetch<BrechaPrecio[]>(`/api/precios/brechas?${p}`);
  },
  preciosPorCategoria: () => jsonFetch<PrecioCategoria[]>('/api/precios/por-categoria'),
  preciosPorCadena: (categoria?: string) =>
    jsonFetch<PrecioCadena[]>(
      `/api/precios/por-cadena${categoria ? `?categoria=${encodeURIComponent(categoria)}` : ''}`,
    ),

  socialRecientes: (opts: { platform?: string; marca?: string; solo_cliente?: boolean; limit?: number } = {}) => {
    const p = new URLSearchParams();
    if (opts.platform) p.set('platform', opts.platform);
    if (opts.marca) p.set('marca', opts.marca);
    if (opts.solo_cliente) p.set('solo_cliente', 'true');
    p.set('limit', String(opts.limit ?? 30));
    return jsonFetch<SocialPost[]>(`/api/social/recent?${p}`);
  },
  socialPost: (postId: string) =>
    jsonFetch<SocialPost>(`/api/social/post/${encodeURIComponent(postId)}`),
  socialVirales: (window_min = 30) =>
    jsonFetch<SocialPost[]>(`/api/social/viral?window_min=${window_min}`),
  socialTermometro: (window_min = 60) =>
    jsonFetch<TermometroMarca[]>(`/api/social/termometro?window_min=${window_min}`),
  socialPorCategoria: (window_min = 60) =>
    jsonFetch<SocialCategoria[]>(`/api/social/por-categoria?window_min=${window_min}`),

  amplificar: (
    postId: string,
    body: {
      objetivo: ObjetivoCampana;
      presupuesto_usd: number;
      plataformas: string[];
      nombre?: string;
    },
  ) =>
    jsonFetch<Campana>(`/api/social/${encodeURIComponent(postId)}/amplificar`, {
      method: 'POST',
      body: JSON.stringify(body),
    }),
  campanas: (limit = 20) => jsonFetch<Campana[]>(`/api/campanas?limit=${limit}`),

  dashboardEmbed: () =>
    jsonFetch<{ url: string | null; dashboard_id: string | null }>('/api/dashboard/embed-url'),
  genieSpace: () =>
    jsonFetch<{
      space_id: string | null;
      embed_url: string | null;
      mode: 'demo' | 'live';
      suggested_questions: string[];
    }>('/api/genie/space-id'),
  genieAsk: (content: string, conversation_id?: string) =>
    jsonFetch<{
      conversation_id: string;
      message_id: string;
      status: string;
      mode?: 'demo' | 'live';
      text: string;
      sql: string | null;
      query_result: { columns: string[]; rows: any[][]; row_count: number; truncated: boolean } | null;
      error: string | null;
    }>('/api/genie/ask', {
      method: 'POST',
      body: JSON.stringify({ content, conversation_id }),
    }),

  metas: (window_min = 30) => jsonFetch<MetaCategoria[]>(`/api/targets?window_min=${window_min}`),
  diagnosticar: (categoria: string) =>
    jsonFetch<DiagnosticoCategoria>(`/api/targets/${encodeURIComponent(categoria)}/diagnose`),
  skuDetalle: (categoria: string, sku: string) =>
    jsonFetch<SkuDetalle>(
      `/api/targets/${encodeURIComponent(categoria)}/sku/${encodeURIComponent(sku)}/detalle`,
    ),
  accionCategoria: (
    categoria: string,
    body: { action_type: string; params?: Record<string, any>; notes?: string },
  ) =>
    jsonFetch<{
      ok: boolean;
      log_id: string;
      categoria: string;
      action: string;
      actor: string;
      occurred_at: string;
    }>(`/api/targets/${encodeURIComponent(categoria)}/actions`, {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  pdv: (opts: { categoria?: string; country_code?: string; window_min?: number } = {}) => {
    const p = new URLSearchParams({ window_min: String(opts.window_min ?? 60) });
    if (opts.categoria) p.set('categoria', opts.categoria);
    if (opts.country_code) p.set('country_code', opts.country_code);
    return jsonFetch<Pdv[]>(`/api/pdv?${p}`);
  },
  pdvDetalle: (id: string) => jsonFetch<PdvDetalle>(`/api/pdv/${encodeURIComponent(id)}/detalle`),

  traslados: (opts: { estado?: EstadoTraslado; country_code?: string; limit?: number } = {}) => {
    const p = new URLSearchParams({ limit: String(opts.limit ?? 40) });
    if (opts.estado) p.set('estado', opts.estado);
    if (opts.country_code) p.set('country_code', opts.country_code);
    return jsonFetch<Traslado[]>(`/api/pdv/traslados?${p}`);
  },
  trasladosResumen: () => jsonFetch<ResumenTraslados>('/api/pdv/traslados/resumen'),
  decidirTraslado: (id: string, accion: 'aprobar' | 'descartar') =>
    jsonFetch<Traslado>(`/api/pdv/traslados/${encodeURIComponent(id)}/decidir`, {
      method: 'POST',
      body: JSON.stringify({ accion }),
    }),

  accionesCampo: (limit = 12, categoria?: string) => {
    const p = new URLSearchParams({ limit: String(limit) });
    if (categoria) p.set('categoria', categoria);
    return jsonFetch<AccionCampo[]>(`/api/campo/acciones?${p}`);
  },
  despacharAccion: (body: {
    store_id: string;
    sku: string;
    tipo_accion: string;
    tienda?: string;
    producto?: string;
    categoria?: string;
    country_code?: string;
    motivo?: string;
    urgencia?: string;
    impacto_usd?: number;
  }) =>
    jsonFetch<{ ok: boolean; id: string; actor: string }>('/api/campo/despachar', {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  lakebaseStatus: () => jsonFetch<LakebaseStatus>('/api/lakebase/status'),
  lakebasePdv: (opts: { q?: string; canal?: string; country_code?: string; limit?: number } = {}) => {
    const p = new URLSearchParams();
    if (opts.q) p.set('q', opts.q);
    if (opts.canal) p.set('canal', opts.canal);
    if (opts.country_code) p.set('country_code', opts.country_code);
    p.set('limit', String(opts.limit ?? 50));
    return jsonFetch<PdvPerfil[]>(`/api/lakebase/pdv?${p}`);
  },
  lakebasePdvDetalle: (id: string) =>
    jsonFetch<PdvPerfil>(`/api/lakebase/pdv/${encodeURIComponent(id)}`),
  lakebaseSugerir: (body: { store_id: string; categoria?: string; n?: number }) =>
    jsonFetch<SugerirResult>('/api/lakebase/sugerir', {
      method: 'POST',
      body: JSON.stringify(body),
    }),
  lakebaseRecientes: (limit = 20, estado?: EstadoSugerencia) => {
    const p = new URLSearchParams({ limit: String(limit) });
    if (estado) p.set('estado', estado);
    return jsonFetch<SugerenciaReciente[]>(`/api/lakebase/recientes?${p}`);
  },
  lakebaseEjecutar: (id: number, skus_ejecutados: string[], nota?: string) =>
    jsonFetch<EjecutarResult>(`/api/lakebase/sugerencia/${id}/ejecutar`, {
      method: 'POST',
      body: JSON.stringify({ skus_ejecutados, nota }),
    }),
  lakebaseFlujo: () => jsonFetch<FlujoCampo>('/api/lakebase/flujo'),
  lakebaseFlujoControl: (activo: boolean, ritmo_por_min = 6) =>
    jsonFetch<FlujoCampo>('/api/lakebase/flujo', {
      method: 'POST',
      body: JSON.stringify({ activo, ritmo_por_min }),
    }),
  lakebaseSugerencia: (id: number) =>
    jsonFetch<SugerenciaDetalle>(`/api/lakebase/sugerencia/${id}`),
  lakebaseStats: () => jsonFetch<LakebaseStats>('/api/lakebase/stats'),
  lakebaseImpacto: () => jsonFetch<LakebaseImpacto>('/api/lakebase/impacto'),

  /** SSE: entrega cada evento parseado hasta que el stream termina o se aborta. */
  streamExplicarCategoria: async function* (
    categoria: string,
    signal?: AbortSignal,
  ): AsyncGenerator<ExplainEvent> {
    const res = await fetch(`/api/targets/${encodeURIComponent(categoria)}/explain`, {
      method: 'POST',
      headers: { Accept: 'text/event-stream' },
      signal,
    });
    if (!res.ok || !res.body) {
      throw new Error(`${res.status} ${res.statusText}: ${await res.text().catch(() => '')}`);
    }
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      let idx;
      while ((idx = buffer.indexOf('\n\n')) !== -1) {
        const raw = buffer.slice(0, idx);
        buffer = buffer.slice(idx + 2);
        let event = 'message';
        let dataStr = '';
        for (const line of raw.split('\n')) {
          if (line.startsWith('event:')) event = line.slice(6).trim();
          else if (line.startsWith('data:')) dataStr += line.slice(5).trim();
        }
        if (!dataStr) continue;
        try {
          yield { type: event as ExplainEvent['type'], data: JSON.parse(dataStr) } as ExplainEvent;
        } catch {
          // frame malformado — se ignora
        }
      }
    }
  },
};
